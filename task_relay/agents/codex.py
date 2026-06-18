import os
import subprocess

from task_relay.agents.common import resolve_cli, run_subprocess
from task_relay.types import AgentRunRequest, AgentRunResult, TargetStatus


class CodexRunner:
    name = "codex"

    def __init__(self, *, default_model: str | None = None, default_effort: str | None = None) -> None:
        self.default_model = default_model
        self.default_effort = default_effort

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        command = [
            resolve_cli("codex"),
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
        ]
        model = request.model or self.default_model
        effort = request.effort or self.default_effort
        if model:
            command.extend(["--model", model])
        if effort:
            command.extend(["-c", f"model_reasoning_effort={effort}"])
        stdout = run_subprocess(
            command,
            stdin_input=request.prompt,
            cwd=request.cwd,
            env=dict(os.environ),
            encoding=request.encoding,
            timeout=request.timeout,
            target=self.name,
        )
        return AgentRunResult(stdout=stdout, target=self.name)

    def check(self) -> TargetStatus:
        binary = resolve_cli("codex")
        try:
            result = subprocess.run(
                [binary, "login", "status"],
                capture_output=True,
                text=True,
                timeout=15,
                input="",
            )
            auth_output = f"{result.stdout}\n{result.stderr}"
            if result.returncode == 0 and "Logged in" in auth_output:
                return TargetStatus(ok=True)
            reason = result.stderr.strip() or result.stdout.strip() or "not logged in"
            return TargetStatus(ok=False, reason=reason[:200])
        except FileNotFoundError:
            return TargetStatus(ok=False, reason="codex CLI not found on PATH")
        except subprocess.TimeoutExpired:
            return TargetStatus(ok=False, reason="codex login status timed out")
        except Exception as exc:
            return TargetStatus(ok=False, reason=str(exc)[:200])
