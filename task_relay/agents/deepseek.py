import os
import subprocess

from task_relay.agents.common import resolve_cli, run_subprocess
from task_relay.errors import AgentExecutionError
from task_relay.types import AgentRunRequest, AgentRunResult, TargetStatus

DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-pro[1m]"
DEEPSEEK_SUBAGENT_MODEL = "deepseek-v4-flash"
DEEPSEEK_EFFORT_LEVEL = "max"


class DeepSeekRunner:
    name = "deepseek"

    def __init__(self, *, default_model: str | None = None, default_effort: str | None = None) -> None:
        self.default_model = default_model or DEEPSEEK_DEFAULT_MODEL
        self.default_effort = default_effort or DEEPSEEK_EFFORT_LEVEL

    def build_command(
        self,
        *,
        prompt: str,
        cwd: str | None,
        model: str | None,
        effort: str | None,
    ) -> tuple[list[str], dict[str, str], str]:
        token = os.environ.get("DEEPSEEK_AUTH_TOKEN", "").strip()
        if not token:
            raise AgentExecutionError(
                "DEEPSEEK_AUTH_TOKEN environment variable is required for deepseek target."
            )
        resolved_model = model or self.default_model
        env = dict(os.environ)
        env["ANTHROPIC_BASE_URL"] = DEEPSEEK_BASE_URL
        env["ANTHROPIC_AUTH_TOKEN"] = token
        env["ANTHROPIC_MODEL"] = resolved_model
        env["ANTHROPIC_DEFAULT_OPUS_MODEL"] = resolved_model
        env["ANTHROPIC_DEFAULT_SONNET_MODEL"] = resolved_model
        env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = DEEPSEEK_SUBAGENT_MODEL
        env["CLAUDE_CODE_SUBAGENT_MODEL"] = DEEPSEEK_SUBAGENT_MODEL
        env["CLAUDE_CODE_EFFORT_LEVEL"] = effort or self.default_effort
        command = [
            resolve_cli("claude"),
            "--print",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]
        if model:
            command.extend(["--model", model])
        return command, env, resolved_model

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
        token = os.environ.get("DEEPSEEK_AUTH_TOKEN", "").strip()
        if not token:
            return TargetStatus(ok=False, reason="DEEPSEEK_AUTH_TOKEN is not set")
        binary = resolve_cli("claude")
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                input="",
            )
        except FileNotFoundError:
            return TargetStatus(ok=False, reason="claude CLI not found on PATH")
        except subprocess.TimeoutExpired:
            return TargetStatus(ok=False, reason="claude --version timed out")
        except Exception as exc:
            return TargetStatus(ok=False, reason=str(exc)[:200])
        if result.returncode != 0:
            reason = result.stderr.strip() or result.stdout.strip() or "claude CLI probe failed"
            return TargetStatus(ok=False, reason=reason[:200])
        return TargetStatus(ok=True)
