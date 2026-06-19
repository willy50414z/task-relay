"""Interactive install wizard for trly install."""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from task_relay.models import (
    get_catalog,
    get_default_model,
)

VALID_PRIMARY_AGENTS = ("claude", "codex")
VALID_SCOPES = ("user", "project")
VALID_MODES = ("main", "hybrid", "delegated-apply")
VALID_SUB_AGENTS = ("claude", "codex", "deepseek")

# Display metadata for each option value
_OPTION_LABELS: dict[str, str] = {
    "claude": "Claude Code",
    "codex": "OpenAI Codex",
    "deepseek": "DeepSeek (via Claude CLI bridge)",
    "user": "User (~/.claude/ or ~/.codex/) — global default for all projects",
    "project": "Project (./) — this project only",
    "main": "Main — no delegation, all work stays with primary agent",
    "hybrid": "Hybrid — primary orchestrates, sub-agent handles bounded work (recommended)",
    "delegated-apply": "Delegated-apply — primary delegates full apply to sub-agent and verifies",
}


@dataclass
class WizardState:
    primary_agent: str | None = None
    scope: str | None = None
    mode: str | None = None
    sub_agent: str | None = None
    # "primary" → model_id, "sub" → model_id
    models: dict[str, str] = field(default_factory=dict)
    cwd: Path = field(default_factory=Path.cwd)


@dataclass(frozen=True)
class Choice:
    value: str
    title: str
    description: str | None = None


class PromptAdapter(Protocol):
    def select(self, message: str, choices: list[Choice], default: str | None = None) -> str:
        ...

    def confirm(self, message: str, default: bool = True) -> bool:
        ...


class QuestionaryPromptAdapter:
    def select(self, message: str, choices: list[Choice], default: str | None = None) -> str:
        if not sys.stdin.isatty():
            raise RuntimeError(_non_interactive_message())
        try:
            import questionary
            from questionary import Choice as QuestionaryChoice
        except ImportError as exc:
            raise RuntimeError(
                "Interactive install requires the 'questionary' package. "
                "Install task-relay with its dependencies or use non-interactive flags."
            ) from exc

        rendered = [
            QuestionaryChoice(
                title=f"{choice.value} - {choice.title}",
                value=choice.value,
                description=choice.description,
            )
            for choice in choices
        ]
        result = questionary.select(message, choices=rendered, default=default).ask()
        if result is None:
            raise KeyboardInterrupt
        return str(result)

    def confirm(self, message: str, default: bool = True) -> bool:
        if not sys.stdin.isatty():
            raise RuntimeError(_non_interactive_message())
        try:
            import questionary
        except ImportError as exc:
            raise RuntimeError(
                "Interactive install requires the 'questionary' package. "
                "Install task-relay with its dependencies or use non-interactive flags."
            ) from exc
        result = questionary.confirm(message, default=default).ask()
        if result is None:
            raise KeyboardInterrupt
        return bool(result)


def make_prompt_adapter() -> PromptAdapter:
    return QuestionaryPromptAdapter()


def _non_interactive_message() -> str:
    return (
        "stdin is not a TTY; use required non-interactive flags: "
        "--primary, --scope, --mode, and --sub-agent when mode is not 'main'"
    )


def _choices(options: list[str]) -> list[Choice]:
    return [Choice(value=opt, title=_OPTION_LABELS.get(opt, opt)) for opt in options]


def prompt_primary_agent(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = list(VALID_PRIMARY_AGENTS)
    default = state.primary_agent or "codex"
    choice = prompt.select("Select primary orchestration agent:", _choices(options), default=default)
    return WizardState(
        primary_agent=choice,
        scope=state.scope,
        mode=state.mode,
        sub_agent=state.sub_agent,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_scope(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = list(VALID_SCOPES)
    default = state.scope or "project"
    choice = prompt.select("Select installation scope:", _choices(options), default=default)
    return WizardState(
        primary_agent=state.primary_agent,
        scope=choice,
        mode=state.mode,
        sub_agent=state.sub_agent,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_mode(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = list(VALID_MODES)
    default = state.mode or "hybrid"
    choice = prompt.select("Select delegation mode:", _choices(options), default=default)
    return WizardState(
        primary_agent=state.primary_agent,
        scope=state.scope,
        mode=choice,
        sub_agent=state.sub_agent,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_sub_agent(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = list(VALID_SUB_AGENTS)
    default = state.sub_agent or "deepseek"
    choice = prompt.select("Select sub-agent for delegated work:", _choices(options), default=default)
    return WizardState(
        primary_agent=state.primary_agent,
        scope=state.scope,
        mode=state.mode,
        sub_agent=choice,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_model(
    agent_name: str,
    role_key: str,
    role_label: str,
    state: WizardState,
    prompt: PromptAdapter,
) -> WizardState:
    catalog = get_catalog(agent_name)
    existing = state.models.get(role_key)
    default_id = existing or get_default_model(agent_name)
    choices = [
        Choice(
            value=model.id,
            title=f"{model.name} ({model.tier})",
            description=model.provider,
        )
        for model in catalog
    ]
    choice = prompt.select(
        f"Select model for {role_label} ({agent_name}):",
        choices,
        default=default_id,
    )

    new_models = dict(state.models)
    new_models[role_key] = choice
    return WizardState(
        primary_agent=state.primary_agent,
        scope=state.scope,
        mode=state.mode,
        sub_agent=state.sub_agent,
        models=new_models,
        cwd=state.cwd,
    )


def confirm_and_write(
    state: WizardState,
    write_fn: Callable[[WizardState], None],
    prompt: PromptAdapter,
) -> bool:
    print()
    print("-- Configuration Summary --")
    print(f"  Primary agent : {state.primary_agent}")
    print(f"  Scope         : {state.scope}")
    print(f"  Mode          : {state.mode}")
    print(f"  Sub-agent     : {state.sub_agent}")
    print(f"  Models        :")
    if "primary" in state.models:
        print(f"    primary ({state.primary_agent}): {state.models['primary']}")
    if "sub" in state.models:
        print(f"    sub ({state.sub_agent}): {state.models['sub']}")
    print()

    if prompt.confirm("Write configuration?", default=True):
        write_fn(state)
        print("Configuration written.")
        return True
    print("Aborted.")
    return False


def run_wizard(
    write_fn: Callable[[WizardState], None],
    clear_fn: Callable[[WizardState], None],
    cwd: Path | None = None,
    prefill_path: str | None = None,
    prompt: PromptAdapter | None = None,
) -> int:
    state = WizardState(cwd=Path(cwd) if cwd else Path.cwd())
    prompt = prompt or make_prompt_adapter()

    if prefill_path:
        state = prefill_from_existing(Path(prefill_path), state)

    try:
        state = prompt_primary_agent(state, prompt)
        state = prompt_scope(state, prompt)

        state = prompt_mode(state, prompt)
        if state.mode == "main":
            clear_fn(state)
            print("Delegation cleared (mode: main).")
            return 0

        state = prompt_sub_agent(state, prompt)

        # Primary agent model
        state = prompt_model(state.primary_agent, "primary", "primary", state, prompt)
        # Sub-agent model
        state = prompt_model(state.sub_agent, "sub", "sub-agent", state, prompt)

        if confirm_and_write(state, write_fn, prompt):
            return 0
        return 1

    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return 1


def prefill_from_existing(path: Path, state: WizardState | None = None) -> WizardState:
    if state is None:
        state = WizardState()
    if not path.exists():
        return state
    try:
        parsed = _parse_managed_block(path.read_text(encoding="utf-8"))
    except Exception:
        return state

    if parsed.get("primary"):
        state.primary_agent = parsed["primary"]
    if parsed.get("mode"):
        state.mode = parsed["mode"]
    if parsed.get("sub_agent"):
        state.sub_agent = parsed["sub_agent"]
    if parsed.get("models"):
        state.models = _normalize_model_roles(parsed)
    if parsed.get("scope"):
        state.scope = parsed["scope"]
    return state


def _normalize_model_roles(parsed: dict) -> dict[str, str]:
    models = parsed.get("models") or {}
    normalized: dict[str, str] = {}
    if models.get("primary"):
        normalized["primary"] = models["primary"]
    if models.get("sub"):
        normalized["sub"] = models["sub"]

    primary = parsed.get("primary")
    sub_agent = parsed.get("sub_agent")
    if primary and not normalized.get("primary"):
        normalized["primary"] = models.get(primary) or models.get(f"{primary} (primary)")
    if sub_agent and not normalized.get("sub"):
        normalized["sub"] = models.get(sub_agent) or models.get(f"{sub_agent} (sub)")

    return {key: value for key, value in normalized.items() if value}


def _parse_managed_block(text: str) -> dict:
    start_marker = "<!-- task-relay:start -->"
    end_marker = "<!-- task-relay:end -->"
    legacy_start = "<!-- task-relay:openspec-delegation:start -->"
    legacy_end = "<!-- task-relay:openspec-delegation:end -->"

    for s, e in [(start_marker, end_marker), (legacy_start, legacy_end)]:
        si = text.find(s)
        ei = text.find(e)
        if si != -1 and ei != -1 and ei > si:
            block = text[si + len(s):ei]
            result: dict = {}
            for line in block.strip().splitlines():
                stripped = line.strip()
                # Parse key: value lines (with optional leading "- ")
                kv = stripped.removeprefix("- ").strip()
                if ":" not in kv:
                    continue
                key, _, value = kv.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "primary":
                    result["primary"] = value
                elif key == "mode":
                    result["mode"] = value
                elif key == "sub-agent":
                    result["sub_agent"] = value
                elif key == "scope":
                    result["scope"] = value
            # Parse models section
            in_models = False
            for line in block.strip().splitlines():
                stripped = line.strip()
                if stripped == "- models:" or stripped == "models:":
                    in_models = True
                    continue
                if in_models and stripped.startswith("- ") and ":" in stripped[2:]:
                    agent, _, model = stripped[2:].partition(":")
                    agent = agent.strip()
                    model = model.strip()
                    if agent and model:
                        result.setdefault("models", {})[agent] = model
                elif in_models and not stripped.startswith("- "):
                    in_models = False
            return result
    return {}
