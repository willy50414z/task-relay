import os
import subprocess

from task_relay.agents.common import resolve_cli, run_subprocess
from task_relay.types import AgentRunRequest, AgentRunResult, TargetStatus


class ClaudeRunner:
    name = "claude"

    def __init__(self, *, default_model: str | None = None, default_effort: str | None = None) -> None:
        self.default_model = default_model
        self.default_effort = default_effort

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        command = [
            resolve_cli("claude"),
            "--print",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]
        model = request.model or self.default_model
        if model:
            command.extend(["--model", model])
        env = dict(os.environ)
        if request.extra_env:
            env.update(request.extra_env)
        result = run_subprocess(
            command,
            stdin_input=request.prompt,
            cwd=request.cwd,
            env=env,
            encoding=request.encoding,
            timeout=request.timeout,
            target=self.name,
            wait_on_hard_quota=request.wait_on_hard_quota,
            parse_json_output=True,
        )
        return AgentRunResult(
            stdout=result.stdout,
            target=self.name,
            model=model,
            retries=result.retries,
            usage=result.usage,
        )

    def check(self) -> TargetStatus:
        binary = resolve_cli("claude")
        try:
            result = subprocess.run(
                [binary, "auth", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
                input="",
            )
            if result.returncode == 0 and '"loggedIn": true' in result.stdout:
                return TargetStatus(ok=True)
            reason = result.stderr.strip() or result.stdout.strip() or "loggedIn not true"
            return TargetStatus(ok=False, reason=reason[:200])
        except FileNotFoundError:
            return TargetStatus(ok=False, reason="claude CLI not found on PATH")
        except subprocess.TimeoutExpired:
            return TargetStatus(ok=False, reason="claude auth status timed out")
        except Exception as exc:
            return TargetStatus(ok=False, reason=str(exc)[:200])
