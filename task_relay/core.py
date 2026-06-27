import logging
import os
import time
from dataclasses import replace
from pathlib import Path

from task_relay import agents
from task_relay.errors import AgentExecutionError, AgentQuotaError, DelegationOutputError, DirtyWorkingTreeError
from task_relay.prompt import build_prompt
from task_relay.resolver import resolve
from task_relay.trace import append_trace_record, extract_prompt_context, new_session_id
from task_relay.types import AgentRunRequest, AgentRunResult, JobResult, Outcome, PurposeInput
from task_relay.workspace import cleanup_workspace, create_workspace

logger = logging.getLogger(__name__)


def run(
    target: str | None = None,
    prompt: str = "",
    *,
    targets: list[str] | None = None,
    model: str | None = None,
    effort: str | None = None,
    timeout: float = 1800,
    cwd: str | None = None,
    expect_output: list[str] | None = None,
) -> str:
    if target is not None and targets is not None:
        raise ValueError("Provide either 'target' or 'targets', not both.")
    selected = targets if targets is not None else ([target] if target is not None else [])
    if not selected:
        raise ValueError("run() requires 'target' or 'targets'.")
    if not prompt.strip():
        raise ValueError("prompt must not be empty.")
    request = AgentRunRequest(
        prompt=prompt,
        cwd=cwd,
        model=model,
        effort=effort,
        timeout=timeout,
        session=new_session_id(),
    )
    result = _normalize_agent_run_result(
        _run_with_fallback(selected, request),
        target=selected[0],
        request=request,
    )
    if expect_output:
        verify_expected_output(expect_output, cwd=cwd)
    return result.stdout


def run_isolated(
    target: str | None = None,
    prompt: str = "",
    *,
    targets: list[str] | None = None,
    model: str | None = None,
    effort: str | None = None,
    timeout: float = 1800,
    cwd: str | None = None,
    allow_dirty: bool = False,
    base: str = "HEAD",
) -> tuple[str, str]:
    """Run a delegate inside an ephemeral worktree with push disabled.

    The delegate's writes land on a throwaway branch instead of the real working tree,
    and `git push` is neutralized for the subprocess. Returns `(stdout, branch)`; the
    primary integrates by diffing/merging the branch. The worktree directory is removed
    after the run (the branch and its commit persist) unless `TASK_RELAY_KEEP_IO=1`.
    """
    from task_relay import worktree as wt

    selected = targets if targets is not None else ([target] if target is not None else [])
    if not selected:
        raise ValueError("run_isolated() requires 'target' or 'targets'.")
    if not prompt.strip():
        raise ValueError("prompt must not be empty.")

    repo_root = wt.git_repo_root(cwd)
    if repo_root is None:
        raise AgentExecutionError("run_isolated requires a git repository (none found at cwd).")
    if not allow_dirty and wt.is_dirty(repo_root):
        raise DirtyWorkingTreeError(
            "isolated delegation requires a clean working tree; commit or stash changes and re-run, "
            "or pass --allow-dirty to delegate from clean HEAD anyway."
        )

    _, worktree_path, branch = wt.create_worktree(repo_root, base_dir=str(repo_root), base=base)
    try:
        request = AgentRunRequest(
            prompt=prompt,
            cwd=str(worktree_path),
            model=model,
            effort=effort,
            timeout=timeout,
            extra_env=wt.push_disable_env(repo_root),
            base_ref=base,
            branch=branch,
            session=new_session_id(),
        )
        result = _normalize_agent_run_result(
            _run_with_fallback(selected, request),
            target=selected[0],
            request=request,
        )
        had_changes = wt.commit_worktree(worktree_path, branch)
    finally:
        wt.remove_worktree(repo_root, worktree_path, branch, keep_branch=True)

    if not had_changes:
        raise DelegationOutputError(
            f"delegation produced no changes (branch {branch} is empty)."
        )
    return result.stdout, branch


def verify_expected_output(expected: list[str], *, cwd: str | None = None) -> None:
    """Raise DelegationOutputError if any declared artifact is missing or empty.

    Backstops the review delegation path, which has no tasks.md checkbox to catch a
    delegate that claims success in stdout without actually writing the artifact.
    """
    base = Path(cwd) if cwd else Path.cwd()
    for name in expected:
        path = Path(name)
        if not path.is_absolute():
            path = base / path
        if not path.exists():
            raise DelegationOutputError(f"expected output '{name}' was not created at {path}")
        try:
            non_empty = bool(path.read_text(encoding="utf-8", errors="replace").strip())
        except OSError as exc:
            raise DelegationOutputError(f"expected output '{name}' could not be read: {exc}") from exc
        if not non_empty:
            raise DelegationOutputError(f"expected output '{name}' is empty at {path}")


def evaluate(
    target: str | None,
    purpose: PurposeInput,
    outcomes: list[Outcome],
    *,
    targets: list[str] | None = None,
    on_exception=None,
    model: str | None = None,
    effort: str | None = None,
    timeout: float = 1800,
    cwd: str | None = None,
) -> None:
    if target is not None and targets is not None:
        raise ValueError("Provide either 'target' or 'targets', not both.")
    selected = targets if targets is not None else ([target] if target is not None else [])
    if not selected:
        raise ValueError("evaluate() requires 'target' or 'targets'.")
    if not outcomes:
        raise ValueError("outcomes must not be empty.")

    job_id, workspace = create_workspace(cwd)
    purpose_text = purpose(workspace) if callable(purpose) else purpose
    prompt = build_prompt(purpose_text, outcomes, workspace=workspace)
    start = time.monotonic()
    try:
        result = _run_with_fallback(
            selected,
            AgentRunRequest(
                prompt=prompt,
                cwd=str(workspace),
                model=model,
                effort=effort,
                timeout=timeout,
                session=new_session_id(),
            ),
        )
        matched, resolved = resolve(
            workspace=workspace,
            outcomes=outcomes,
            job_id=job_id,
            target=result.target,
            duration_seconds=time.monotonic() - start,
            stdout=result.stdout,
        )
    except Exception as exc:
        cleanup_workspace(workspace)
        if on_exception is not None:
            on_exception(exc)
            return
        raise

    try:
        matched.callback(resolved)
    finally:
        cleanup_workspace(workspace)


def evaluate_result(
    targets: list[str],
    purpose: str,
    outcomes: list[Outcome],
    *,
    model: str | None = None,
    effort: str | None = None,
    timeout: float = 1800,
    cwd: str | None = None,
) -> JobResult:
    if not targets:
        raise ValueError("evaluate requires at least one target")
    job_id, workspace = create_workspace(cwd)
    prompt = build_prompt(purpose, outcomes, workspace=workspace)
    start = time.monotonic()
    try:
        result = _run_with_fallback(
            targets,
            AgentRunRequest(
                prompt=prompt,
                cwd=str(workspace),
                model=model,
                effort=effort,
                timeout=timeout,
                session=new_session_id(),
            ),
        )
        _, resolved = resolve(
            workspace=workspace,
            outcomes=outcomes,
            job_id=job_id,
            target=result.target,
            duration_seconds=time.monotonic() - start,
            stdout=result.stdout,
        )
        return resolved
    finally:
        cleanup_workspace(workspace)


def _fast_fallback_enabled() -> bool:
    return os.getenv("LLM_FAST_FALLBACK", "0").strip().lower() in ("1", "true", "yes")


def _log_level() -> int:
    raw = os.getenv("LLM_LOG_LEVEL", "WARNING").strip().upper()
    return getattr(logging, raw, logging.WARNING)


def _normalize_agent_run_result(
    result,
    *,
    target: str | None = None,
    request: AgentRunRequest | None = None,
) -> AgentRunResult:
    if isinstance(result, AgentRunResult):
        return result
    if isinstance(result, tuple) and len(result) >= 2:
        stdout, resolved_target = result[0], result[1]
        return AgentRunResult(
            stdout=str(stdout),
            target=str(resolved_target),
            model=request.model if request is not None else None,
        )

    stdout = getattr(result, "stdout", result)
    resolved_target = getattr(result, "target", target)
    if resolved_target is None:
        raise AgentExecutionError("agent result did not include a target")
    return AgentRunResult(
        stdout="" if stdout is None else str(stdout),
        target=str(resolved_target),
        model=getattr(result, "model", None) or (request.model if request is not None else None),
        retries=int(getattr(result, "retries", 0) or 0),
        usage=getattr(result, "usage", None),
    )


def _run_with_fallback(
    targets: list[str],
    request: AgentRunRequest,
) -> AgentRunResult:
    # Fast fallback (opt-in, default off): on hard quota exhaustion, move to the
    # next chain agent instead of waiting out the retry budget. The last agent has
    # nowhere to fall back to, so it always waits within the bounded budget.
    fast_fallback = _fast_fallback_enabled()
    last_exc: AgentExecutionError | None = None
    fallback_chain: list[str] = []
    prompt_context = extract_prompt_context(request.prompt)
    session = request.session or new_session_id()
    for index, name in enumerate(targets):
        is_last = index == len(targets) - 1
        wait_on_hard = True if is_last else not fast_fallback
        attempt = replace(request, wait_on_hard_quota=wait_on_hard, session=session)
        level = _log_level()
        logger.log(level, "delegation start: target=%s role=%s branch=%s", name, prompt_context.get("role"), request.branch)
        start = time.monotonic()
        try:
            raw_result = agents.resolve(name).run(attempt)
            result = _normalize_agent_run_result(raw_result, target=name, request=attempt)
            duration = time.monotonic() - start
            logger.log(level, "delegation end: target=%s outcome=success duration=%.2fs retries=%d", name, duration, result.retries)
            _write_trace(
                session=session,
                request=request,
                prompt_context=prompt_context,
                result=result,
                duration=duration,
                outcome="success",
                fallback_from=",".join(fallback_chain) or None,
                target=name,
            )
            return result
        except AgentQuotaError as exc:
            duration = time.monotonic() - start
            logger.log(level, "delegation end: target=%s outcome=quota duration=%.2fs", name, duration)
            _write_trace(
                session=session,
                request=request,
                prompt_context=prompt_context,
                result=None,
                duration=duration,
                outcome="quota",
                fallback_from=",".join(fallback_chain) or None,
                target=name,
            )
            logger.warning("fallback: %s failed, trying next. error: %s", name, exc)
            fallback_chain.append(name)
            last_exc = exc
        except AgentExecutionError as exc:
            duration = time.monotonic() - start
            logger.log(level, "delegation end: target=%s outcome=error duration=%.2fs", name, duration)
            _write_trace(
                session=session,
                request=request,
                prompt_context=prompt_context,
                result=None,
                duration=duration,
                outcome="error",
                fallback_from=",".join(fallback_chain) or None,
                target=name,
            )
            logger.warning("fallback: %s failed, trying next. error: %s", name, exc)
            fallback_chain.append(name)
            last_exc = exc
    if last_exc is None:
        raise ValueError("targets must not be empty")
    raise last_exc


def _write_trace(
    *,
    session: str,
    request: AgentRunRequest,
    prompt_context: dict[str, str | None],
    result: AgentRunResult | None,
    duration: float,
    outcome: str,
    fallback_from: str | None,
    target: str,
) -> None:
    usage = result.usage if result is not None else None
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "session": session,
        "target": target,
        "model": result.model if result is not None else request.model,
        "role": prompt_context.get("role"),
        "change": prompt_context.get("change"),
        "task": prompt_context.get("task"),
        "duration_s": round(duration, 6),
        "outcome": outcome,
        "fallback_from": fallback_from,
        "branch": request.branch,
        "tokens_in": usage.input_tokens if usage else None,
        "tokens_out": usage.output_tokens if usage else None,
        "cost_usd": usage.cost_usd if usage else None,
        "retries": result.retries if result is not None else 0,
    }
    append_trace_record(record, cwd=request.cwd)
