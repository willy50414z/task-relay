"""Evaluate context-packer scope selection against labeled examples."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

from task_relay.packer import plan_packet


@dataclass(frozen=True)
class EvalExample:
    change: str
    mode: str
    task: str | None
    category: str
    expected_specs: tuple[str, ...]
    expected_task_blocks: tuple[str, ...]
    expected_design_sections: tuple[str, ...]
    expected_repo_files: tuple[str, ...]
    evidence: dict[str, str]
    quality_proxy: dict[str, Any] | None = None
    trace_filters: dict[str, dict[str, Any]] | None = None


def load_eval_set(path: str | Path) -> list[EvalExample]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    examples = payload.get("examples", payload)
    if not isinstance(examples, list):
        raise ValueError("eval set must be a list or an object with an examples list")
    return [_parse_example(item) for item in examples]


def run_eval_set(path: str | Path, *, cwd: str | None = None) -> dict[str, Any]:
    examples = load_eval_set(path)
    results: list[dict[str, Any]] = []
    spec_tp = spec_fp = spec_fn = 0
    task_tp = task_fp = task_fn = 0
    design_expected = design_found = 0
    fallback_count = 0
    total_packet_bytes = 0
    categories: dict[str, int] = {}

    for example in examples:
        plan = plan_packet(example.mode, example.change, task=example.task, cwd=cwd)
        report = plan.to_report(
            mode=example.mode,
            change=example.change,
            task=example.task,
            full_change_context=False,
            cache_layout_enabled=False,
        )
        trace_usage = _lookup_trace_usage(cwd, example, "packed")
        selected_specs = {
            str(section["source"])
            for section in report["sections"]
            if str(section["source"]).startswith("specs/")
        }
        selected_task_blocks = {
            str(section["label"])
            for section in report["sections"]
            if str(section["label"]).startswith("tasks.md")
        }
        selected_design_sections = {
            str(section["label"])
            for section in report["sections"]
            if str(section["label"]).startswith("design.md ::")
        }
        selected_repo_files = {str(ref["path"]) for ref in report["repo_references"]}

        expected_specs = set(example.expected_specs)
        expected_task_blocks = set(example.expected_task_blocks)
        expected_design_sections = set(example.expected_design_sections)
        expected_repo_files = set(example.expected_repo_files)

        spec_hit = selected_specs & expected_specs
        task_hit = selected_task_blocks & expected_task_blocks
        design_hit = selected_design_sections & expected_design_sections
        repo_hit = selected_repo_files & expected_repo_files

        spec_tp += len(spec_hit)
        spec_fp += len(selected_specs - expected_specs)
        spec_fn += len(expected_specs - selected_specs)
        task_tp += len(task_hit)
        task_fp += len(selected_task_blocks - expected_task_blocks)
        task_fn += len(expected_task_blocks - selected_task_blocks)
        design_expected += len(expected_design_sections)
        design_found += len(design_hit)
        fallback_count += 1 if report.get("fallback_reason") else 0
        total_packet_bytes += int(report["byte_estimate"])
        categories[example.category] = categories.get(example.category, 0) + 1

        results.append({
            "change": example.change,
            "mode": example.mode,
            "task": example.task,
            "category": example.category,
            "fallback_reason": report.get("fallback_reason"),
            "byte_estimate": report["byte_estimate"],
            "budget_status": report.get("budget_status"),
            "specs": _comparison(selected_specs, expected_specs),
            "task_blocks": _comparison(selected_task_blocks, expected_task_blocks),
            "design_sections": _comparison(selected_design_sections, expected_design_sections),
            "repo_files": _comparison(selected_repo_files, expected_repo_files),
            "evidence_count": len(example.evidence),
            "selection_accuracy": {
                "specs": _comparison(selected_specs, expected_specs),
                "task_blocks": _comparison(selected_task_blocks, expected_task_blocks),
                "design_sections": _comparison(selected_design_sections, expected_design_sections),
                "repo_files": _comparison(selected_repo_files, expected_repo_files),
            },
            "context_cost": {
                "byte_estimate": report["byte_estimate"],
                "estimated_input_tokens": _estimate_tokens(int(report["byte_estimate"])),
            },
            "cache_metrics": _compute_cache_metrics(report, trace_usage),
            "quality_outcome": _normalize_quality_proxy(example.quality_proxy),
        })

    total = len(examples)
    return {
        "sample_count": total,
        "category_coverage": dict(sorted(categories.items())),
        "metrics": {
            "spec_precision": _precision(spec_tp, spec_fp),
            "spec_recall": _recall(spec_tp, spec_fn),
            "task_block_precision": _precision(task_tp, task_fp),
            "task_block_recall": _recall(task_tp, task_fn),
            "fallback_rate": (fallback_count / total) if total else 0.0,
            "average_packet_bytes": (total_packet_bytes / total) if total else 0.0,
            "design_section_recall_secondary": (design_found / design_expected) if design_expected else None,
            "selection_accuracy": {
                "spec_precision": _precision(spec_tp, spec_fp),
                "spec_recall": _recall(spec_tp, spec_fn),
                "task_block_precision": _precision(task_tp, task_fp),
                "task_block_recall": _recall(task_tp, task_fn),
                "design_section_recall_secondary": (design_found / design_expected) if design_expected else None,
            },
            "context_cost": {
                "average_packet_bytes": (total_packet_bytes / total) if total else 0.0,
            },
            "quality_outcome": {
                "fallback_rate": (fallback_count / total) if total else 0.0,
            },
        },
        "results": results,
    }


def run_context_benchmark(path: str | Path, *, cwd: str | None = None) -> dict[str, Any]:
    examples = load_eval_set(path)
    results: list[dict[str, Any]] = []
    packed_bytes_total = 0
    full_bytes_total = 0
    packed_duration_total_ms = 0.0
    full_duration_total_ms = 0.0
    actual_metrics_available = False

    for example in examples:
        packed_start = time.monotonic()
        packed_plan = plan_packet(example.mode, example.change, task=example.task, cwd=cwd)
        packed_duration_ms = (time.monotonic() - packed_start) * 1000.0
        full_start = time.monotonic()
        full_plan = plan_packet(
            example.mode,
            example.change,
            task=example.task,
            cwd=cwd,
            full_change_context=True,
        )
        full_duration_ms = (time.monotonic() - full_start) * 1000.0

        packed_report = packed_plan.to_report(
            mode=example.mode,
            change=example.change,
            task=example.task,
            full_change_context=False,
            cache_layout_enabled=True,
        )
        full_report = full_plan.to_report(
            mode=example.mode,
            change=example.change,
            task=example.task,
            full_change_context=True,
            cache_layout_enabled=False,
        )

        packed_bytes = int(packed_report["byte_estimate"])
        full_bytes = int(full_report["byte_estimate"])
        packed_trace = _lookup_trace_usage(cwd, example, "packed")
        full_trace = _lookup_trace_usage(cwd, example, "full")
        packed_bytes_total += packed_bytes
        full_bytes_total += full_bytes
        packed_duration_total_ms += packed_duration_ms
        full_duration_total_ms += full_duration_ms
        actual_metrics_available = actual_metrics_available or packed_trace is not None or full_trace is not None

        packed_context_cost = _context_cost_payload(packed_bytes, packed_duration_ms, packed_trace)
        full_context_cost = _context_cost_payload(full_bytes, full_duration_ms, full_trace)
        quality_proxy = _normalize_quality_proxy(example.quality_proxy)

        results.append({
            "change": example.change,
            "mode": example.mode,
            "task": example.task,
            "category": example.category,
            "packed": {
                "byte_estimate": packed_bytes,
                "duration_ms": round(packed_duration_ms, 3),
                "fallback_reason": packed_report.get("fallback_reason"),
                "selection_mode": packed_report.get("selection_mode"),
                "budget_status": packed_report.get("budget_status"),
            },
            "full": {
                "byte_estimate": full_bytes,
                "duration_ms": round(full_duration_ms, 3),
                "fallback_reason": full_report.get("fallback_reason"),
                "selection_mode": full_report.get("selection_mode"),
                "budget_status": full_report.get("budget_status"),
            },
            "delta": {
                "bytes_saved": full_bytes - packed_bytes,
                "bytes_saved_ratio": None if full_bytes == 0 else (full_bytes - packed_bytes) / full_bytes,
            },
            "quality_proxy": quality_proxy,
            "tokens": {
                "packed_input_tokens": packed_trace["input_tokens"] if packed_trace else None,
                "packed_output_tokens": packed_trace["output_tokens"] if packed_trace else None,
                "full_input_tokens": full_trace["input_tokens"] if full_trace else None,
                "full_output_tokens": full_trace["output_tokens"] if full_trace else None,
            },
            "context_cost": {
                "packed": packed_context_cost,
                "full": full_context_cost,
            },
            "cache_metrics": _compute_cache_metrics(packed_report, packed_trace),
            "quality_outcome": quality_proxy,
        })

    sample_count = len(examples)
    bytes_saved_total = full_bytes_total - packed_bytes_total
    return {
        "sample_count": sample_count,
        "metrics": {
            "average_packed_bytes": (packed_bytes_total / sample_count) if sample_count else 0.0,
            "average_full_bytes": (full_bytes_total / sample_count) if sample_count else 0.0,
            "average_bytes_saved": (bytes_saved_total / sample_count) if sample_count else 0.0,
            "average_bytes_saved_ratio": None if full_bytes_total == 0 else bytes_saved_total / full_bytes_total,
            "average_packed_duration_ms": (packed_duration_total_ms / sample_count) if sample_count else 0.0,
            "average_full_duration_ms": (full_duration_total_ms / sample_count) if sample_count else 0.0,
            "token_metrics_available": actual_metrics_available,
            "selection_accuracy": {
                "samples": sample_count,
            },
            "context_cost": {
                "average_packed_estimated_tokens": (_estimate_tokens(packed_bytes_total) / sample_count) if sample_count else 0.0,
                "average_full_estimated_tokens": (_estimate_tokens(full_bytes_total) / sample_count) if sample_count else 0.0,
            },
            "quality_outcome": {
                "quality_proxy_fields": [
                    "review_artifact_sections_present",
                    "verification_passed",
                    "apply_exit_code",
                    "retry_count",
                ],
            },
        },
        "results": results,
    }


def _parse_example(item: object) -> EvalExample:
    if not isinstance(item, dict):
        raise ValueError("eval example must be an object")
    evidence = item.get("evidence", {})
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("eval example must include non-empty evidence")
    return EvalExample(
        change=str(item["change"]),
        mode=str(item.get("mode", "implementation-draft")),
        task=None if item.get("task") is None else str(item.get("task")),
        category=str(item.get("category", "uncategorized")),
        expected_specs=tuple(_list(item.get("expected_specs"))),
        expected_task_blocks=tuple(_list(item.get("expected_task_blocks"))),
        expected_design_sections=tuple(_list(item.get("expected_design_sections"))),
        expected_repo_files=tuple(_list(item.get("expected_repo_files"))),
        evidence={str(k): str(v) for k, v in evidence.items()},
        quality_proxy=item.get("quality_proxy") if isinstance(item.get("quality_proxy"), dict) else None,
        trace_filters=item.get("trace_filters") if isinstance(item.get("trace_filters"), dict) else None,
    )


def _list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("expected list field")


def _comparison(selected: set[str], expected: set[str]) -> dict[str, list[str]]:
    return {
        "selected": sorted(selected),
        "expected": sorted(expected),
        "missing": sorted(expected - selected),
        "extra": sorted(selected - expected),
    }


def _precision(tp: int, fp: int) -> float | None:
    denom = tp + fp
    return None if denom == 0 else tp / denom


def _recall(tp: int, fn: int) -> float | None:
    denom = tp + fn
    return None if denom == 0 else tp / denom


def _estimate_tokens(byte_count: int) -> int:
    return max(1, round(byte_count / 4)) if byte_count > 0 else 0


def _normalize_quality_proxy(raw: dict[str, Any] | None) -> dict[str, Any]:
    proxy = raw or {}
    return {
        "review_artifact_sections_present": proxy.get("review_artifact_sections_present", "missing"),
        "verification_passed": proxy.get("verification_passed", "missing"),
        "apply_exit_code": proxy.get("apply_exit_code", "missing"),
        "retry_count": proxy.get("retry_count", "missing"),
    }


def _context_cost_payload(byte_estimate: int, duration_ms: float, trace_usage: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "byte_estimate": byte_estimate,
        "estimated_input_tokens": _estimate_tokens(byte_estimate),
        "actual_input_tokens": trace_usage["input_tokens"] if trace_usage else "unavailable",
        "actual_output_tokens": trace_usage["output_tokens"] if trace_usage else "unavailable",
        "actual_cost_usd": trace_usage["cost_usd"] if trace_usage else "unavailable",
        "duration_ms": round(duration_ms, 3),
    }


def _compute_cache_metrics(
    report: dict[str, Any],
    trace_usage: dict[str, Any] | None,
) -> dict[str, Any] | None:
    static_bytes = report.get("static_byte_count")
    dynamic_bytes = report.get("dynamic_byte_count")
    if static_bytes is None and dynamic_bytes is None and trace_usage is None:
        return None

    cache_write_tokens = trace_usage.get("cache_creation_input_tokens") if trace_usage else None
    cache_read_tokens = trace_usage.get("cache_read_input_tokens") if trace_usage else None
    authoritative = cache_write_tokens is not None or cache_read_tokens is not None
    cache_hit = bool(cache_read_tokens) if authoritative else None

    metrics: dict[str, Any] = {
        "static_byte_count": static_bytes,
        "dynamic_byte_count": dynamic_bytes,
        "cache_write_tokens": cache_write_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_hit": cache_hit,
    }
    if authoritative:
        metrics["estimated_savings_tokens"] = int(cache_read_tokens or 0) * 9
        metrics["estimated_savings_authoritative"] = True
    elif static_bytes is not None:
        metrics["estimated_savings_tokens"] = _estimate_tokens(int(static_bytes))
        metrics["estimated_savings_authoritative"] = False
    else:
        metrics["estimated_savings_tokens"] = None
        metrics["estimated_savings_authoritative"] = False
    return metrics


def _lookup_trace_usage(cwd: str | None, example: EvalExample, variant: str) -> dict[str, Any] | None:
    filters = (example.trace_filters or {}).get(variant)
    if not isinstance(filters, dict):
        return None
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    trace_path = base / ".task_relay" / "trace.jsonl"
    if not trace_path.is_file():
        return None
    for line in reversed(trace_path.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if any(payload.get(key) != value for key, value in filters.items()):
            continue
        return {
            "input_tokens": payload.get("tokens_in", "unavailable"),
            "output_tokens": payload.get("tokens_out", "unavailable"),
            "cost_usd": payload.get("cost_usd", "unavailable"),
            "cache_creation_input_tokens": payload.get("cache_creation_input_tokens"),
            "cache_read_input_tokens": payload.get("cache_read_input_tokens"),
        }
    return None
