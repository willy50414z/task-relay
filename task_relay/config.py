from copy import deepcopy
from pathlib import Path
from typing import Any

from task_relay.errors import ConfigError

DEFAULT_CONFIG = {
    "default_agent": None,
    "agents": {
        "claude": {},
        "codex": {},
        "deepseek": {},
    },
}


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path).expanduser() if config_path else Path.home() / ".task-relay" / "config.yml"
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)
    data = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("config must be a mapping")
    unknown_root = set(data) - {"default_agent", "agents"}
    if unknown_root:
        raise ConfigError(f"unknown config fields: {', '.join(sorted(unknown_root))}")
    merged = deepcopy(DEFAULT_CONFIG)
    if "default_agent" in data:
        merged["default_agent"] = data["default_agent"]
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise ConfigError("config agents field must be a mapping")
    for name, values in agents.items():
        if not isinstance(values, dict):
            raise ConfigError(f"agent '{name}' config must be a mapping")
        if values.get("type") == "opencli":
            raise ConfigError("agent type 'opencli' is not supported in task-relay v0.2")
        unsupported = set(values) - {"type", "model", "effort"}
        if unsupported:
            raise ConfigError(
                f"agent '{name}' has unknown fields: {', '.join(sorted(unsupported))}"
            )
        merged["agents"].setdefault(name, {}).update(values)
    return merged


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current_section: str | None = None
    current_agent: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0:
            key, value = _parse_key_value(stripped)
            current_agent = None
            if value is None:
                root[key] = {}
                current_section = key
            else:
                root[key] = value
                current_section = None
        elif indent == 2 and current_section == "agents":
            key, value = _parse_key_value(stripped)
            if value is None:
                root.setdefault("agents", {})[key] = {}
                current_agent = key
            else:
                root.setdefault("agents", {})[key] = value
                current_agent = None
        elif indent == 4 and current_section == "agents" and current_agent is not None:
            key, value = _parse_key_value(stripped)
            if value is None:
                raise ConfigError("nested config deeper than one agent mapping is not supported")
            root["agents"][current_agent][key] = value
        else:
            raise ConfigError("unsupported config indentation or structure")
    return root


def _parse_key_value(text: str) -> tuple[str, str | None]:
    if ":" not in text:
        raise ConfigError("config lines must use key: value syntax")
    key, raw_value = text.split(":", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
        raise ConfigError("config keys must not be empty")
    return key, value or None
