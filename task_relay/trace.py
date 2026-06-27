from __future__ import annotations

import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from task_relay import worktree

_TRACE_ENV = "TASK_RELAY_TRACE_FILE"
_MODE_RE = re.compile(r"^Mode:\s*`([^`]+)`", re.MULTILINE)
_TASK_RE = re.compile(r"^Task id:\s*`([^`]+)`", re.MULTILINE)
_CHANGE_RE = re.compile(r"^Change:\s*`([^`]+)`", re.MULTILINE)
_CHANGE_PATH_RE = re.compile(r"openspec/changes/([^/]+)/")


def new_session_id() -> str:
    return f"trly-{int(time.time())}-{os.getpid()}"


def extract_prompt_context(prompt: str) -> dict[str, str | None]:
    mode_match = _MODE_RE.search(prompt)
    task_match = _TASK_RE.search(prompt)
    change_match = _CHANGE_RE.search(prompt) or _CHANGE_PATH_RE.search(prompt)
    return {
        "role": mode_match.group(1) if mode_match else None,
        "task": task_match.group(1) if task_match else None,
        "change": change_match.group(1) if change_match else None,
    }


def resolve_trace_path(cwd: str | None = None) -> Path:
    configured = os.getenv(_TRACE_ENV, "").strip()
    repo_root = worktree.git_repo_root(cwd)
    base = repo_root or (Path(cwd).resolve() if cwd else Path.cwd())
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = base / path
        return path
    return base / ".task_relay" / "trace.jsonl"


def append_trace_record(record: dict[str, Any], *, cwd: str | None = None) -> Path:
    path = resolve_trace_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return path


def load_trace_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def summarize_trace_records(records: list[dict[str, Any]], *, change: str | None = None) -> dict[str, Any]:
    if change:
        records = [record for record in records if record.get("change") == change]
    if not records:
        return {"count": 0, "change": change}

    per_agent: dict[str, dict[str, Any]] = defaultdict(_blank_bucket)
    per_role: dict[str, dict[str, Any]] = defaultdict(_blank_bucket)
    outcomes: Counter[str] = Counter()

    total_duration = 0.0
    total_retries = 0
    total_cost = 0.0
    cost_known = False
    input_total = 0
    output_total = 0
    input_unknown = 0
    output_unknown = 0
    fallback_count = 0

    for record in records:
        duration = float(record.get("duration_s") or 0.0)
        retries = int(record.get("retries") or 0)
        outcome = str(record.get("outcome") or "unknown")
        fallback_from = record.get("fallback_from")
        agent = str(record.get("target") or "unknown")
        role = str(record.get("role") or "unknown")
        tokens_in = record.get("tokens_in")
        tokens_out = record.get("tokens_out")
        cost = record.get("cost_usd")

        total_duration += duration
        total_retries += retries
        outcomes[outcome] += 1
        if fallback_from:
            fallback_count += 1

        if tokens_in is None:
            input_unknown += 1
        else:
            input_total += int(tokens_in)
        if tokens_out is None:
            output_unknown += 1
        else:
            output_total += int(tokens_out)
        if cost is not None:
            total_cost += float(cost)
            cost_known = True

        _update_bucket(per_agent[agent], duration, retries, tokens_in, tokens_out, cost)
        _update_bucket(per_role[role], duration, retries, tokens_in, tokens_out, cost)

    return {
        "count": len(records),
        "change": change,
        "total_duration_s": total_duration,
        "total_retries": total_retries,
        "fallback_count": fallback_count,
        "outcomes": dict(outcomes),
        "tokens": {
            "input_total": input_total,
            "output_total": output_total,
            "input_unknown": input_unknown,
            "output_unknown": output_unknown,
        },
        "cost_usd": total_cost if cost_known else None,
        "per_agent": {key: _finalize_bucket(value) for key, value in sorted(per_agent.items())},
        "per_role": {key: _finalize_bucket(value) for key, value in sorted(per_role.items())},
    }


def format_summary(summary: dict[str, Any]) -> str:
    if summary.get("count", 0) == 0:
        return "no records"
    tokens = summary["tokens"]
    lines = [
        f"delegations: {summary['count']}",
        f"total duration (s): {summary['total_duration_s']:.2f}",
        f"total retries: {summary['total_retries']}",
        f"fallbacks: {summary['fallback_count']}",
        (
            "tokens: "
            f"input={tokens['input_total']} (unknown={tokens['input_unknown']}), "
            f"output={tokens['output_total']} (unknown={tokens['output_unknown']})"
        ),
        "cost usd: unknown" if summary["cost_usd"] is None else f"cost usd: {summary['cost_usd']:.6f}",
        "outcomes: " + ", ".join(
            f"{key}={value}" for key, value in sorted(summary["outcomes"].items())
        ),
        "per-agent:",
    ]
    for name, bucket in summary["per_agent"].items():
        lines.append(_format_bucket(name, bucket))
    lines.append("per-role:")
    for name, bucket in summary["per_role"].items():
        lines.append(_format_bucket(name, bucket))
    return "\n".join(lines)


def _blank_bucket() -> dict[str, Any]:
    return {
        "count": 0,
        "duration_s": 0.0,
        "retries": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "tokens_in_unknown": 0,
        "tokens_out_unknown": 0,
        "cost_usd": 0.0,
        "cost_known": False,
    }


def _update_bucket(bucket: dict[str, Any], duration: float, retries: int, tokens_in, tokens_out, cost) -> None:
    bucket["count"] += 1
    bucket["duration_s"] += duration
    bucket["retries"] += retries
    if tokens_in is None:
        bucket["tokens_in_unknown"] += 1
    else:
        bucket["tokens_in"] += int(tokens_in)
    if tokens_out is None:
        bucket["tokens_out_unknown"] += 1
    else:
        bucket["tokens_out"] += int(tokens_out)
    if cost is not None:
        bucket["cost_usd"] += float(cost)
        bucket["cost_known"] = True


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    result = dict(bucket)
    if not result.pop("cost_known"):
        result["cost_usd"] = None
    return result


def _format_bucket(name: str, bucket: dict[str, Any]) -> str:
    cost = "unknown" if bucket["cost_usd"] is None else f"{bucket['cost_usd']:.6f}"
    return (
        f"- {name}: count={bucket['count']}, duration_s={bucket['duration_s']:.2f}, "
        f"retries={bucket['retries']}, tokens_in={bucket['tokens_in']} "
        f"(unknown={bucket['tokens_in_unknown']}), tokens_out={bucket['tokens_out']} "
        f"(unknown={bucket['tokens_out_unknown']}), cost_usd={cost}"
    )
