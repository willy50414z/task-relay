"""TokenFreeGatewayRunner — adapter for @andeya/token-free-gateway.

Calls the OpenAI-compatible endpoint at localhost:3456/v1 to leverage
web-based LLM sessions (DeepSeek, ChatGPT, Gemini, etc.) without API tokens.

Protocol: AgentRunner (same as ClaudeRunner, CodexRunner, DeepSeekRunner).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from task_relay.types import AgentRunRequest, AgentRunResult, AgentUsage, TargetStatus

ZEROTOKEN_BASE_URL = "http://127.0.0.1:3456/v1"
ZEROTOKEN_DEFAULT_MODEL = "deepseek-web/deepseek-chat"

logger = logging.getLogger(__name__)


class TokenFreeGatewayRunner:
    """Agent runner that calls @andeya/token-free-gateway via HTTP.

    The gateway must be running: `token-free-gateway` (npm global install).
    It exposes an OpenAI-compatible API at localhost:3456.

    Model naming convention: <provider>/<model>
      - deepseek-web/deepseek-chat
      - chatgpt-web/gpt-4
      - gemini-web/gemini-pro
    """

    name = "zerotoken"

    def __init__(self, *, default_model: str | None = None) -> None:
        self.default_model = default_model or ZEROTOKEN_DEFAULT_MODEL

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        model = request.model or self.default_model
        timeout = request.timeout or 600

        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0.3,
        }).encode("utf-8")

        retries = 0
        deadline = time.monotonic() + timeout

        while True:
            try:
                req = urllib.request.Request(
                    f"{ZEROTOKEN_BASE_URL}/chat/completions",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                remaining = max(1.0, deadline - time.monotonic())
                with urllib.request.urlopen(req, timeout=remaining) as resp:
                    body = json.loads(resp.read().decode("utf-8"))

                content = _extract_content(body)
                usage = _extract_usage(body)

                return AgentRunResult(
                    stdout=content,
                    target=self.name,
                    model=model,
                    retries=retries,
                    usage=usage,
                )

            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                retries += 1
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise _gateway_error(exc, retries) from exc
                wait = min(5 * (2 ** (retries - 1)), 60)
                if wait > remaining:
                    wait = remaining
                logger.warning(
                    "zerotoken gateway error (attempt %d), retrying in %.0fs: %s",
                    retries, wait, exc,
                )
                time.sleep(wait)

    def check(self) -> TargetStatus:
        try:
            req = urllib.request.Request(
                f"{ZEROTOKEN_BASE_URL}/models",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return TargetStatus(ok=True)
                return TargetStatus(ok=False, reason=f"gateway returned HTTP {resp.status}")
        except urllib.error.URLError as exc:
            return TargetStatus(ok=False, reason=f"gateway unreachable: {exc.reason}")
        except OSError as exc:
            return TargetStatus(ok=False, reason=f"connection failed: {exc}")
        except Exception as exc:
            return TargetStatus(ok=False, reason=str(exc)[:200])


def _extract_content(body: dict) -> str:
    """Extract message content from an OpenAI-compatible chat completion response."""
    choices = body.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if content:
            return str(content)
    # Fallback: return raw JSON
    return json.dumps(body, ensure_ascii=False)


def _extract_usage(body: dict) -> AgentUsage | None:
    """Extract token usage from response."""
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
    if input_tokens is None and output_tokens is None:
        return None
    return AgentUsage(
        input_tokens=int(input_tokens) if input_tokens is not None else None,
        output_tokens=int(output_tokens) if output_tokens is not None else None,
        cost_usd=0.0,  # web sessions have no per-token cost
    )


def _gateway_error(exc: Exception, retries: int) -> Exception:
    from task_relay.errors import AgentExecutionError

    return AgentExecutionError(
        f"zerotoken gateway unreachable after {retries} retries: {exc}"
    )
