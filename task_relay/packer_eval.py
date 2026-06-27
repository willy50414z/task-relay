"""Evaluate context-packer scope selection against labeled examples."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
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
        )
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
            "specs": _comparison(selected_specs, expected_specs),
            "task_blocks": _comparison(selected_task_blocks, expected_task_blocks),
            "design_sections": _comparison(selected_design_sections, expected_design_sections),
            "repo_files": _comparison(selected_repo_files, expected_repo_files),
            "evidence_count": len(example.evidence),
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
