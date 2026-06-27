"""Ephemeral git worktree isolation for delegated agents.

Threat model: the delegate is unreliable, not malicious. The goal is to keep its
normal writes out of the real working tree and to hard-block `git push` to real
remotes — not full OS-level containment. A worktree shares the repo's `.git`
(objects, refs, remotes), so push is neutralized via a process-local
`GIT_CONFIG_*` env override rather than by mutating `.git/config`.
"""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from pathlib import Path

from task_relay.errors import AgentExecutionError

KEEP_IO_ENV = "TASK_RELAY_KEEP_IO"
_DEAD_PUSHURL = "disabled-by-task-relay://no-push"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise AgentExecutionError(f"git {' '.join(args)} failed: {detail[:300]}")
    return result


def git_repo_root(cwd: str | None) -> Path | None:
    base = cwd or os.getcwd()
    try:
        result = subprocess.run(
            ["git", "-C", base, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    top = result.stdout.strip()
    return Path(top) if top else None


def push_disable_env(repo_root: Path) -> dict[str, str]:
    """Env vars that override every remote's pushurl to a dead value for one process."""
    remotes = _git(repo_root, "remote").stdout.split()
    env: dict[str, str] = {}
    for index, remote in enumerate(remotes):
        env[f"GIT_CONFIG_KEY_{index}"] = f"remote.{remote}.pushurl"
        env[f"GIT_CONFIG_VALUE_{index}"] = _DEAD_PUSHURL
    if remotes:
        env["GIT_CONFIG_COUNT"] = str(len(remotes))
    return env


def is_dirty(repo_root: Path) -> bool:
    """Return True when the main working tree has staged, unstaged, or untracked changes."""
    return bool(_git(repo_root, "status", "--porcelain").stdout.strip())


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip("/"))
    slug = slug.strip(".-")
    return slug or uuid.uuid4().hex[:8]


def create_worktree(
    repo_root: Path,
    base_dir: str | None = None,
    *,
    base: str = "HEAD",
    branch_name: str | None = None,
    branch_prefix: str = "tr",
) -> tuple[str, Path, str]:
    job_id = uuid.uuid4().hex[:8]
    branch = branch_name or f"{branch_prefix}/{job_id}"
    base_path = Path(base_dir) if base_dir else repo_root
    worktree_id = _slug(branch_name or job_id)
    worktree = base_path / ".task_relay" / "worktrees" / worktree_id
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "worktree", "add", "-b", branch, str(worktree), base)
    return job_id, worktree, branch


def create_change_worktree(
    repo_root: Path,
    change_name: str,
    base_dir: str | None = None,
    *,
    base: str = "HEAD",
) -> tuple[str, Path, str]:
    return create_worktree(
        repo_root,
        base_dir=base_dir,
        base=base,
        branch_name=f"chg/{change_name}",
        branch_prefix="chg",
    )


def commit_worktree(worktree: Path, branch: str) -> bool:
    """Commit any delegate changes to the throwaway branch. Returns True if there were changes."""
    _git(worktree, "add", "-A")
    status = _git(worktree, "status", "--porcelain").stdout
    if not status.strip():
        return False
    _git(
        worktree,
        "-c",
        "user.email=delegate@task-relay.local",
        "-c",
        "user.name=task-relay delegate",
        "commit",
        "-q",
        "-m",
        f"delegated work {branch}",
    )
    return True


def merge_branch(worktree: Path, branch: str) -> None:
    _git(worktree, "merge", "--no-ff", "--no-edit", branch)


def remove_worktree(repo_root: Path, worktree: Path, branch: str, *, keep_branch: bool = True) -> None:
    if os.getenv(KEEP_IO_ENV, "0").strip() == "1":
        return
    try:
        _git(repo_root, "worktree", "remove", "--force", str(worktree))
    except AgentExecutionError:
        pass
    if not keep_branch:
        try:
            _git(repo_root, "branch", "-D", branch)
        except AgentExecutionError:
            pass
    current = worktree.parent
    while current != repo_root:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
