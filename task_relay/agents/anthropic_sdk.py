from __future__ import annotations

import os
import re
from typing import Any

from task_relay.errors import AgentExecutionError
from task_relay.models import get_default_model
from task_relay.packer import CACHE_BREAK_MARKER, TEMPLATE_END_MARKER
from task_relay.types import AgentRunRequest, AgentRunResult, AgentUsage, TargetStatus

_CACHE_BREAK_RE = re.compile(rf"(?m)^{re.escape(CACHE_BREAK_MARKER)}$")
_TEMPLATE_END_RE = re.compile(rf"(?m)^{re.escape(TEMPLATE_END_MARKER)}$")
_DEFAULT_MAX_TOKENS = 4096


class AnthropicSDKRunner:
    name = "claude-sdk"

    def __init__(self, *, default_model: str | None = None) -> None:
        self.default_model = default_model or get_default_model("claude")

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise AgentExecutionError("ANTHROPIC_API_KEY environment variable is required for claude-sdk target.")

        anthropic = _import_anthropic()
        model = request.model or self.default_model
        system_blocks, messages = self._build_messages(request.prompt)
        client = anthropic.Anthropic(api_key=api_key)
        if request.timeout is not None and hasattr(client, "with_options"):
            client = client.with_options(timeout=request.timeout, max_retries=0)

        create_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": _DEFAULT_MAX_TOKENS,
            "messages": messages,
        }
        if system_blocks:
            create_kwargs["system"] = system_blocks

        try:
            response = client.messages.create(**create_kwargs)
        except Exception as exc:
            raise AgentExecutionError(f"claude-sdk request failed: {exc}") from exc

        return AgentRunResult(
            stdout=_extract_response_text(response),
            target=self.name,
            model=model,
            usage=_extract_usage(response),
        )

    def check(self) -> TargetStatus:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return TargetStatus(ok=False, reason="ANTHROPIC_API_KEY is not set")
        try:
            _import_anthropic()
        except AgentExecutionError as exc:
            return TargetStatus(ok=False, reason=str(exc))
        return TargetStatus(ok=True)

    def _parse_cache_markers(self, prompt: str) -> tuple[str | None, str]:
        matches = list(_CACHE_BREAK_RE.finditer(prompt))
        if not matches:
            return None, prompt
        if len(matches) > 1:
            raise AgentExecutionError("claude-sdk prompt contains multiple cache break markers.")
        match = matches[0]
        static_portion = prompt[:match.start()].rstrip()
        dynamic_portion = prompt[match.end():].lstrip("\n")
        return static_portion, dynamic_portion

    def _extract_template(self, static_portion: str) -> tuple[str | None, str]:
        matches = list(_TEMPLATE_END_RE.finditer(static_portion))
        if not matches:
            return None, static_portion
        if len(matches) > 1:
            raise AgentExecutionError("claude-sdk prompt contains multiple template end markers.")
        match = matches[0]
        template = static_portion[:match.start()].rstrip()
        static_user = static_portion[match.end():].lstrip("\n")
        return template, static_user

    def _build_messages(self, prompt: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        static_portion, dynamic_portion = self._parse_cache_markers(prompt)
        if static_portion is None:
            return [], [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

        template, static_user = self._extract_template(static_portion)
        system_blocks: list[dict[str, Any]] = []
        if template:
            system_blocks.append({
                "type": "text",
                "text": template,
                "cache_control": {"type": "ephemeral"},
            })

        content_blocks: list[dict[str, Any]] = []
        if static_user:
            content_blocks.append({
                "type": "text",
                "text": static_user,
                "cache_control": {"type": "ephemeral"},
            })
        if dynamic_portion:
            content_blocks.append({"type": "text", "text": dynamic_portion})
        if not content_blocks:
            content_blocks.append({"type": "text", "text": ""})
        return system_blocks, [{"role": "user", "content": content_blocks}]


def _import_anthropic():
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise AgentExecutionError("anthropic package is not installed; run project dependencies install.") from exc
    return anthropic


def _extract_response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts).strip()


def _extract_usage(response: Any) -> AgentUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return AgentUsage(
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", None),
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None),
    )
