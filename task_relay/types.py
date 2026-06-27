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
    # When False, hard quota exhaustion raises immediately instead of waiting out
    # the retry budget — used by fast-fallback to move to the next chain agent.
    wait_on_hard_quota: bool = True
    # Extra environment merged into the agent subprocess (e.g. worktree push-disable).
    extra_env: dict[str, str] | None = None
    # Base ref used when isolated work should branch from something other than HEAD.
    base_ref: str = "HEAD"
    # Branch name of the isolated worktree when applicable.
    branch: str | None = None
    # Stable session id for per-delegation trace records.
    session: str | None = None


@dataclass(frozen=True)
class AgentUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


@dataclass(frozen=True)
class AgentRunResult:
    stdout: str
    target: str
    model: str | None = None
    retries: int = 0
    usage: AgentUsage | None = None

    def __iter__(self):
        yield self.stdout
        yield self.target


PurposeInput = str | Callable[[Path], str]
