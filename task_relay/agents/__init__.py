from task_relay.agents.base import AgentRunner
from task_relay.agents.claude import ClaudeRunner
from task_relay.agents.codex import CodexRunner
from task_relay.agents.deepseek import DeepSeekRunner
from task_relay.agents.zerotoken import TokenFreeGatewayRunner
from task_relay.errors import AgentNotFoundError
from task_relay.types import TargetStatus

BUILTIN_AGENTS = ("claude", "codex", "deepseek", "zerotoken")


def resolve(name: str | None = None) -> AgentRunner:
    agent_name = name or "claude"
    if agent_name == "claude":
        return ClaudeRunner()
    if agent_name == "codex":
        return CodexRunner()
    if agent_name == "deepseek":
        return DeepSeekRunner()
    if agent_name == "zerotoken":
        return TokenFreeGatewayRunner()
    raise AgentNotFoundError(f"Unknown agent: {agent_name}")


def check_target(name: str) -> TargetStatus:
    return resolve(name).check()


def check_all() -> dict[str, TargetStatus]:
    return {name: resolve(name).check() for name in BUILTIN_AGENTS}
