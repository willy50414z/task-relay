from task_relay.agents.base import AgentRunner
from task_relay.agents.claude import ClaudeRunner
from task_relay.agents.codex import CodexRunner
from task_relay.agents.deepseek import DeepSeekRunner
from task_relay.config import load_config
from task_relay.errors import AgentNotFoundError
from task_relay.types import TargetStatus

BUILTIN_AGENTS = ("claude", "codex", "deepseek")


def resolve(name: str | None = None, *, config_path: str | None = None) -> AgentRunner:
    config = load_config(config_path)
    agent_name = name or config.get("default_agent") or "claude"
    agent_cfg = config.get("agents", {}).get(agent_name, {})
    if agent_name == "claude":
        return ClaudeRunner(default_model=agent_cfg.get("model"), default_effort=agent_cfg.get("effort"))
    if agent_name == "codex":
        return CodexRunner(default_model=agent_cfg.get("model"), default_effort=agent_cfg.get("effort"))
    if agent_name == "deepseek":
        return DeepSeekRunner(default_model=agent_cfg.get("model"), default_effort=agent_cfg.get("effort"))
    raise AgentNotFoundError(f"Unknown agent: {agent_name}")


def check_target(name: str, *, config_path: str | None = None) -> TargetStatus:
    return resolve(name, config_path=config_path).check()


def check_all(*, config_path: str | None = None) -> dict[str, TargetStatus]:
    return {name: resolve(name, config_path=config_path).check() for name in BUILTIN_AGENTS}
