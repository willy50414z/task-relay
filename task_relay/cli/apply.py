from __future__ import annotations

from argparse import Namespace
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

from task_relay import core, worktree
from task_relay.delegation import parse_existing_block
from task_relay.errors import AgentExecutionError
from task_relay.packer import build_packet


def handle_apply(args: Namespace) -> int:
    mode = getattr(args, "mode", "implementation-draft")
    if mode not in ("implementation-draft", "test-draft"):
        raise ValueError("apply mode must be implementation-draft or test-draft")
    if not getattr(args, "task", None):
        raise ValueError("--task is required for trly apply")

    selected_targets = _resolve_apply_targets(args)
    packet = build_packet(
        mode=mode,
        change=args.change,
        task=args.task,
        cwd=args.cwd,
        extra_reads=getattr(args, "extra_reads", None) or None,
        diff_file=getattr(args, "diff_file", None),
        diff_from=getattr(args, "diff_from", None),
        full_change_context=False,
    )
    stdout, branch = core.run_isolated(
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
    diff_summary = summarize_branch_diff(branch=branch, cwd=args.cwd, base=getattr(args, "base", "HEAD"))
    verification = None
    if getattr(args, "verify_cmd", None):
        verification = run_verification(
            branch=branch,
            verify_cmd=args.verify_cmd,
            cwd=args.cwd,
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
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"apply branch: {branch}")
        print("diff summary:")
        print(diff_summary or "(no diff summary)")
        if verification is not None:
            print(f"verification: {'passed' if verification['ok'] else 'failed'}")
            if verification.get("detail"):
                print(verification["detail"])
    return 0 if verification is None or verification["ok"] else 1


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
