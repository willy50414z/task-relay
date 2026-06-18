import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone

from task_relay.errors import AgentExecutionError, AgentQuotaError, AgentTimeoutError
from task_relay.types import TargetStatus

QUOTA_ERROR_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"exceeded your monthly token limit",
        r"exceeded your current quota",
        r"insufficient.quota",
        r"quota.exceeded",
        r"billing hard limit",
        r"credit balance is too low",
        r"out of credits",
        r"rate.limit.exceeded",
        r"429",
        r"payment required",
    ]
]


def resolve_cli(command_name: str) -> str:
    if os.name == "nt":
        cmd_candidate = shutil.which(f"{command_name}.cmd")
        if cmd_candidate:
            return cmd_candidate
    return shutil.which(command_name) or command_name


def is_quota_error(text: str) -> bool:
    return any(pattern.search(text) for pattern in QUOTA_ERROR_PATTERNS)


def run_subprocess(
    command: list[str],
    *,
    stdin_input: str,
    cwd: str | None,
    env: dict[str, str],
    encoding: str,
    timeout: float | None,
    target: str,
) -> str:
    retry_interval = int(os.getenv("LLM_QUOTA_RETRY_INTERVAL", "300"))
    max_retries = int(os.getenv("LLM_QUOTA_MAX_RETRIES", "288"))
    for quota_attempt in range(max_retries + 1):
        try:
            completed = subprocess.run(
                command,
                input=stdin_input,
                capture_output=True,
                text=True,
                encoding=encoding,
                errors="replace",
                cwd=cwd,
                env=env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentTimeoutError(f"{target} subprocess timed out") from exc
        except FileNotFoundError as exc:
            raise AgentExecutionError(f"{target} CLI not found on PATH") from exc
        except Exception as exc:
            raise AgentExecutionError(f"{target} subprocess error: {exc}") from exc

        if completed.returncode == 0:
            return (completed.stdout or "").strip()

        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = "\n".join(part for part in (stderr, stdout) if part) or "(no output)"
        if is_quota_error(detail):
            if quota_attempt < max_retries:
                _ = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                time.sleep(retry_interval)
                continue
            raise AgentQuotaError(f"{target} quota exhausted after {max_retries} retries. Last error: {detail[:300]}")
        raise AgentExecutionError(f"{target} CLI failed (exit {completed.returncode}): {detail[:500]}")
    raise AgentQuotaError(f"{target} quota exhausted")


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
