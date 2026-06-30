from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
import hashlib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from task_relay import jobs
from task_relay.delegation import parse_existing_block
from task_relay.errors import ReviewArtifactError, ReviewGateConfigError, ReviewGateTimeoutError
from task_relay.packer import build_packet
from task_relay.review_config import (
    DEFAULT_GLOBAL_TIMEOUT,
    DEFAULT_REVIEWER_PERSONA,
    ReviewGateConfig,
    ReviewRoleEntry,
    default_arbiter_entries,
    parse_role_entries,
)

APPROVE_EXIT_CODE = 0
REVISE_EXIT_CODE = 10
REJECT_EXIT_CODE = 20
CONFIG_EXIT_CODE = 2
TIMEOUT_EXIT_CODE = 124
RUNTIME_EXIT_CODE = 1

REVIEWER_VERDICTS = {"PASS", "CONCERNS", "BLOCKED"}
ARBITER_DECISIONS = {"APPROVE", "REVISE", "REJECT"}


@dataclass(frozen=True)
class ReviewArtifact:
    reviewer_id: str
    entry: ReviewRoleEntry
    path: Path
    payload: dict


@dataclass(frozen=True)
class ArbiterArtifact:
    stage_id: str
    entry: ReviewRoleEntry
    path: Path
    payload: dict


@dataclass(frozen=True)
class ReviewGateResult:
    decision: str
    reviewer_artifacts: tuple[ReviewArtifact, ...]
    arbiter_artifacts: tuple[ArbiterArtifact, ...]
    summary_path: Path
    result_path: Path


def load_review_gate_config(cwd: str | None = None) -> ReviewGateConfig:
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = base / name
        parsed = parse_existing_block(path)
        if not parsed:
            continue
        reviewers = tuple(parsed.get("reviewers") or [])
        if not reviewers and parsed.get("review_chain"):
            from task_relay.review_config import migrate_legacy_review_chain

            reviewers = tuple(migrate_legacy_review_chain(parsed["review_chain"]))
        arbiters = tuple(parsed.get("arbiters") or (default_arbiter_entries() if reviewers else []))
        return ReviewGateConfig(
            reviewers=reviewers,
            arbiters=arbiters,
            global_timeout=int(parsed.get("global_timeout") or DEFAULT_GLOBAL_TIMEOUT),
            legacy_review_chain=tuple(parsed.get("review_chain") or ()),
        )
    raise ReviewGateConfigError(f"no managed review gate configuration found under {base}")


def run_review_gate(
    change: str,
    *,
    cwd: str | None = None,
    config: ReviewGateConfig | None = None,
) -> ReviewGateResult:
    effective_config = config or load_review_gate_config(cwd)
    _validate_config(effective_config)
    return asyncio.run(_run_review_gate_async(change, effective_config, cwd=cwd))


async def _run_review_gate_async(
    change: str,
    config: ReviewGateConfig,
    *,
    cwd: str | None = None,
) -> ReviewGateResult:
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    review_dir = _review_dir(base, change)
    review_dir.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + config.global_timeout

    reviewers = await run_parallel_review(change, config, cwd=str(base), deadline=deadline)
    arbiters = await run_arbiter_chain(change, config, reviewers, cwd=str(base), deadline=deadline)
    decision = _aggregate_decision(arbiters)
    result_path = _write_result_json(base, change, decision, reviewers, arbiters)
    summary_path = _write_summary(review_dir / "delegation_review.md", decision, reviewers, arbiters)
    return ReviewGateResult(
        decision=decision,
        reviewer_artifacts=tuple(reviewers),
        arbiter_artifacts=tuple(arbiters),
        summary_path=summary_path,
        result_path=result_path,
    )


async def run_parallel_review(
    change: str,
    config: ReviewGateConfig,
    *,
    cwd: str,
    deadline: float,
) -> list[ReviewArtifact]:
    ids = _unique_entry_ids(config.reviewers)
    tasks = [
        _run_reviewer(change, reviewer_id, entry, cwd=cwd, timeout=_remaining_timeout(deadline))
        for reviewer_id, entry in ids
    ]
    try:
        return list(await asyncio.gather(*tasks))
    except asyncio.TimeoutError as exc:
        raise ReviewGateTimeoutError("review gate timed out while waiting for reviewer subprocesses") from exc


async def run_arbiter_chain(
    change: str,
    config: ReviewGateConfig,
    reviewers: list[ReviewArtifact],
    *,
    cwd: str,
    deadline: float,
) -> list[ArbiterArtifact]:
    results: list[ArbiterArtifact] = []
    for stage_id, entry in _unique_entry_ids(config.arbiters):
        artifact = await _run_arbiter(
            change,
            stage_id,
            entry,
            reviewers,
            results,
            cwd=cwd,
            timeout=_remaining_timeout(deadline),
        )
        results.append(artifact)
        if artifact.payload["decision"] == "REJECT":
            break
    return results


async def _run_reviewer(
    change: str,
    reviewer_id: str,
    entry: ReviewRoleEntry,
    *,
    cwd: str,
    timeout: float,
) -> ReviewArtifact:
    output_path = _review_dir(Path(cwd), change) / f"delegation_review_{reviewer_id}.json"
    packet_text = build_packet("review-proposal", change, cwd=cwd, full_change_context=True)
    packet_text = _prepend_persona_packet(entry, packet_text, output_path)
    packet_path = _write_temp_packet(packet_text)
    try:
        await _run_subprocess(
            _reviewer_command(entry, packet_path, output_path),
            cwd=cwd,
            timeout=timeout,
            target=entry.agent,
            role=reviewer_id,
            change=change,
            expected_output=output_path,
        )
        payload = _validate_reviewer_artifact(output_path)
        return ReviewArtifact(reviewer_id=reviewer_id, entry=entry, path=output_path, payload=payload)
    finally:
        packet_path.unlink(missing_ok=True)


async def _run_arbiter(
    change: str,
    stage_id: str,
    entry: ReviewRoleEntry,
    reviewers: list[ReviewArtifact],
    prior_arbiters: list[ArbiterArtifact],
    *,
    cwd: str,
    timeout: float,
) -> ArbiterArtifact:
    output_path = _review_dir(Path(cwd), change) / f"delegation_arbiter_{stage_id}.json"
    packet_text = build_packet("review-arbiter", change, cwd=cwd, full_change_context=True)
    packet_text = _prepend_arbiter_packet(entry, packet_text, reviewers, prior_arbiters, output_path)
    packet_path = _write_temp_packet(packet_text)
    try:
        await _run_subprocess(
            _reviewer_command(entry, packet_path, output_path),
            cwd=cwd,
            timeout=timeout,
            target=entry.agent,
            role=stage_id,
            change=change,
            expected_output=output_path,
        )
        payload = _validate_arbiter_artifact(output_path)
        return ArbiterArtifact(stage_id=stage_id, entry=entry, path=output_path, payload=payload)
    finally:
        packet_path.unlink(missing_ok=True)


def _reviewer_command(entry: ReviewRoleEntry, packet_path: Path, output_path: Path) -> list[str]:
    cmd = [
        os.getenv("TASK_RELAY_BIN", "trly"),
        "run",
        "--target",
        entry.agent,
        "--prompt-file",
        str(packet_path),
        "--expect-output",
        str(output_path),
    ]
    if entry.model:
        cmd.extend(["--model", entry.model])
    return cmd


async def _run_subprocess(
    cmd: list[str],
    *,
    cwd: str,
    timeout: float,
    target: str | None = None,
    role: str | None = None,
    change: str | None = None,
    expected_output: Path | None = None,
) -> None:
    result = await jobs.run_async(
        jobs.JobSpec(
            command=cmd,
            cwd=cwd,
            timeout=timeout,
            target=target,
            role=role,
            change=change,
            expected_outputs=[str(expected_output)] if expected_output else [],
        )
    )
    if result.status == jobs.JOB_STATUS_TIMEOUT:
        raise ReviewGateTimeoutError(_job_detail("review gate subprocess timed out", result, expected_output))
    if result.status != jobs.JOB_STATUS_SUCCEEDED:
        detail = (result.stderr or result.stdout or "").strip()
        raise ReviewArtifactError(
            _job_detail(f"review gate subprocess failed ({result.returncode}): {detail}", result, expected_output)
        )


def _job_detail(message: str, result: jobs.JobRunResult, expected_output: Path | None) -> str:
    parts = [
        message,
        f"job_id={result.job_id}",
        f"status={result.status}",
        f"log={result.log_path}",
    ]
    if expected_output is not None:
        parts.append(f"expected_output={expected_output}")
    return " | ".join(parts)


def _validate_config(config: ReviewGateConfig) -> None:
    if not config.reviewers:
        raise ReviewGateConfigError("review gate requires at least one reviewer")
    if not config.arbiters:
        raise ReviewGateConfigError("review gate requires at least one arbiter")
    if config.global_timeout <= 0:
        raise ReviewGateConfigError("global timeout must be positive")


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ReviewGateTimeoutError("review gate global timeout expired")
    return remaining


def _validate_reviewer_artifact(path: Path) -> dict:
    payload = _load_json(path)
    required = {"reviewer", "verdict", "summary", "findings"}
    missing = required.difference(payload)
    if missing:
        raise ReviewArtifactError(f"reviewer artifact {path} missing fields: {', '.join(sorted(missing))}")
    if payload["verdict"] not in REVIEWER_VERDICTS:
        raise ReviewArtifactError(f"reviewer artifact {path} has invalid verdict: {payload['verdict']}")
    if not isinstance(payload["findings"], list):
        raise ReviewArtifactError(f"reviewer artifact {path} findings must be an array")
    for finding in payload["findings"]:
        if not isinstance(finding, dict):
            raise ReviewArtifactError(f"reviewer artifact {path} has non-object finding")
        for field in ("severity", "area", "description", "recommendation"):
            if not str(finding.get(field, "")).strip():
                raise ReviewArtifactError(f"reviewer artifact {path} finding missing {field}")
    return payload


def _validate_arbiter_artifact(path: Path) -> dict:
    payload = _load_json(path)
    required = {"decision", "confidence", "summary", "actionable_items", "conflict_resolution"}
    missing = required.difference(payload)
    if missing:
        raise ReviewArtifactError(f"arbiter artifact {path} missing fields: {', '.join(sorted(missing))}")
    if payload["decision"] not in ARBITER_DECISIONS:
        raise ReviewArtifactError(f"arbiter artifact {path} has invalid decision: {payload['decision']}")
    if not isinstance(payload["actionable_items"], list):
        raise ReviewArtifactError(f"arbiter artifact {path} actionable_items must be an array")
    if payload["decision"] == "REVISE":
        for item in payload["actionable_items"]:
            if not isinstance(item, dict):
                raise ReviewArtifactError(f"arbiter artifact {path} has non-object actionable item")
            for field in ("target_artifact", "required_change", "acceptance_criteria"):
                if not str(item.get(field, "")).strip():
                    raise ReviewArtifactError(f"arbiter artifact {path} actionable item missing {field}")
    return payload


def _aggregate_decision(arbiters: list[ArbiterArtifact]) -> str:
    decisions = [artifact.payload["decision"] for artifact in arbiters]
    if any(decision == "REJECT" for decision in decisions):
        return "REJECT"
    if any(decision == "REVISE" for decision in decisions):
        return "REVISE"
    return "APPROVE"


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise ReviewArtifactError(f"expected review artifact missing: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ReviewArtifactError(f"expected review artifact is empty: {path}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewArtifactError(f"review artifact {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewArtifactError(f"review artifact {path} must be a JSON object")
    return payload


def _write_summary(
    path: Path,
    decision: str,
    reviewers: list[ReviewArtifact],
    arbiters: list[ArbiterArtifact],
) -> Path:
    lines = [
        "# Delegation Review Summary",
        "",
        f"- Final decision: {decision}",
        "",
        "## Reviewer Artifacts",
    ]
    for reviewer in reviewers:
        lines.append(f"- `{reviewer.reviewer_id}`: `{reviewer.path}`")
    lines.append("")
    lines.append("## Arbiter Artifacts")
    for arbiter in arbiters:
        lines.append(f"- `{arbiter.stage_id}`: `{arbiter.path}`")
    lines.append("")
    lines.append("## Arbiter Summaries")
    for arbiter in arbiters:
        lines.append(f"- `{arbiter.stage_id}`: {arbiter.payload['summary']}")
        for item in arbiter.payload.get("actionable_items", []):
            lines.append(
                f"  - `{item.get('target_artifact', '')}`: {item.get('required_change', '')} "
                f"(acceptance: {item.get('acceptance_criteria', '')})"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_result_json(
    base: Path,
    change: str,
    decision: str,
    reviewers: list[ReviewArtifact],
    arbiters: list[ArbiterArtifact],
) -> Path:
    path = _review_dir(base, change) / "delegation_review_result.json"
    actionable_items = _collect_actionable_items(arbiters)
    payload = {
        "change": change,
        "decision": decision,
        "apply_allowed": decision != "REJECT",
        "requires_primary_revision": decision == "REVISE",
        "reviewers": [
            {
                "id": artifact.reviewer_id,
                "path": str(artifact.path),
                "reviewer": artifact.payload.get("reviewer"),
                "verdict": artifact.payload.get("verdict"),
            }
            for artifact in reviewers
        ],
        "arbiters": [
            {
                "id": artifact.stage_id,
                "path": str(artifact.path),
                "decision": artifact.payload.get("decision"),
                "summary": artifact.payload.get("summary"),
            }
            for artifact in arbiters
        ],
        "actionable_items": actionable_items,
        "target_artifacts": _target_artifact_state(base, change, actionable_items),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_temp_packet(text: str) -> Path:
    fd, raw_path = tempfile.mkstemp(prefix="trly-review-gate-", suffix=".md")
    path = Path(raw_path)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _prepend_persona_packet(entry: ReviewRoleEntry, packet: str, output_path: Path) -> str:
    persona = entry.persona or DEFAULT_REVIEWER_PERSONA
    strict = _strict_reviewer_output_contract(entry, output_path)
    return (
        f"Reviewer persona: `{entry.agent}:{persona}`\n"
        f"Expected output path: `{output_path}`\n"
        f"{strict}\n\n"
        f"{_persona_text(persona)}\n\n"
        f"{packet}"
    )


def _prepend_arbiter_packet(
    entry: ReviewRoleEntry,
    packet: str,
    reviewers: list[ReviewArtifact],
    arbiters: list[ArbiterArtifact],
    output_path: Path,
) -> str:
    reviewer_json = "\n\n".join(
        f"### {artifact.reviewer_id}\n\n```json\n{json.dumps(artifact.payload, ensure_ascii=False, indent=2)}\n```"
        for artifact in reviewers
    )
    prior_arbiter_json = "\n\n".join(
        f"### {artifact.stage_id}\n\n```json\n{json.dumps(artifact.payload, ensure_ascii=False, indent=2)}\n```"
        for artifact in arbiters
    )
    parts = [
        f"Arbiter persona: `{entry.agent}:{entry.persona}`",
        f"Expected output path: `{output_path}`",
        _strict_arbiter_output_contract(entry, output_path),
        "",
        _persona_text(entry.persona or "/plan-eng-review"),
        "",
        packet,
        "",
        "## Reviewer JSON",
        reviewer_json or "_none_",
    ]
    if prior_arbiter_json:
        parts.extend(["", "## Prior Arbiter JSON", prior_arbiter_json])
    return "\n".join(parts)


def _unique_entry_ids(entries: tuple[ReviewRoleEntry, ...] | list[ReviewRoleEntry]) -> list[tuple[str, ReviewRoleEntry]]:
    counts: dict[str, int] = {}
    result: list[tuple[str, ReviewRoleEntry]] = []
    for entry in entries:
        persona = entry.persona or DEFAULT_REVIEWER_PERSONA
        base = f"{_slug(entry.agent)}_{_slug(persona.lstrip('/'))}"
        counts[base] = counts.get(base, 0) + 1
        identifier = base if counts[base] == 1 else f"{base}_{counts[base]}"
        result.append((identifier, entry))
    return result


def _strict_reviewer_output_contract(entry: ReviewRoleEntry, output_path: Path) -> str:
    lines = ["Return JSON only."]
    if entry.agent == "deepseek":
        lines.extend([
            f"You MUST create the JSON file at `{output_path}`.",
            "Do not output markdown fences.",
            "Do not output prose before or after the JSON object.",
            "Do not use fields named `category` or `title` inside findings.",
            "Every finding object MUST contain exactly these required fields: `severity`, `area`, `description`, `recommendation`.",
            "Valid verdict values: `PASS`, `CONCERNS`, `BLOCKED`.",
            "Valid area values: `architecture`, `security`, `qa`, `scope`, `tests`.",
            "If there are no findings, return an empty findings array.",
        ])
    return "\n".join(lines)


def _strict_arbiter_output_contract(entry: ReviewRoleEntry, output_path: Path) -> str:
    lines = ["Return JSON only."]
    if entry.agent == "deepseek":
        lines.extend([
            f"You MUST create the JSON file at `{output_path}`.",
            "Do not output markdown fences.",
            "Do not output prose before or after the JSON object.",
            "Every actionable item MUST contain `target_artifact`, `required_change`, and `acceptance_criteria`.",
            "Valid decision values: `APPROVE`, `REVISE`, `REJECT`.",
            "If the decision is `REVISE`, actionable_items MUST be non-empty.",
            "If the decision is not `REVISE`, actionable_items MAY be an empty array.",
        ])
    return "\n".join(lines)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "stage"


def _persona_text(persona: str) -> str:
    mapping = {
        "/review": "reviewer-review.md",
        "/cso": "reviewer-cso.md",
        "/qa-only": "reviewer-qa-only.md",
        "/plan-ceo-review": "arbiter-plan-ceo-review.md",
        "/plan-eng-review": "arbiter-plan-eng-review.md",
    }
    name = mapping.get(persona)
    if name is None:
        return ""
    try:
        return resources.files("task_relay.assets").joinpath(f"task-relay-delegation/personas/{name}").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def verify_revision_readiness(
    change: str,
    *,
    cwd: str | None = None,
    result_path: str | None = None,
) -> dict:
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    change_dir = base / "openspec" / "changes" / change
    path = Path(result_path) if result_path else _review_dir(base, change) / "delegation_review_result.json"
    if not path.is_absolute():
        path = base / path
    payload = _load_json(path)
    decision = str(payload.get("decision") or "")
    target_artifacts = payload.get("target_artifacts") or []
    if decision == "REJECT":
        return {
            "decision": decision,
            "apply_ready": False,
            "requires_primary_revision": False,
            "pending_targets": [],
            "satisfied_targets": [],
        }
    if decision == "APPROVE":
        return {
            "decision": decision,
            "apply_ready": True,
            "requires_primary_revision": False,
            "pending_targets": [],
            "satisfied_targets": [],
        }
    pending_targets: list[str] = []
    satisfied_targets: list[str] = []
    for item in target_artifacts:
        rel_path = str(item.get("path") or "").strip()
        baseline_sha = item.get("baseline_sha256")
        current_sha = _artifact_sha256(change_dir / rel_path)
        if current_sha == baseline_sha:
            pending_targets.append(rel_path)
        else:
            satisfied_targets.append(rel_path)
    return {
        "decision": decision,
        "apply_ready": not pending_targets,
        "requires_primary_revision": True,
        "pending_targets": pending_targets,
        "satisfied_targets": satisfied_targets,
    }


def config_from_args(args) -> ReviewGateConfig:
    reviewers = tuple(parse_role_entries(args.reviewers)) if getattr(args, "reviewers", None) else ()
    arbiters = tuple(
        entry
        for value in (getattr(args, "arbiter", None) or [])
        for entry in parse_role_entries(value)
    )
    if reviewers:
        return ReviewGateConfig(
            reviewers=reviewers,
            arbiters=arbiters or tuple(default_arbiter_entries()),
            global_timeout=int(getattr(args, "global_timeout", DEFAULT_GLOBAL_TIMEOUT)),
        )
    return load_review_gate_config(getattr(args, "cwd", None))


def exit_code_for_result(result: ReviewGateResult) -> int:
    return {
        "APPROVE": APPROVE_EXIT_CODE,
        "REVISE": REVISE_EXIT_CODE,
        "REJECT": REJECT_EXIT_CODE,
    }[result.decision]


def _collect_actionable_items(arbiters: list[ArbiterArtifact]) -> list[dict]:
    items: list[dict] = []
    for artifact in arbiters:
        for item in artifact.payload.get("actionable_items", []):
            if isinstance(item, dict):
                items.append(dict(item))
    return items


def _target_artifact_state(base: Path, change: str, actionable_items: list[dict]) -> list[dict]:
    change_dir = base / "openspec" / "changes" / change
    seen: set[str] = set()
    artifacts: list[dict] = []
    for item in actionable_items:
        rel_path = str(item.get("target_artifact") or "").strip()
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)
        artifacts.append(
            {
                "path": rel_path,
                "baseline_sha256": _artifact_sha256(change_dir / rel_path),
            }
        )
    return artifacts


def _artifact_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _review_dir(base: Path, change: str) -> Path:
    return base / "openspec" / "changes" / change / "review"
