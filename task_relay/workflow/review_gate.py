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
from task_relay.review_artifacts import (
    ArtifactValidationError,
    load_json_artifact,
    reviewer_schema_example,
    validate_arbiter_artifact,
    validate_reviewer_artifact,
)
from task_relay.review_config import (
    DEFAULT_GLOBAL_TIMEOUT,
    DEFAULT_REVIEWER_PERSONA,
    ReviewGateConfig,
    ReviewRoleEntry,
    arbiter_personas_for_profile,
    default_arbiter_entries,
    normalize_arbiter_profile,
    normalize_review_profile,
    parse_role_entries,
    reviewer_personas_for_profile,
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
class AbandonedReviewer:
    reviewer_id: str
    entry: ReviewRoleEntry
    path: Path
    errors: tuple[str, ...]
    retry_count: int


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

    reviewer_outcomes = await run_parallel_review(change, config, cwd=str(base), deadline=deadline)
    reviewers = [artifact for artifact in reviewer_outcomes if isinstance(artifact, ReviewArtifact)]
    abandoned = [artifact for artifact in reviewer_outcomes if isinstance(artifact, AbandonedReviewer)]
    if not reviewers:
        raise ReviewArtifactError("all reviewer personas were abandoned after invalid artifact retry")

    reducer = _reduce_reviewers(reviewers, abandoned)
    if reducer["arbiter_invoked"]:
        arbiters = await run_arbiter_chain(change, config, reviewers, abandoned, cwd=str(base), deadline=deadline)
        decision = _aggregate_decision(arbiters)
    else:
        arbiters = []
        decision = "APPROVE"

    result_path = _write_result_json(base, change, decision, config, reviewers, abandoned, arbiters, reducer)
    summary_path = _write_summary(review_dir / "delegation_review.md", decision, config, reviewers, abandoned, arbiters, reducer)
    return ReviewGateResult(
        decision=decision,
        reviewer_artifacts=tuple(reviewers),
        arbiter_artifacts=tuple(arbiters),
        summary_path=summary_path,
        result_path=result_path,
    )



def _review_entries_for_config(config: ReviewGateConfig) -> tuple[ReviewRoleEntry, ...]:
    if config.profile_source == "manual_override":
        return config.reviewers
    selected = config.reviewers[0]
    return tuple(
        ReviewRoleEntry(agent=selected.agent, persona=persona, model=selected.model)
        for persona in reviewer_personas_for_profile(config.review_profile)
    )


def _arbiter_entries_for_config(config: ReviewGateConfig) -> tuple[ReviewRoleEntry, ...]:
    if config.arbiter_source == "manual_override":
        return config.arbiters
    fallback = config.arbiters[0] if config.arbiters else default_arbiter_entries()[0]
    return tuple(
        ReviewRoleEntry(agent=fallback.agent, persona=persona, model=fallback.model)
        for persona in arbiter_personas_for_profile(config.arbiter_profile)
    )


def _all_reviewers_pass(reviewers: list[ReviewArtifact], abandoned: list[AbandonedReviewer] | None = None) -> bool:
    return bool(reviewers) and not (abandoned or []) and all(
        artifact.payload.get("verdict") == "PASS" for artifact in reviewers
    )


def _reduce_reviewers(reviewers: list[ReviewArtifact], abandoned: list[AbandonedReviewer]) -> dict:
    verdicts = [artifact.payload.get("verdict") for artifact in reviewers]
    if _all_reviewers_pass(reviewers, abandoned):
        return {
            "decision": "APPROVE",
            "arbiter_invoked": False,
            "skip_reason": "all reviewer artifacts passed",
            "trigger": "all_pass",
        }
    triggers: list[str] = []
    if abandoned:
        triggers.append("abandoned_reviewers")
    triggers.extend(sorted({str(verdict).lower() for verdict in verdicts if verdict != "PASS"}))
    return {
        "decision": "ARBITRATE",
        "arbiter_invoked": True,
        "skip_reason": None,
        "trigger": ",".join(triggers) or "non_pass_reviewer",
    }


async def run_parallel_review(
    change: str,
    config: ReviewGateConfig,
    *,
    cwd: str,
    deadline: float,
) -> list[ReviewArtifact | AbandonedReviewer]:
    ids = _unique_entry_ids(_review_entries_for_config(config))
    tasks = [
        _run_reviewer_with_retry(change, reviewer_id, entry, cwd=cwd, timeout=_remaining_timeout(deadline))
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
    abandoned: list[AbandonedReviewer],
    *,
    cwd: str,
    deadline: float,
) -> list[ArbiterArtifact]:
    results: list[ArbiterArtifact] = []
    for stage_id, entry in _unique_entry_ids(_arbiter_entries_for_config(config)):
        artifact = await _run_arbiter(
            change,
            stage_id,
            entry,
            reviewers,
            abandoned,
            results,
            cwd=cwd,
            timeout=_remaining_timeout(deadline),
        )
        results.append(artifact)
        if artifact.payload["decision"] == "REJECT":
            break
    return results



async def _run_reviewer_with_retry(
    change: str,
    reviewer_id: str,
    entry: ReviewRoleEntry,
    *,
    cwd: str,
    timeout: float,
) -> ReviewArtifact | AbandonedReviewer:
    output_path = _review_dir(Path(cwd), change) / f"delegation_review_{reviewer_id}.json"
    try:
        return await _run_reviewer(change, reviewer_id, entry, cwd=cwd, timeout=timeout)
    except ReviewArtifactError as exc:
        errors = [str(exc)]
    try:
        return await _run_reviewer_retry(change, reviewer_id, entry, errors, cwd=cwd, timeout=timeout)
    except ReviewArtifactError as exc:
        return AbandonedReviewer(
            reviewer_id=reviewer_id,
            entry=entry,
            path=output_path,
            errors=tuple([*errors, str(exc)]),
            retry_count=1,
        )


async def _run_reviewer_retry(
    change: str,
    reviewer_id: str,
    entry: ReviewRoleEntry,
    errors: list[str],
    *,
    cwd: str,
    timeout: float,
) -> ReviewArtifact:
    output_path = _review_dir(Path(cwd), change) / f"delegation_review_{reviewer_id}.json"
    packet_text = build_packet("review-proposal", change, cwd=cwd, full_change_context=True)
    packet_text = _prepend_reviewer_retry_packet(entry, packet_text, output_path, errors)
    packet_path = _write_temp_packet(packet_text)
    try:
        await _run_subprocess(
            _reviewer_command(entry, packet_path, output_path),
            cwd=cwd,
            timeout=timeout,
            target=entry.agent,
            role=f"{reviewer_id}_retry",
            change=change,
            expected_output=output_path,
        )
        payload = _validate_reviewer_artifact(output_path, entry)
        return ReviewArtifact(reviewer_id=reviewer_id, entry=entry, path=output_path, payload=payload)
    finally:
        packet_path.unlink(missing_ok=True)
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
        payload = _validate_reviewer_artifact(output_path, entry)
        return ReviewArtifact(reviewer_id=reviewer_id, entry=entry, path=output_path, payload=payload)
    finally:
        packet_path.unlink(missing_ok=True)


async def _run_arbiter(
    change: str,
    stage_id: str,
    entry: ReviewRoleEntry,
    reviewers: list[ReviewArtifact],
    abandoned: list[AbandonedReviewer],
    prior_arbiters: list[ArbiterArtifact],
    *,
    cwd: str,
    timeout: float,
) -> ArbiterArtifact:
    output_path = _review_dir(Path(cwd), change) / f"delegation_arbiter_{stage_id}.json"
    packet_text = build_packet("review-arbiter", change, cwd=cwd, full_change_context=True)
    packet_text = _prepend_arbiter_packet(entry, packet_text, reviewers, abandoned, prior_arbiters, output_path)
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
        payload = _validate_arbiter_artifact(output_path, entry)
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
    try:
        normalize_review_profile(config.review_profile)
        normalize_arbiter_profile(config.arbiter_profile)
    except ValueError as exc:
        raise ReviewGateConfigError(str(exc)) from exc
    if config.arbiter_source == "manual_override" and not config.arbiters:
        raise ReviewGateConfigError("manual arbiter override requires at least one arbiter")
    if config.global_timeout <= 0:
        raise ReviewGateConfigError("global timeout must be positive")


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ReviewGateTimeoutError("review gate global timeout expired")
    return remaining


def _validate_reviewer_artifact(path: Path, entry: ReviewRoleEntry | None = None) -> dict:
    try:
        payload = load_json_artifact(path)
        errors = validate_reviewer_artifact(
            payload,
            persona=(entry.persona if entry else DEFAULT_REVIEWER_PERSONA),
        )
    except ArtifactValidationError as exc:
        raise ReviewArtifactError(str(exc)) from exc
    if errors:
        raise ReviewArtifactError(f"reviewer artifact {path} invalid: {'; '.join(errors)}")
    return payload


def _validate_arbiter_artifact(path: Path, entry: ReviewRoleEntry | None = None) -> dict:
    try:
        payload = load_json_artifact(path)
        errors = validate_arbiter_artifact(payload, persona=entry.persona if entry else None)
    except ArtifactValidationError as exc:
        raise ReviewArtifactError(str(exc)) from exc
    if errors:
        raise ReviewArtifactError(f"arbiter artifact {path} invalid: {'; '.join(errors)}")
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
    config: ReviewGateConfig,
    reviewers: list[ReviewArtifact],
    abandoned: list[AbandonedReviewer],
    arbiters: list[ArbiterArtifact],
    reducer: dict,
) -> Path:
    lines = [
        "# Delegation Review Summary",
        "",
        f"- Final decision: {decision}",
        f"- Reviewer profile: {config.review_profile} ({config.profile_source})",
        f"- Arbiter profile: {config.arbiter_profile} ({config.arbiter_source})",
        f"- Reducer decision: {reducer['decision']}",
        f"- Arbiter invoked: {str(reducer['arbiter_invoked']).lower()}",
    ]
    if reducer.get("skip_reason"):
        lines.append(f"- Skip reason: {reducer['skip_reason']}")
    lines.extend(["", "## Reviewer Artifacts"])
    for reviewer in reviewers:
        persona = reviewer.entry.persona or DEFAULT_REVIEWER_PERSONA
        lines.append(f"- `{reviewer.reviewer_id}` ({persona}): `{reviewer.path}` -> {reviewer.payload.get('verdict')}")
    if abandoned:
        lines.extend(["", "## Abandoned Reviewers"])
        for reviewer in abandoned:
            persona = reviewer.entry.persona or DEFAULT_REVIEWER_PERSONA
            lines.append(f"- `{reviewer.reviewer_id}` ({persona}): retry_count={reviewer.retry_count}")
            for error in reviewer.errors:
                lines.append(f"  - {error}")
    lines.extend(["", "## Arbiter Artifacts"])
    if arbiters:
        for arbiter in arbiters:
            persona = arbiter.entry.persona or "/plan-eng-review"
            lines.append(f"- `{arbiter.stage_id}` ({persona}): `{arbiter.path}` -> {arbiter.payload.get('decision')}")
    else:
        lines.append("- skipped")
    lines.extend(["", "## Arbiter Summaries"])
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
    config: ReviewGateConfig,
    reviewers: list[ReviewArtifact],
    abandoned: list[AbandonedReviewer],
    arbiters: list[ArbiterArtifact],
    reducer: dict,
) -> Path:
    path = _review_dir(base, change) / "delegation_review_result.json"
    actionable_items = _collect_actionable_items(arbiters)
    reviewer_entries = _review_entries_for_config(config)
    arbiter_entries = _arbiter_entries_for_config(config) if reducer.get("arbiter_invoked") else ()
    selected_reviewer = reviewer_entries[0] if reviewer_entries else None
    payload = {
        "change": change,
        "decision": decision,
        "apply_allowed": decision != "REJECT",
        "requires_primary_revision": decision == "REVISE",
        "review_profile": config.review_profile,
        "arbiter_profile": config.arbiter_profile,
        "profile_source": config.profile_source,
        "arbiter_source": config.arbiter_source,
        "selected_reviewer_personas": [entry.persona or DEFAULT_REVIEWER_PERSONA for entry in reviewer_entries],
        "selected_arbiter_personas": [entry.persona or "/plan-eng-review" for entry in arbiter_entries],
        "selected_review_agent": {
            "agent": selected_reviewer.agent if selected_reviewer else None,
            "model": selected_reviewer.model if selected_reviewer else None,
        },
        "reducer": reducer,
        "arbiter_invoked": bool(reducer.get("arbiter_invoked")),
        "arbiter_skip_reason": reducer.get("skip_reason"),
        "retry_attempts": [
            {
                "id": artifact.reviewer_id,
                "persona": artifact.entry.persona or DEFAULT_REVIEWER_PERSONA,
                "count": artifact.retry_count,
                "errors": list(artifact.errors),
            }
            for artifact in abandoned
        ],
        "abandoned_reviewers": [
            {
                "id": artifact.reviewer_id,
                "path": str(artifact.path),
                "agent": artifact.entry.agent,
                "persona": artifact.entry.persona or DEFAULT_REVIEWER_PERSONA,
                "model": artifact.entry.model,
                "retry_count": artifact.retry_count,
                "errors": list(artifact.errors),
            }
            for artifact in abandoned
        ],
        "reviewers": [
            {
                "id": artifact.reviewer_id,
                "path": str(artifact.path),
                "reviewer": artifact.payload.get("reviewer"),
                "agent": artifact.entry.agent,
                "persona": artifact.entry.persona or DEFAULT_REVIEWER_PERSONA,
                "model": artifact.entry.model,
                "verdict": artifact.payload.get("verdict"),
            }
            for artifact in reviewers
        ],
        "arbiters": [
            {
                "id": artifact.stage_id,
                "path": str(artifact.path),
                "agent": artifact.entry.agent,
                "persona": artifact.entry.persona or "/plan-eng-review",
                "model": artifact.entry.model,
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



def _reviewer_schema_rules(persona: str) -> str:
    lines = [
        "- JSON object only; no markdown fences or prose.",
        "- Required fields: reviewer, verdict, summary, findings.",
        "- Valid verdict values: PASS, CONCERNS, BLOCKED.",
        "- Every finding requires severity, area, description, recommendation.",
        "- PASS requires an empty findings array.",
        "- CONCERNS and BLOCKED require at least one finding or persona-specific concern field.",
    ]
    if persona == "/devils-advocate":
        lines.append("- /devils-advocate also requires object fields: fatal_flaw, simpler_alternative, reverse_case.")
    return "\n".join(lines)


def _prepend_reviewer_retry_packet(entry: ReviewRoleEntry, packet: str, output_path: Path, errors: list[str]) -> str:
    persona = entry.persona or DEFAULT_REVIEWER_PERSONA
    example = json.dumps(reviewer_schema_example(persona=persona), ensure_ascii=False, indent=2)
    error_lines = "\n".join(f"- {error}" for error in errors)
    return (
        f"Reviewer persona: `{entry.agent}:{persona}`\n"
        f"Expected output path: `{output_path}`\n"
        "Your previous review artifact was invalid and rejected by the review gate.\n"
        "You MUST rewrite the artifact at the expected output path using the required JSON schema.\n\n"
        f"Validation errors:\n{error_lines}\n\n"
        f"Schema rules:\n{_reviewer_schema_rules(persona)}\n\n"
        f"Valid example:\n```json\n{example}\n```\n\n"
        f"{_strict_reviewer_output_contract(entry, output_path)}\n\n"
        f"{_persona_text(persona)}\n\n"
        f"{packet}"
    )
def _prepend_arbiter_packet(
    entry: ReviewRoleEntry,
    packet: str,
    reviewers: list[ReviewArtifact],
    abandoned: list[AbandonedReviewer],
    arbiters: list[ArbiterArtifact],
    output_path: Path,
) -> str:
    reviewer_json = "\n\n".join(
        f"### {artifact.reviewer_id}\n\n```json\n{json.dumps(artifact.payload, ensure_ascii=False, indent=2)}\n```"
        for artifact in reviewers
    )
    abandoned_json = "\n\n".join(
        f"### {artifact.reviewer_id}\n\n```json\n{json.dumps({'persona': artifact.entry.persona or DEFAULT_REVIEWER_PERSONA, 'retry_count': artifact.retry_count, 'errors': list(artifact.errors)}, ensure_ascii=False, indent=2)}\n```"
        for artifact in abandoned
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
    if abandoned_json:
        parts.extend(["", "## Abandoned Reviewer Metadata", abandoned_json])
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
        "/devils-advocate": "reviewer-devils-advocate.md",
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
    review_profile = normalize_review_profile(getattr(args, "review_profile", None))
    arbiter_profile = normalize_arbiter_profile(getattr(args, "arbiter_profile", None))
    timeout = int(getattr(args, "global_timeout", DEFAULT_GLOBAL_TIMEOUT))
    if reviewers:
        return ReviewGateConfig(
            reviewers=reviewers,
            arbiters=arbiters or tuple(default_arbiter_entries()),
            global_timeout=timeout,
            review_profile=review_profile,
            arbiter_profile=arbiter_profile,
            profile_source="manual_override",
            arbiter_source="manual_override" if arbiters else "profile",
        )

    loaded = load_review_gate_config(getattr(args, "cwd", None))
    return ReviewGateConfig(
        reviewers=loaded.reviewers,
        arbiters=arbiters or loaded.arbiters,
        global_timeout=timeout,
        legacy_review_chain=loaded.legacy_review_chain,
        review_profile=review_profile,
        arbiter_profile=arbiter_profile,
        profile_source="explicit" if getattr(args, "review_profile", None) else loaded.profile_source,
        arbiter_source="manual_override" if arbiters else "profile",
    )


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
