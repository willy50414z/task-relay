"""Simplified Python API for running the review gate.

Thin wrapper around review_gate.run_review_gate() that:
- Reads per-step workflow config from AGENTS.md
- Supports --target / --model override
- Provides cold-start config bootstrapping
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from task_relay.workflow.review_gate import ReviewGateResult, load_review_gate_config, run_review_gate
from task_relay.review_config import ReviewGateConfig, ReviewRoleEntry

logger = logging.getLogger(__name__)


def run_review(
    change: str,
    *,
    target: str | None = None,
    model: str | None = None,
    cwd: str | None = None,
) -> ReviewGateResult:
    """Run the full review gate (parallel reviewers + arbiter chain).

    Reads reviewer/arbiter config from the AGENTS.md managed block.
    Uses --target / --model overrides when provided.

    If target is "zerotoken" and the gateway is unreachable, automatically
    falls back to deepseek (reads fallback from step config if available).
    """
    base = Path(cwd).resolve() if cwd else Path.cwd()

    config = load_review_gate_config(str(base))

    if target or model:
        config = _apply_overrides(config, target=target, model=model)

    if target == "zerotoken" or any(r.agent == "zerotoken" for r in config.reviewers):
        if not _gateway_reachable():
            fallback_target = _read_fallback_target("review", base)
            print(
                f"zerotoken gateway unreachable — falling back to {fallback_target}",
                file=sys.stderr,
            )
            config = _apply_overrides(config, target=fallback_target, model=None)

    return run_review_gate(change, cwd=str(base), config=config)


def _gateway_reachable(timeout: float = 3.0) -> bool:
    """Quick check whether token-free-gateway is running at localhost:3456."""
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:3456/v1/models", method="GET")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def _read_fallback_target(step: str, base: Path) -> str:
    """Read fallback agent from per-step workflow config, defaulting to deepseek."""
    cfg = get_step_config(step, cwd=str(base))
    return cfg.get("fallback_agent", "deepseek")


def run_review(
    change: str,
    *,
    target: str | None = None,
    model: str | None = None,
    cwd: str | None = None,
) -> ReviewGateResult:
    """Run the full review gate (parallel reviewers + arbiter chain).

    Reads reviewer/arbiter config from the AGENTS.md managed block.
    Uses --target / --model overrides when provided.

    Returns a ReviewGateResult with decision, reviewer artifacts, and arbiter output.
    """
    base = Path(cwd).resolve() if cwd else Path.cwd()

    config = load_review_gate_config(str(base))

    if target or model:
        config = _apply_overrides(config, target=target, model=model)

    return run_review_gate(change, cwd=str(base), config=config)


def is_configured(cwd: str | None = None) -> bool:
    """Check whether a task-relay managed block exists in AGENTS.md."""
    base = Path(cwd).resolve() if cwd else Path.cwd()
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = base / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "<!-- task-relay:start -->" in text and "<!-- task-relay:end -->" in text:
            return True
    return False


def get_step_config(step: str, cwd: str | None = None) -> dict:
    """Read per-step workflow config from AGENTS.md managed block.

    Returns a dict with target, model, fallback keys.
    Example config line: workflow.review: target=zerotoken, model=deepseek-web/deepseek-chat, fallback=deepseek=deepseek-v4-pro
    """
    base = Path(cwd).resolve() if cwd else Path.cwd()
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = base / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find("<!-- task-relay:start -->")
        end = text.find("<!-- task-relay:end -->")
        if start == -1 or end == -1:
            continue
        block = text[start:end]
        prefix = f"workflow.{step}:"
        for line in block.splitlines():
            stripped = line.strip().lstrip("- ").strip()
            if stripped.startswith(prefix):
                return _parse_step_config_line(stripped[len(prefix):])
    return {}


def list_steps(cwd: str | None = None) -> dict[str, dict]:
    """List all configured workflow steps and their agent/model settings."""
    base = Path(cwd).resolve() if cwd else Path.cwd()
    steps: dict[str, dict] = {}
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = base / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        start = text.find("<!-- task-relay:start -->")
        end = text.find("<!-- task-relay:end -->")
        if start == -1 or end == -1:
            continue
        block = text[start:end]
        for line in block.splitlines():
            stripped = line.strip().lstrip("- ").strip()
            if stripped.startswith("workflow."):
                step_name = stripped.split(":", 1)[0].replace("workflow.", "")
                config_str = stripped.split(":", 1)[1] if ":" in stripped else ""
                steps[step_name] = _parse_step_config_line(config_str)
    return steps


def _parse_step_config_line(raw: str) -> dict:
    """Parse 'target=zerotoken, model=deepseek-web/deepseek-chat, fallback=deepseek=deepseek-v4-pro'"""
    config: dict = {}
    raw = raw.strip()
    if not raw:
        return config
    for part in raw.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip()
        if key == "fallback":
            # fallback=deepseek=deepseek-v4-pro → {"fallback_agent": "deepseek", "fallback_model": "deepseek-v4-pro"}
            if "=" in value:
                fa, _, fm = value.partition("=")
                config["fallback_agent"] = fa.strip()
                config["fallback_model"] = fm.strip()
            else:
                config["fallback_agent"] = value
        else:
            config[key] = value
    return config


def _apply_overrides(config: ReviewGateConfig, *, target: str | None, model: str | None) -> ReviewGateConfig:
    """Apply --target / --model overrides to reviewer entries."""
    from task_relay.review_config import ReviewRoleEntry

    new_reviewers = []
    for entry in config.reviewers:
        new_agent = target if target else entry.agent
        new_model = model if model else entry.model
        new_reviewers.append(ReviewRoleEntry(
            agent=new_agent,
            persona=entry.persona,
            model=new_model,
        ))
    return ReviewGateConfig(
        reviewers=tuple(new_reviewers),
        arbiters=config.arbiters,
        global_timeout=config.global_timeout,
        legacy_review_chain=config.legacy_review_chain,
    )
