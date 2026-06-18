from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Outcome:
    description: str
    callback: Callable[["JobResult"], None]
    status: str | None = None
    output_files: list[str] | None = None


def effective_status(outcome: Outcome, index: int) -> str:
    return outcome.status if outcome.status is not None else str(index)


@dataclass(frozen=True)
class JobResult:
    job_id: str
    status: str
    target: str
    duration_seconds: float
    files: dict[str, bytes]
    stdout: str


@dataclass(frozen=True)
class TargetStatus:
    ok: bool
    reason: str | None = None


@dataclass(frozen=True)
class AgentRunRequest:
    prompt: str
    cwd: str | None = None
    model: str | None = None
    effort: str | None = None
    timeout: float | None = 1800
    encoding: str = "utf-8"


@dataclass(frozen=True)
class AgentRunResult:
    stdout: str
    target: str


PurposeInput = str | Callable[[Path], str]
