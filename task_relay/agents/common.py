import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass

from task_relay import jobs
from task_relay.errors import AgentExecutionError, AgentQuotaError, AgentTimeoutError
from task_relay.types import AgentUsage, TargetStatus

logger = logging.getLogger(__name__)

# Transient throttling: a short wait usually clears it. The agent's request was
# rejected, so retrying the same agent is the right move.
TRANSIENT_QUOTA_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\b429\b",
        r"rate.?limit",
        r"too many requests",
        r"overloaded",
        r"\b503\b",
        r"service unavailable",
        r"temporarily unavailable",
        r"retry.?after",
    ]
]

# Hard exhaustion: credits/quota are gone. Waiting rarely helps quickly; bound
# the wait and (optionally) fall back to another agent instead of hanging.
HARD_QUOTA_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"exceeded your monthly token limit",
        r"exceeded your current quota",
        r"insufficient.quota",
        r"quota.?exceeded",
        r"billing hard limit",
        r"credit balance is too low",
        r"out of credits",
        r"payment required",
    ]
]

_RETRY_AFTER_RE = re.compile(r'retry.?after["\'\s:=]+(\d+(?:\.\d+)?)', re.IGNORECASE)


@dataclass(frozen=True)
class SubprocessResult:
    stdout: str
    retries: int
    usage: AgentUsage | None = None
    job_id: str | None = None
    log_path: str | None = None

    def __str__(self) -> str:
        return self.stdout

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.stdout == other
        if isinstance(other, SubprocessResult):
            return (
                self.stdout == other.stdout
                and self.retries == other.retries
                and self.usage == other.usage
                and self.job_id == other.job_id
                and self.log_path == other.log_path
            )
        return NotImplemented


def resolve_cli(command_name: str) -> str:
    if os.name == "nt":
        cmd_candidate = shutil.which(f"{command_name}.cmd")
        if cmd_candidate:
            return cmd_candidate
    return shutil.which(command_name) or command_name


def classify_quota_error(text: str) -> str | None:
    """Return "transient", "hard", or None for a CLI error string."""
    if any(pattern.search(text) for pattern in HARD_QUOTA_PATTERNS):
        return "hard"
    if any(pattern.search(text) for pattern in TRANSIENT_QUOTA_PATTERNS):
        return "transient"
    return None


def is_quota_error(text: str) -> bool:
    return classify_quota_error(text) is not None


def _parse_retry_after(text: str) -> float | None:
    match = _RETRY_AFTER_RE.search(text)
    return float(match.group(1)) if match else None


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _extract_text(payload) -> str:
    if isinstance(payload, dict):
        for key in ("result", "completion", "output", "text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
        content = payload.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                    continue
                nested = item.get("content")
                if isinstance(nested, list):
                    parts.extend(str(part) for part in nested if isinstance(part, str))
            if parts:
                return "\n".join(parts)
        message = payload.get("message")
        if isinstance(message, dict):
            return _extract_text(message)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False)


def _parse_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_usage(payload) -> AgentUsage | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = _parse_int(
        usage.get("input_tokens", usage.get("inputTokens", usage.get("prompt_tokens")))
    )
    output_tokens = _parse_int(
        usage.get("output_tokens", usage.get("outputTokens", usage.get("completion_tokens")))
    )
    cost_usd = _parse_float(
        usage.get("cost_usd", usage.get("costUSD", usage.get("total_cost_usd")))
    )
    if input_tokens is None and output_tokens is None and cost_usd is None:
        return None
    return AgentUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


def _parse_agent_json(stdout: str) -> tuple[str, AgentUsage | None]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout.strip(), None
    return _extract_text(payload).strip(), _extract_usage(payload)


def run_subprocess(
    command: list[str],
    *,
    stdin_input: str,
    cwd: str | None,
    env: dict[str, str],
    encoding: str,
    timeout: float | None,
    target: str,
    wait_on_hard_quota: bool = True,
    parse_json_output: bool = False,
    role: str | None = None,
    change: str | None = None,
    task: str | None = None,
    branch: str | None = None,
    session: str | None = None,
    model: str | None = None,
) -> SubprocessResult:
    # Hard exhaustion is bounded by total wall-time, not an unbounded retry count
    # (the old 288 x 300s default could hang silently for ~24h). Transient
    # throttling backs off briefly for a small number of attempts.
    hard_budget = _env_float("LLM_QUOTA_HARD_BUDGET", 1800)
    hard_interval = _env_float("LLM_QUOTA_RETRY_INTERVAL", 120)
    transient_max = int(_env_float("LLM_QUOTA_TRANSIENT_MAX_RETRIES", 5))
    transient_base = _env_float("LLM_QUOTA_TRANSIENT_BASE", 5)
    transient_cap = _env_float("LLM_QUOTA_TRANSIENT_CAP", 60)

    transient_attempts = 0
    hard_deadline: float | None = None
    retry_count = 0

    while True:
        try:
            completed = jobs.run_blocking(
                jobs.JobSpec(
                    command=command,
                    stdin_input=stdin_input,
                    cwd=cwd,
                    env=env,
                    encoding=encoding,
                    timeout=timeout,
                    target=target,
                    model=model,
                    role=role,
                    change=change,
                    task=task,
                    branch=branch,
                    session=session,
                )
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentTimeoutError(f"{target} subprocess timed out") from exc
        except FileNotFoundError as exc:
            raise AgentExecutionError(f"{target} CLI not found on PATH") from exc
        except Exception as exc:
            raise AgentExecutionError(f"{target} subprocess error: {exc}") from exc

        if completed.status == jobs.JOB_STATUS_TIMEOUT:
            raise AgentTimeoutError(f"{target} subprocess timed out job_id={completed.job_id} log={completed.log_path}")

        if completed.returncode == 0 and completed.status == jobs.JOB_STATUS_SUCCEEDED:
            stdout = (completed.stdout or "").strip()
            usage = None
            if parse_json_output:
                stdout, usage = _parse_agent_json(stdout)
            return SubprocessResult(
                stdout=stdout,
                retries=retry_count,
                usage=usage,
                job_id=completed.job_id,
                log_path=completed.log_path,
            )

        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = "\n".join(part for part in (stderr, stdout) if part) or "(no output)"
        job_detail = f" job_id={completed.job_id} log={completed.log_path}"
        kind = classify_quota_error(detail)

        if kind is None:
            raise AgentExecutionError(f"{target} CLI failed (exit {completed.returncode}): {detail[:500]}{job_detail}")

        if kind == "transient":
            if transient_attempts >= transient_max:
                raise AgentQuotaError(
                    f"{target} throttled: {transient_max} transient retries exhausted. Last error: {detail[:300]}{job_detail}"
                )
            wait = _parse_retry_after(detail)
            if wait is None:
                wait = min(transient_base * (2 ** transient_attempts), transient_cap)
            transient_attempts += 1
            retry_count += 1
            logger.warning(
                "quota retry: %s transient throttle, attempt %d/%d, waiting %.0fs",
                target,
                transient_attempts,
                transient_max,
                wait,
            )
            time.sleep(wait)
            continue

        # kind == "hard"
        if not wait_on_hard_quota:
            raise AgentQuotaError(
                f"{target} quota exhausted (fast-fallback: not waiting). Last error: {detail[:300]}{job_detail}"
            )
        now = time.monotonic()
        if hard_deadline is None:
            hard_deadline = now + hard_budget
        if now >= hard_deadline:
            raise AgentQuotaError(
                f"{target} quota exhausted: hard retry budget ({hard_budget:.0f}s) elapsed. Last error: {detail[:300]}{job_detail}"
            )
        wait = min(hard_interval, hard_deadline - now)
        retry_count += 1
        logger.warning(
            "quota retry: %s hard exhaustion, waiting %.0fs (%.0fs of %.0fs budget left)",
            target,
            wait,
            hard_deadline - now,
            hard_budget,
        )
        time.sleep(wait)


def check_via_version(tool: str) -> TargetStatus:
    binary = resolve_cli(tool)
    try:
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15, input="")
        if result.returncode == 0:
            return TargetStatus(ok=True)
        reason = (result.stderr or result.stdout or "non-zero exit").strip()
        return TargetStatus(ok=False, reason=reason[:200])
    except FileNotFoundError:
        return TargetStatus(ok=False, reason=f"{tool} CLI not found on PATH")
    except subprocess.TimeoutExpired:
        return TargetStatus(ok=False, reason=f"{tool} --version timed out")
    except Exception as exc:
        return TargetStatus(ok=False, reason=str(exc)[:200])
