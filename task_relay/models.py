from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    tier: str  # "high", "medium", "fast"
    provider: str  # "anthropic", "openai", "deepseek"


CLAUDE_MODELS: list[ModelInfo] = [
    ModelInfo(id="claude-opus-4-8", name="Opus 4.8", tier="high", provider="anthropic"),
    ModelInfo(id="claude-sonnet-4-6", name="Sonnet 4.6", tier="medium", provider="anthropic"),
    ModelInfo(id="claude-haiku-4-5-20251001", name="Haiku 4.5", tier="fast", provider="anthropic"),
    ModelInfo(id="claude-fable-5", name="Fable 5", tier="high", provider="anthropic"),
]

CODEX_MODELS: list[ModelInfo] = [
    ModelInfo(id="gpt-5.5-high", name="GPT-5.5 High", tier="high", provider="openai"),
    ModelInfo(id="gpt-5.5-medium", name="GPT-5.5 Medium", tier="medium", provider="openai"),
    ModelInfo(id="gpt-5.4", name="GPT-5.4", tier="fast", provider="openai"),
]

DEEPSEEK_MODELS: list[ModelInfo] = [
    ModelInfo(id="deepseek-v4-pro[1m]", name="DeepSeek V4 Pro", tier="high", provider="deepseek"),
    ModelInfo(id="deepseek-v4-flash", name="DeepSeek V4 Flash", tier="fast", provider="deepseek"),
]

AGENT_DEFAULTS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "codex": "gpt-5.5-medium",
    "deepseek": "deepseek-v4-pro[1m]",
}

_MODEL_REGISTRY: dict[str, list[ModelInfo]] = {
    "claude": CLAUDE_MODELS,
    "codex": CODEX_MODELS,
    "deepseek": DEEPSEEK_MODELS,
}


def get_catalog(agent_name: str) -> list[ModelInfo]:
    """Return the model catalog for a given agent name.

    Raises ValueError if the agent is unknown.
    """
    catalog = _MODEL_REGISTRY.get(agent_name)
    if catalog is None:
        raise ValueError(f"Unknown agent: {agent_name}. Valid agents: {', '.join(sorted(_MODEL_REGISTRY))}")
    return catalog


def format_model_choices(catalog: list[ModelInfo]) -> str:
    """Format a model catalog as a numbered list for terminal display."""
    lines: list[str] = []
    for i, model in enumerate(catalog, start=1):
        lines.append(f"  [{i}] {model.id} — {model.name} ({model.tier})")
    return "\n".join(lines)


def find_model_by_index(catalog: list[ModelInfo], index: int) -> ModelInfo:
    """Return the model at the given 1-based index in the catalog.

    Raises IndexError if out of range.
    """
    if index < 1 or index > len(catalog):
        raise IndexError(f"Invalid selection: {index}. Choose 1–{len(catalog)}.")
    return catalog[index - 1]


def get_default_model(agent_name: str) -> str:
    """Return the default model ID for an agent."""
    return AGENT_DEFAULTS.get(agent_name, "")
