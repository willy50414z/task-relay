import logging
import time

from task_relay import agents
from task_relay.errors import AgentExecutionError
from task_relay.prompt import build_prompt
from task_relay.resolver import resolve
from task_relay.types import AgentRunRequest, JobResult, Outcome, PurposeInput
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
) -> str:
    if target is not None and targets is not None:
        raise ValueError("Provide either 'target' or 'targets', not both.")
    selected = targets if targets is not None else ([target] if target is not None else [])
    if not selected:
        raise ValueError("run() requires 'target' or 'targets'.")
    if not prompt.strip():
        raise ValueError("prompt must not be empty.")
    return _run_with_fallback(
        selected,
        AgentRunRequest(prompt=prompt, cwd=cwd, model=model, effort=effort, timeout=timeout),
    )[0]


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
        stdout, winning_target = _run_with_fallback(
            selected,
            AgentRunRequest(
                prompt=prompt,
                cwd=str(workspace),
                model=model,
                effort=effort,
                timeout=timeout,
            ),
        )
        matched, result = resolve(
            workspace=workspace,
            outcomes=outcomes,
            job_id=job_id,
            target=winning_target,
            duration_seconds=time.monotonic() - start,
            stdout=stdout,
        )
    except Exception as exc:
        cleanup_workspace(workspace)
        if on_exception is not None:
            on_exception(exc)
            return
        raise

    try:
        matched.callback(result)
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
        stdout, winning_target = _run_with_fallback(
            targets,
            AgentRunRequest(prompt=prompt, cwd=str(workspace), model=model, effort=effort, timeout=timeout),
        )
        _, result = resolve(
            workspace=workspace,
            outcomes=outcomes,
            job_id=job_id,
            target=winning_target,
            duration_seconds=time.monotonic() - start,
            stdout=stdout,
        )
        return result
    finally:
        cleanup_workspace(workspace)


def _run_with_fallback(
    targets: list[str],
    request: AgentRunRequest,
) -> tuple[str, str]:
    last_exc: AgentExecutionError | None = None
    for name in targets:
        try:
            result = agents.resolve(name).run(request)
            return result.stdout, result.target
        except AgentExecutionError as exc:
            logger.warning("fallback: %s failed, trying next. error: %s", name, exc)
            last_exc = exc
    if last_exc is None:
        raise ValueError("targets must not be empty")
    raise last_exc
