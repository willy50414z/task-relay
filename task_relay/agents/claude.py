import os
import subprocess

from task_relay.agents.common import resolve_cli, run_subprocess
from task_relay.types import AgentRunRequest, AgentRunResult, TargetStatus


class ClaudeRunner:
    name = "claude"

    def __init__(self, *, default_model: str | None = None, default_effort: str | None = None) -> None:
        self.default_model = default_model
        self.default_effort = default_effort

    def build_command(
        self,
        *,
        prompt: str,
        cwd: str | None,
        model: str | None,
        effort: str | None,
    ) -> tuple[list[str], dict[str, str], str | None]:
        command = [
            resolve_cli("claude"),
            "--print",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]
        resolved_model = model or self.default_model
        if resolved_model:
            command.extend(["--model", resolved_model])
        return command, dict(os.environ), resolved_model

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        command, env, model = self.build_command(
            prompt=request.prompt,
            cwd=request.cwd,
            model=request.model,
            effort=request.effort,
        )
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
            role=request.role,
            change=request.change,
            task=request.task,
            branch=request.branch,
            session=request.session,
            model=model,
        )
        return AgentRunResult(
            stdout=result.stdout,
            target=self.name,
            model=model,
            retries=result.retries,
            usage=result.usage,
            job_id=result.job_id,
            log_path=result.log_path,
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
