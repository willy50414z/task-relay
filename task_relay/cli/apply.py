from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess

from task_relay import core, worktree
from task_relay.delegation import parse_existing_block
from task_relay.errors import AgentExecutionError
from task_relay.packer import plan_packet


DEFAULT_CONVENTIONS_READ = ".task_relay/conventions.md"


@dataclass
class ApplyObservation:
    item: str
    expected: str
    status: str
    detail: str = ""


def handle_apply(args: Namespace) -> int:
    mode = getattr(args, "mode", "implementation-draft")
    observations: list[ApplyObservation] = []
    packet_report: dict[str, object] | None = None
    selected_targets: list[str] = []
    stdout = ""
    branch: str | None = None
    delegate_result: core.IsolatedRunResult | None = None
    diff_summary = ""
    verification = None
    debug_summary_path: Path | None = None

    if mode not in ("implementation-draft", "test-draft"):
        observations.append(ApplyObservation("input", "apply mode is implementation-draft or test-draft", "fail", mode))
        _write_apply_debug_summary(args, mode, observations, None, "", None, None, "", None)
        raise ValueError("apply mode must be implementation-draft or test-draft")
    if not getattr(args, "task", None):
        observations.append(ApplyObservation("input", "--task is provided", "fail", "missing task id"))
        _write_apply_debug_summary(args, mode, observations, None, "", None, None, "", None)
        raise ValueError("--task is required for trly apply")
    observations.append(ApplyObservation("input", "valid mode and task id", "ok", f"mode={mode}, task={args.task}"))

    try:
        selected_targets = _resolve_apply_targets(args)
        observations.append(
            ApplyObservation(
                "apply target resolution",
                "at least one delegate target is available",
                "ok",
                ", ".join(selected_targets),
            )
        )

        explicit_reads = list(getattr(args, "extra_reads", None) or [])
        extra_reads = default_apply_reads(args.cwd, explicit_reads)
        if DEFAULT_CONVENTIONS_READ in extra_reads and DEFAULT_CONVENTIONS_READ not in explicit_reads:
            observations.append(
                ApplyObservation(
                    "repo conventions context",
                    "repo conventions are packed when available",
                    "ok",
                    DEFAULT_CONVENTIONS_READ,
                )
            )

        plan = plan_packet(
            mode=mode,
            change=args.change,
            task=args.task,
            cwd=args.cwd,
            extra_reads=extra_reads or None,
            diff_file=getattr(args, "diff_file", None),
            diff_from=getattr(args, "diff_from", None),
            full_change_context=False,
        )
        packet_report = plan.to_report(
            mode=mode,
            change=args.change,
            task=args.task,
            full_change_context=False,
            cache_layout_enabled=getattr(args, "cache_layout", False),
        )
        observations.append(_context_packer_observation(packet_report))
        packet = plan.render(cache_layout=getattr(args, "cache_layout", False))

        delegate_result = core.run_isolated_detailed(
            target=args.target,
            targets=selected_targets if args.target is None else None,
            prompt=packet,
            model=getattr(args, "model", None),
            effort=getattr(args, "effort", None),
            timeout=getattr(args, "timeout", 1800),
            cwd=args.cwd,
            allow_dirty=getattr(args, "allow_dirty", False),
            base=getattr(args, "base", "HEAD"),
        )
        stdout = delegate_result.stdout
        branch = delegate_result.branch
        observations.append(
            ApplyObservation(
                "delegate isolated execution",
                "delegate creates a non-empty isolated branch",
                "ok",
                (
                    f"target={delegate_result.target}, branch={branch}, "
                    f"job_id={delegate_result.job_id or '-'}, "
                    f"log={delegate_result.log_path or '-'}, "
                    f"retries={delegate_result.retries}, stdout_chars={len(stdout)}"
                ),
            )
        )

        diff_summary = summarize_branch_diff(branch=branch, cwd=args.cwd, base=getattr(args, "base", "HEAD"))
        observations.append(
            ApplyObservation(
                "branch diff summary",
                "branch diff is available for primary review",
                "ok" if diff_summary else "warn",
                diff_summary or "git diff --stat returned no output",
            )
        )

        if getattr(args, "verify_cmd", None):
            verification = run_verification(
                branch=branch,
                verify_cmd=args.verify_cmd,
                cwd=args.cwd,
            )
            observations.append(
                ApplyObservation(
                    "verification",
                    "verification command exits 0",
                    "ok" if verification["ok"] else "fail",
                    f"returncode={verification['returncode']}, command={args.verify_cmd}",
                )
            )
        else:
            observations.append(
                ApplyObservation(
                    "verification",
                    "verification command is available when requested by workflow",
                    "skipped",
                    "no --verify-cmd provided",
                )
            )
    except Exception as exc:
        observations.append(ApplyObservation("apply completion", "all apply stages finish without exception", "fail", str(exc)))
        _write_apply_debug_summary(args, mode, observations, packet_report, stdout, branch, delegate_result, diff_summary, verification)
        raise

    debug_summary_path = _write_apply_debug_summary(
        args,
        mode,
        observations,
        packet_report,
        stdout,
        branch,
        delegate_result,
        diff_summary,
        verification,
    )

    if getattr(args, "json", False):
        payload = {
            "change": args.change,
            "task": args.task,
            "mode": mode,
            "targets": selected_targets if args.target is None else [args.target],
            "branch": branch,
            "stdout": stdout,
            "diff_summary": diff_summary,
            "verification": verification,
            "debug_summary_path": str(debug_summary_path),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"apply branch: {branch}")
        print("diff summary:")
        print(diff_summary or "(no diff summary)")
        print(f"debug summary: {debug_summary_path}")
        if verification is not None:
            print(f"verification: {'passed' if verification['ok'] else 'failed'}")
            if verification.get("detail"):
                print(verification["detail"])
    return 0 if verification is None or verification["ok"] else 1


def default_apply_reads(cwd: str | None, explicit_reads: list[str] | None) -> list[str]:
    reads = list(explicit_reads or [])
    base = worktree.git_repo_root(cwd) or (Path(cwd).resolve() if cwd else Path.cwd())
    conventions = base / DEFAULT_CONVENTIONS_READ
    if conventions.is_file() and not _has_conventions_read(reads, base):
        reads.append(DEFAULT_CONVENTIONS_READ)
    return reads


def _has_conventions_read(reads: list[str], base: Path) -> bool:
    expected = (base / DEFAULT_CONVENTIONS_READ).resolve()
    for read in reads:
        if read == DEFAULT_CONVENTIONS_READ:
            return True
        path = Path(read)
        candidate = path if path.is_absolute() else base / path
        try:
            if candidate.resolve() == expected:
                return True
        except OSError:
            continue
    return False


def summarize_branch_diff(*, branch: str, cwd: str | None, base: str) -> str:
    repo_root = worktree.git_repo_root(cwd)
    if repo_root is None:
        raise AgentExecutionError("apply summary requires a git repository")
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--stat", f"{base}...{branch}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise AgentExecutionError(f"git diff summary failed: {detail[:300]}")
    return result.stdout.strip()


def run_verification(*, branch: str, verify_cmd: str, cwd: str | None) -> dict[str, str | bool | int]:
    repo_root = worktree.git_repo_root(cwd)
    if repo_root is None:
        raise AgentExecutionError("verification requires a git repository")
    _, verify_wt, verify_branch = worktree.create_worktree(
        repo_root,
        base_dir=str(repo_root),
        base=branch,
        branch_name=f"verify/{branch.replace('/', '-')}",
        branch_prefix="verify",
    )
    try:
        result = subprocess.run(
            shlex.split(verify_cmd),
            cwd=str(verify_wt),
            capture_output=True,
            text=True,
        )
    finally:
        worktree.remove_worktree(repo_root, verify_wt, verify_branch, keep_branch=False)
    detail = (result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr).strip()
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "detail": detail[:2000],
    }


def _resolve_apply_targets(args: Namespace) -> list[str]:
    if getattr(args, "targets", None):
        return list(args.targets)
    if getattr(args, "target", None):
        return [args.target]

    base = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = base / name
        parsed = parse_existing_block(path)
        if not parsed:
            continue
        apply_chain = parsed.get("apply_chain") or []
        if apply_chain:
            return [agent for agent, _model in apply_chain]
    raise ValueError("no apply chain configured; pass --target/--targets or run `trly install` first")


def _context_packer_observation(report: dict[str, object]) -> ApplyObservation:
    gaps = report.get("repo_context_gap") or []
    missing = report.get("missing_signals") or []
    trimmed = report.get("trimmed_sections") or []
    budget_status = str(report.get("budget_status") or "unknown")
    status = "ok"
    if budget_status == "trimmed" or gaps or missing or trimmed:
        status = "warn"
    if budget_status == "violation":
        status = "fail"
    detail = (
        f"selection_mode={report.get('selection_mode')}, "
        f"bytes={report.get('byte_estimate')}, "
        f"budget_status={budget_status}, "
        f"sections={len(report.get('sections') or [])}, "
        f"repo_refs={len(report.get('repo_references') or [])}, "
        f"missing_signals={len(missing)}, "
        f"repo_context_gap={len(gaps)}, "
        f"trimmed_sections={len(trimmed)}"
    )
    return ApplyObservation(
        "context-packer",
        "packet context is bounded, relevant, and within budget",
        status,
        detail,
    )


def _write_apply_debug_summary(
    args: Namespace,
    mode: str,
    observations: list[ApplyObservation],
    packet_report: dict[str, object] | None,
    stdout: str,
    branch: str | None,
    delegate_result: core.IsolatedRunResult | None,
    diff_summary: str,
    verification: dict[str, str | bool | int] | None,
) -> Path:
    path = _apply_debug_summary_path(args)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _render_apply_debug_summary(
            args=args,
            mode=mode,
            observations=observations,
            packet_report=packet_report,
            stdout=stdout,
            branch=branch,
            delegate_result=delegate_result,
            diff_summary=diff_summary,
            verification=verification,
        ),
        encoding="utf-8",
    )
    return path


def _apply_debug_summary_path(args: Namespace) -> Path:
    base = Path(args.cwd).resolve() if getattr(args, "cwd", None) else Path.cwd().resolve()
    task_id = _safe_slug(str(getattr(args, "task", None) or "unknown-task"))
    return base / "openspec" / "changes" / args.change / "apply" / f"task-{task_id}-debug-summary.md"


def _render_apply_debug_summary(
    *,
    args: Namespace,
    mode: str,
    observations: list[ApplyObservation],
    packet_report: dict[str, object] | None,
    stdout: str,
    branch: str | None,
    delegate_result: core.IsolatedRunResult | None,
    diff_summary: str,
    verification: dict[str, str | bool | int] | None,
) -> str:
    status_counts: dict[str, int] = {}
    for observation in observations:
        status_counts[observation.status] = status_counts.get(observation.status, 0) + 1
    overall = "fail" if status_counts.get("fail") else "warn" if status_counts.get("warn") else "ok"

    lines = [
        "# Apply Debug Summary",
        "",
        "## Overview",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- change: `{args.change}`",
        f"- task: `{getattr(args, 'task', None)}`",
        f"- mode: `{mode}`",
        f"- base: `{getattr(args, 'base', 'HEAD')}`",
        f"- target_override: `{getattr(args, 'target', None)}`",
        f"- branch: `{branch}`",
        f"- delegate_target: `{delegate_result.target if delegate_result else None}`",
        f"- delegate_job_id: `{delegate_result.job_id if delegate_result else None}`",
        f"- delegate_log_path: `{delegate_result.log_path if delegate_result else None}`",
        f"- overall_status: `{overall}`",
        "",
        "## Observation Checklist",
        "",
        "| Item | Expected | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for observation in observations:
        lines.append(
            "| "
            + " | ".join(
                _md_cell(value)
                for value in (
                    observation.item,
                    observation.expected,
                    observation.status,
                    observation.detail,
                )
            )
            + " |"
        )

    recommendations = _apply_debug_recommendations(observations, packet_report, verification)
    if recommendations:
        lines.extend(["", "## Tool Optimization Notes", ""])
        lines.extend(f"- {item}" for item in recommendations)

    if packet_report is not None:
        lines.extend([
            "",
            "## Context Packer Report",
            "",
            "```json",
            json.dumps(packet_report, ensure_ascii=False, indent=2),
            "```",
        ])

    lines.extend([
        "",
        "## Delegate Output",
        "",
        f"- target: `{delegate_result.target if delegate_result else None}`",
        f"- model: `{delegate_result.model if delegate_result else None}`",
        f"- retries: `{delegate_result.retries if delegate_result else None}`",
        f"- job_id: `{delegate_result.job_id if delegate_result else None}`",
        f"- log_path: `{delegate_result.log_path if delegate_result else None}`",
        f"- tokens_in: `{delegate_result.tokens_in if delegate_result else None}`",
        f"- tokens_out: `{delegate_result.tokens_out if delegate_result else None}`",
        f"- cost_usd: `{delegate_result.cost_usd if delegate_result else None}`",
        f"- stdout_chars: {len(stdout)}",
        "",
        "```text",
        _truncate(stdout, 4000),
        "```",
        "",
        "## Diff Summary",
        "",
        "```text",
        diff_summary or "(empty)",
        "```",
    ])

    if verification is not None:
        lines.extend([
            "",
            "## Verification",
            "",
            "```json",
            json.dumps(verification, ensure_ascii=False, indent=2),
            "```",
        ])

    return "\n".join(lines).rstrip() + "\n"


def _apply_debug_recommendations(
    observations: list[ApplyObservation],
    packet_report: dict[str, object] | None,
    verification: dict[str, str | bool | int] | None,
) -> list[str]:
    notes: list[str] = []
    for observation in observations:
        if observation.status == "fail":
            notes.append(f"{observation.item}: failed; inspect the detail and upstream logs before accepting apply output.")
        elif observation.status == "warn":
            notes.append(f"{observation.item}: warning; verify whether the behavior is expected for this task.")

    if packet_report is not None:
        if packet_report.get("repo_context_gap"):
            notes.append("context-packer: add or fix repo references so selected context resolves cleanly.")
        if packet_report.get("missing_signals"):
            notes.append("context-packer: enrich task/spec/design signals for more deterministic context selection.")
        if packet_report.get("trimmed_sections"):
            notes.append("context-packer: review budget settings or scoped inputs because some sections were trimmed.")

    if verification is None:
        notes.append("verification: no command was provided; add --verify-cmd when apply output should be automatically checked.")
    elif not verification.get("ok"):
        notes.append("verification: command failed; keep branch unintegrated until the failure is resolved.")

    return notes


def _md_cell(value: object) -> str:
    text = str(value).replace("\n", "<br>").replace("|", "\\|")
    return text


def _safe_slug(value: str) -> str:
    chars = [ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value.strip()]
    slug = "".join(chars).strip("-")
    return slug or "unknown"


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... truncated {len(value) - limit} chars ..."
