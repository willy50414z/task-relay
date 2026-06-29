"""Interactive install wizard for trly install."""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from task_relay.models import get_catalog, get_default_model
from task_relay.review_config import (
    DEFAULT_GLOBAL_TIMEOUT,
    DEFAULT_REVIEWER_PERSONA,
    ReviewRoleEntry,
    default_arbiter_entries,
    format_role_entries,
)

VALID_TARGET_AGENTS = ("claude", "codex")
VALID_SCOPES = ("user", "project")
VALID_AGENTS = ("claude", "codex", "deepseek")

_OPTION_LABELS: dict[str, str] = {
    "claude": "Claude Code",
    "codex": "OpenAI Codex",
    "deepseek": "DeepSeek (via Claude CLI bridge)",
    "user": "User (~/.claude/ or ~/.codex/) — global default for all projects",
    "project": "Project (./) — this project only",
}


@dataclass
class WizardState:
    target_agents: list[str] = field(default_factory=list)
    scope: str | None = None
    features: list[str] = field(default_factory=list)
    reviewers: list[ReviewRoleEntry] = field(default_factory=list)
    arbiters: list[ReviewRoleEntry] = field(default_factory=list)
    apply_chain: list[tuple[str, str | None]] = field(default_factory=list)
    global_timeout: int = DEFAULT_GLOBAL_TIMEOUT
    cwd: Path = field(default_factory=Path.cwd)


@dataclass(frozen=True)
class Choice:
    value: str
    title: str
    description: str | None = None


class PromptAdapter(Protocol):
    def select(self, message: str, choices: list[Choice], default: str | None = None) -> str:
        ...

    def checkbox(self, message: str, choices: list[Choice], default: list[str] | None = None) -> list[str]:
        ...

    def confirm(self, message: str, default: bool = True) -> bool:
        ...


class QuestionaryPromptAdapter:
    def _load_questionary(self):
        try:
            import questionary
            from questionary import Choice as QuestionaryChoice
        except ImportError as exc:
            raise RuntimeError(
                "Interactive install requires the 'questionary' package. "
                "Install task-relay with its dependencies or use non-interactive flags."
            ) from exc
        return questionary, QuestionaryChoice

    def _rendered_choices(self, choices: list[Choice]):
        _, QuestionaryChoice = self._load_questionary()
        return [
            QuestionaryChoice(
                title=f"{choice.value} - {choice.title}",
                value=choice.value,
                description=choice.description,
                checked=False,
            )
            for choice in choices
        ]

    def select(self, message: str, choices: list[Choice], default: str | None = None) -> str:
        if not sys.stdin.isatty():
            raise RuntimeError(_non_interactive_message())
        questionary, _ = self._load_questionary()
        result = questionary.select(message, choices=self._rendered_choices(choices), default=default).ask()
        if result is None:
            raise KeyboardInterrupt
        return str(result)

    def checkbox(self, message: str, choices: list[Choice], default: list[str] | None = None) -> list[str]:
        if not sys.stdin.isatty():
            raise RuntimeError(_non_interactive_message())
        questionary, QuestionaryChoice = self._load_questionary()
        defaults = set(default or [])
        rendered = [
            QuestionaryChoice(
                title=f"{choice.value} - {choice.title}",
                value=choice.value,
                description=choice.description,
                checked=choice.value in defaults,
            )
            for choice in choices
        ]
        result = questionary.checkbox(message, choices=rendered).ask()
        if result is None:
            raise KeyboardInterrupt
        return [str(item) for item in result]

    def confirm(self, message: str, default: bool = True) -> bool:
        if not sys.stdin.isatty():
            raise RuntimeError(_non_interactive_message())
        questionary, _ = self._load_questionary()
        result = questionary.confirm(message, default=default).ask()
        if result is None:
            raise KeyboardInterrupt
        return bool(result)


def make_prompt_adapter() -> PromptAdapter:
    return QuestionaryPromptAdapter()


def _non_interactive_message() -> str:
    return (
        "stdin is not a TTY; use required non-interactive flags: "
        "--primary/--targets, --scope, --mode, and --sub-agent when mode is not 'main'"
    )


def _choices(options: list[str]) -> list[Choice]:
    return [Choice(value=opt, title=_OPTION_LABELS.get(opt, opt)) for opt in options]


def prompt_target_agents(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = list(VALID_TARGET_AGENTS)
    default = state.target_agents or ["codex"]
    choices = prompt.checkbox("Select installation targets:", _choices(options), default=default)
    selected = [choice for choice in options if choice in choices]
    if not selected:
        raise ValueError("Select at least one installation target.")
    return WizardState(
        target_agents=selected,
        scope=state.scope,
        features=list(state.features),
        reviewers=list(state.reviewers),
        arbiters=list(state.arbiters),
        apply_chain=list(state.apply_chain),
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def prompt_scope(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = list(VALID_SCOPES)
    default = state.scope or "project"
    choice = prompt.select("Select installation scope:", _choices(options), default=default)
    return WizardState(
        target_agents=list(state.target_agents),
        scope=choice,
        features=list(state.features),
        reviewers=list(state.reviewers),
        arbiters=list(state.arbiters),
        apply_chain=list(state.apply_chain),
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def prompt_features(state: WizardState, prompt: PromptAdapter) -> WizardState:
    options = ["review", "apply"]
    labels: dict[str, str] = {
        "review": "Review — review agent validates proposals for clarity, correctness, and completeness",
        "apply": "Apply — apply agent implements changes (replaces legacy sub-agent)",
    }
    default = state.features or ["apply"]
    choices = [Choice(value=opt, title=labels.get(opt, opt)) for opt in options]
    selected = prompt.checkbox("Select features to enable:", choices, default=default)
    selected = [choice for choice in options if choice in selected]
    return WizardState(
        target_agents=list(state.target_agents),
        scope=state.scope,
        features=selected,
        reviewers=list(state.reviewers),
        arbiters=list(state.arbiters),
        apply_chain=list(state.apply_chain),
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def _chain_agents(chain: list[tuple[str, str | None]]) -> list[str]:
    """Extract agent names already in the chain."""
    return [agent for agent, _model in chain]


def prompt_reviewer_primary(state: WizardState, prompt: PromptAdapter) -> WizardState:
    choice = prompt.select("Select primary reviewer agent:", _choices(list(VALID_AGENTS)))
    reviewers = [ReviewRoleEntry(agent=choice, persona=DEFAULT_REVIEWER_PERSONA)]
    return WizardState(
        target_agents=list(state.target_agents),
        scope=state.scope,
        features=list(state.features),
        reviewers=reviewers,
        arbiters=list(state.arbiters),
        apply_chain=list(state.apply_chain),
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def prompt_apply_primary(state: WizardState, prompt: PromptAdapter) -> WizardState:
    choice = prompt.select("Select primary Apply agent:", _choices(list(VALID_AGENTS)))
    return WizardState(
        target_agents=list(state.target_agents),
        scope=state.scope,
        features=list(state.features),
        reviewers=list(state.reviewers),
        arbiters=list(state.arbiters),
        apply_chain=[(choice, None)],
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def prompt_chain_primary(state: WizardState, chain_name: str, prompt: PromptAdapter) -> WizardState:
    if chain_name == "review":
        return prompt_reviewer_primary(state, prompt)
    return prompt_apply_primary(state, prompt)


def prompt_chain_model(
    state: WizardState, chain_name: str, agent: str, prompt: PromptAdapter
) -> WizardState:
    catalog = get_catalog(agent)
    default_id = get_default_model(agent)
    choices = [
        Choice(
            value=model.id,
            title=f"{model.name} ({model.tier})",
            description=model.provider,
        )
        for model in catalog
    ]
    label = "Reviewer" if chain_name == "review" else "Apply"
    choice = prompt.select(
        f"Select model for {label} agent ({agent}):",
        choices,
        default=default_id,
    )
    if chain_name == "review":
        updated_reviewers = [
            ReviewRoleEntry(agent=entry.agent, persona=entry.persona, model=choice if entry.agent == agent else entry.model)
            for entry in state.reviewers
        ]
        return WizardState(
            target_agents=list(state.target_agents),
            scope=state.scope,
            features=list(state.features),
            reviewers=updated_reviewers,
            arbiters=list(state.arbiters),
            apply_chain=list(state.apply_chain),
            global_timeout=state.global_timeout,
            cwd=state.cwd,
        )
    chain = _get_chain(state, chain_name)
    updated_chain = [(a, choice if a == agent else m) for a, m in chain]
    return _set_chain(state, chain_name, updated_chain)


def _get_chain(state: WizardState, chain_name: str) -> list[tuple[str, str | None]]:
    if chain_name == "review":
        return [(entry.agent, entry.model) for entry in state.reviewers]
    return state.apply_chain


def _set_chain(state: WizardState, chain_name: str, chain: list[tuple[str, str | None]]) -> WizardState:
    if chain_name == "review":
        return WizardState(
            target_agents=list(state.target_agents),
            scope=state.scope,
            features=list(state.features),
            reviewers=[ReviewRoleEntry(agent=agent, persona=DEFAULT_REVIEWER_PERSONA, model=model) for agent, model in chain],
            arbiters=list(state.arbiters),
            apply_chain=list(state.apply_chain),
            global_timeout=state.global_timeout,
            cwd=state.cwd,
        )
    return WizardState(
        target_agents=list(state.target_agents),
        scope=state.scope,
        features=list(state.features),
        reviewers=list(state.reviewers),
        arbiters=list(state.arbiters),
        apply_chain=chain,
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def prompt_chain_fallback_loop(
    state: WizardState, chain_name: str, prompt: PromptAdapter
) -> WizardState:
    """Loop: add fallback agents to a chain until user declines or agents exhausted."""
    label = "Review" if chain_name == "review" else "Apply"
    current = state

    while True:
        chain = _get_chain(current, chain_name)
        used_agents = _chain_agents(chain)
        available = [a for a in VALID_AGENTS if a not in used_agents]

        if not available:
            break

        chain_display = " → ".join(f"{a} ({m or 'default'})" for a, m in chain)
        print(f"\n  Current {label} chain: {chain_display}")

        if not prompt.confirm(f"Add fallback agent to {label} chain?", default=False):
            break

        chosen = prompt.select(
            f"Select {label} fallback agent:", _choices(available)
        )
        catalog = get_catalog(chosen)
        default_id = get_default_model(chosen)
        model_choices = [
            Choice(value=model.id, title=f"{model.name} ({model.tier})", description=model.provider)
            for model in catalog
        ]
        model = prompt.select(
            f"Select model for {label} fallback ({chosen}):",
            model_choices,
            default=default_id,
        )
        chain.append((chosen, model))
        current = _set_chain(current, chain_name, chain)

    return current


def prompt_default_arbiters(state: WizardState, prompt: PromptAdapter) -> WizardState:
    arbiters = default_arbiter_entries()
    if prompt.confirm("Use default serial arbiters (CEO then engineering)?", default=True):
        return WizardState(
            target_agents=list(state.target_agents),
            scope=state.scope,
            features=list(state.features),
            reviewers=list(state.reviewers),
            arbiters=arbiters,
            apply_chain=list(state.apply_chain),
            global_timeout=state.global_timeout,
            cwd=state.cwd,
        )
    return WizardState(
        target_agents=list(state.target_agents),
        scope=state.scope,
        features=list(state.features),
        reviewers=list(state.reviewers),
        arbiters=list(state.arbiters),
        apply_chain=list(state.apply_chain),
        global_timeout=state.global_timeout,
        cwd=state.cwd,
    )


def confirm_and_write(
    state: WizardState,
    write_fn: Callable[[WizardState], None],
    prompt: PromptAdapter,
) -> bool:
    print()
    print("-- Configuration Summary --")
    print(f"  Targets       : {', '.join(state.target_agents)}")
    print(f"  Scope         : {state.scope}")
    features_display = ", ".join(state.features) if state.features else "(none — no delegation)"
    print(f"  Features      : {features_display}")
    if "review" in state.features:
        print(f"  Reviewers     : {format_role_entries(state.reviewers)}")
        print(f"  Arbiter chain : {format_role_entries(state.arbiters)}")
        print(f"  Global timeout: {state.global_timeout}s")
    if "apply" in state.features:
        chain_display = " → ".join(
            f"{a} ({m or 'default'})" for a, m in state.apply_chain
        )
        print(f"  Apply chain   : {chain_display}")
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
    prefill_state: WizardState | None = None,
    prompt: PromptAdapter | None = None,
) -> int:
    state = WizardState(cwd=Path(cwd) if cwd else Path.cwd())
    prompt = prompt or make_prompt_adapter()

    if prefill_state is not None:
        state.target_agents = list(prefill_state.target_agents)
        state.scope = prefill_state.scope
        state.features = list(prefill_state.features)
        state.reviewers = list(prefill_state.reviewers)
        state.arbiters = list(prefill_state.arbiters)
        state.apply_chain = list(prefill_state.apply_chain)
        state.global_timeout = prefill_state.global_timeout

    try:
        state = prompt_target_agents(state, prompt)
        state = prompt_scope(state, prompt)
        state = prompt_features(state, prompt)

        if not state.features:
            clear_fn(state)
            print("No features selected — delegation cleared (equivalent to mode: main).")
            return 0

        if "review" in state.features:
            state = prompt_reviewer_primary(state, prompt)
            review_primary = state.reviewers[0].agent
            state = prompt_chain_model(state, "review", review_primary, prompt)
            state = prompt_default_arbiters(state, prompt)
            state = prompt_chain_fallback_loop(state, "review", prompt)

        if "apply" in state.features:
            state = prompt_apply_primary(state, prompt)
            apply_primary = state.apply_chain[0][0]
            state = prompt_chain_model(state, "apply", apply_primary, prompt)
            state = prompt_chain_fallback_loop(state, "apply", prompt)

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

    target = parsed.get("primary")
    if target and target in VALID_TARGET_AGENTS:
        state.target_agents = [target]

    if parsed.get("features"):
        state.features = parsed["features"]
    elif parsed.get("mode") and parsed["mode"] != "main":
        # Legacy: hybrid or delegated-apply → apply feature
        state.features = ["apply"]

    if parsed.get("reviewers"):
        state.reviewers = parsed["reviewers"]
    elif parsed.get("review_chain"):
        state.reviewers = [ReviewRoleEntry(agent=agent, persona=DEFAULT_REVIEWER_PERSONA, model=model) for agent, model in parsed["review_chain"][:1]]
    if parsed.get("arbiters"):
        state.arbiters = parsed["arbiters"]
    if parsed.get("apply_chain"):
        state.apply_chain = parsed["apply_chain"]
    elif parsed.get("sub_agent"):
        # Legacy: sub-agent → apply chain primary
        sub = parsed["sub_agent"]
        model = None
        models_dict = parsed.get("models") or {}
        if models_dict.get("sub"):
            model = models_dict["sub"]
        elif models_dict.get(sub):
            model = models_dict[sub]
        state.apply_chain = [(sub, model)]

    if parsed.get("scope"):
        state.scope = parsed["scope"]
    if parsed.get("global_timeout"):
        state.global_timeout = int(parsed["global_timeout"])
    return state


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
                kv = stripped.removeprefix("- ").strip()
                if ":" not in kv:
                    continue
                key, _, value = kv.partition(":")
                key = key.strip()
                value = value.strip()

                if key == "features":
                    result["features"] = [f.strip() for f in value.split(",") if f.strip()]
                elif key in ("review-chain", "apply-chain"):
                    result[_chain_key(key)] = _parse_chain_value(value)
                elif key == "reviewers":
                    from task_relay.review_config import parse_role_entries
                    result["reviewers"] = parse_role_entries(value)
                elif key == "arbiter":
                    from task_relay.review_config import parse_role_entries
                    result.setdefault("arbiters", [])
                    result["arbiters"].extend(parse_role_entries(value))
                elif key == "primary":
                    result["primary"] = value
                elif key == "mode":
                    result["mode"] = value
                elif key == "sub-agent":
                    result["sub_agent"] = value
                elif key == "scope":
                    result["scope"] = value
                elif key == "global-timeout":
                    result["global_timeout"] = int(value)

            # Parse models sub-block
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


def _chain_key(block_key: str) -> str:
    """Map 'review-chain' / 'apply-chain' to 'review_chain' / 'apply_chain'."""
    return block_key.replace("-", "_")


def _parse_chain_value(value: str) -> list[tuple[str, str | None]]:
    """Parse 'agent=model, agent' into [(agent, model_or_none), ...]."""
    chain: list[tuple[str, str | None]] = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" in entry:
            agent, _, model = entry.partition("=")
            agent = agent.strip()
            model_val = model.strip() or None
        else:
            agent = entry.strip()
            model_val = None
        if agent:
            chain.append((agent, model_val))
    return chain
