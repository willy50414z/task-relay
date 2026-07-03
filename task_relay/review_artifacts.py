from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REVIEWER_VERDICTS = {"PASS", "CONCERNS", "BLOCKED"}
ARBITER_DECISIONS = {"APPROVE", "REVISE", "REJECT"}
FINDING_FIELDS = ("severity", "area", "description", "recommendation")
ACTIONABLE_ITEM_FIELDS = ("target_artifact", "required_change", "acceptance_criteria")
DEVILS_ADVOCATE_FIELDS = ("fatal_flaw", "simpler_alternative", "reverse_case")


class ArtifactValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def load_json_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ArtifactValidationError([f"expected review artifact missing: {path}"])
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ArtifactValidationError([f"expected review artifact is empty: {path}"])
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError([f"review artifact {path} is not valid JSON: {exc}"]) from exc
    if not isinstance(payload, dict):
        raise ArtifactValidationError([f"review artifact {path} must be a JSON object"])
    return payload


def validate_reviewer_artifact(payload: Mapping[str, Any], *, persona: str | None = None) -> list[str]:
    errors: list[str] = []
    required = {"reviewer", "verdict", "summary", "findings"}
    missing = required.difference(payload)
    for field in sorted(missing):
        errors.append(f"missing required field: {field}")

    verdict = payload.get("verdict")
    if verdict not in REVIEWER_VERDICTS:
        errors.append(f"verdict must be one of {', '.join(sorted(REVIEWER_VERDICTS))}")

    if not str(payload.get("reviewer", "")).strip() and "reviewer" in payload:
        errors.append("reviewer must be a non-empty string")
    if not str(payload.get("summary", "")).strip() and "summary" in payload:
        errors.append("summary must be a non-empty string")

    findings = payload.get("findings")
    if not isinstance(findings, list):
        if "findings" in payload:
            errors.append("findings must be an array")
        findings_list: list[Any] = []
    else:
        findings_list = findings

    for index, finding in enumerate(findings_list):
        if not isinstance(finding, dict):
            errors.append(f"findings[{index}] must be an object")
            continue
        for field in FINDING_FIELDS:
            if not str(finding.get(field, "")).strip():
                errors.append(f"findings[{index}] missing {field}")

    if verdict == "PASS" and findings_list:
        errors.append("PASS verdict requires an empty findings array")

    has_persona_concern = any(field in payload for field in DEVILS_ADVOCATE_FIELDS)
    if verdict in {"CONCERNS", "BLOCKED"} and not findings_list and not has_persona_concern:
        errors.append(f"{verdict} verdict requires at least one finding or persona-specific concern field")

    if persona == "/devils-advocate":
        for field in DEVILS_ADVOCATE_FIELDS:
            if field not in payload:
                errors.append(f"/devils-advocate artifact missing {field}")
            elif not isinstance(payload.get(field), dict):
                errors.append(f"/devils-advocate field {field} must be an object")

    return errors


def validate_arbiter_artifact(payload: Mapping[str, Any], *, persona: str | None = None) -> list[str]:
    errors: list[str] = []
    required = {"decision", "confidence", "summary", "actionable_items", "conflict_resolution"}
    missing = required.difference(payload)
    for field in sorted(missing):
        errors.append(f"missing required field: {field}")

    decision = payload.get("decision")
    if decision not in ARBITER_DECISIONS:
        errors.append(f"decision must be one of {', '.join(sorted(ARBITER_DECISIONS))}")

    if not str(payload.get("summary", "")).strip() and "summary" in payload:
        errors.append("summary must be a non-empty string")
    if not str(payload.get("conflict_resolution", "")).strip() and "conflict_resolution" in payload:
        errors.append("conflict_resolution must be a non-empty string")

    actionable_items = payload.get("actionable_items")
    if not isinstance(actionable_items, list):
        if "actionable_items" in payload:
            errors.append("actionable_items must be an array")
        items_list: list[Any] = []
    else:
        items_list = actionable_items

    if decision == "REVISE" and not items_list:
        errors.append("REVISE decision requires at least one actionable item")

    if decision == "REVISE":
        for index, item in enumerate(items_list):
            if not isinstance(item, dict):
                errors.append(f"actionable_items[{index}] must be an object")
                continue
            for field in ACTIONABLE_ITEM_FIELDS:
                if not str(item.get(field, "")).strip():
                    errors.append(f"actionable_items[{index}] missing {field}")

    return errors


def write_reviewer_artifact(output_path: Path, payload: Mapping[str, Any], *, persona: str | None = None) -> None:
    errors = validate_reviewer_artifact(payload, persona=persona)
    if errors:
        raise ArtifactValidationError(errors)
    _write_stable_json(output_path, payload)


def write_arbiter_artifact(output_path: Path, payload: Mapping[str, Any], *, persona: str | None = None) -> None:
    errors = validate_arbiter_artifact(payload, persona=persona)
    if errors:
        raise ArtifactValidationError(errors)
    _write_stable_json(output_path, payload)


def reviewer_schema_example(*, persona: str = "/review") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "reviewer": f"agent:{persona}",
        "verdict": "CONCERNS",
        "summary": "One concise sentence summarizing the review result.",
        "findings": [
            {
                "severity": "medium",
                "area": "scope",
                "description": "Problem statement.",
                "recommendation": "Concrete next step.",
            }
        ],
    }
    if persona == "/devils-advocate":
        payload.update(
            {
                "fatal_flaw": {
                    "assumption": "The assumption that would invalidate the proposal.",
                    "why_fatal": "Why this breaks the proposal.",
                    "evidence_needed": "What must be verified.",
                    "status": "unverified",
                },
                "simpler_alternative": {
                    "description": "Smallest viable alternative.",
                    "tradeoff": "What it loses.",
                    "recommendation": "consider",
                },
                "reverse_case": {
                    "opposite_approach": "What if we do the opposite?",
                    "when_better": "Conditions where the opposite is better.",
                    "risk": "Risk of ignoring it.",
                },
            }
        )
    return payload


def _write_stable_json(output_path: Path, payload: Mapping[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(prefix=f".{output_path.name}.", suffix=".tmp", dir=str(output_path.parent))
    tmp_path = Path(raw_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        tmp_path.replace(output_path)
    finally:
        tmp_path.unlink(missing_ok=True)
