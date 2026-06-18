import logging
from pathlib import Path

from task_relay.errors import OutcomeResolutionError
from task_relay.types import JobResult, Outcome, effective_status

logger = logging.getLogger(__name__)


def resolve(
    workspace: Path,
    outcomes: list[Outcome],
    job_id: str,
    target: str,
    duration_seconds: float,
    stdout: str,
) -> tuple[Outcome, JobResult]:
    status_files = sorted(workspace.glob("status_*"))
    if len(status_files) > 1:
        logger.warning(
            "Multiple status files found: %s. Using %s.",
            [path.name for path in status_files],
            status_files[0].name,
        )

    if not status_files:
        matched = next((o for i, o in enumerate(outcomes) if effective_status(o, i) == "error"), None)
        if matched is None:
            raise OutcomeResolutionError("No status file created by agent and no 'error' outcome defined.")
        status_name = "error"
    else:
        status_name = status_files[0].stem[len("status_") :]
        matched = next((o for i, o in enumerate(outcomes) if effective_status(o, i) == status_name), None)
        if matched is None:
            raise OutcomeResolutionError(
                f"Status file 'status_{status_name}' does not match any defined outcome."
            )

    declared = matched.output_files or []
    missing = [name for name in declared if not (workspace / name).exists()]
    if missing:
        raise OutcomeResolutionError(
            f"Outcome '{status_name}' declared output_files {missing} but agent did not create them."
        )

    files = {name: (workspace / name).read_bytes() for name in declared}
    return matched, JobResult(
        job_id=job_id,
        status=status_name,
        target=target,
        duration_seconds=duration_seconds,
        files=files,
        stdout=stdout,
    )
