"""Interactive install wizard for trly install."""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from task_relay.models import (
    get_catalog,
    find_model_by_index,
    format_model_choices,
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


def _prompt_numbered(prompt: str, options: list[str], default_value: str | None = None) -> str:
    """Display a numbered list of options and return the selected value."""
    default_index = 1
    if default_value:
        for i, opt in enumerate(options, start=1):
            if opt == default_value:
                default_index = i
                break

    print()
    print(prompt)
    print()
    for i, opt in enumerate(options, start=1):
        label = _OPTION_LABELS.get(opt, opt)
        marker = " (*)" if opt == default_value else "    "
        print(f"  {marker} [{i}] {opt} — {label}")
    print()

    if not sys.stdin.isatty():
        raise RuntimeError("stdin is not a TTY; use non-interactive flags for scripting")

    while True:
        raw = input(f"Choice [1-{len(options)}, default {default_index}]: ").strip()
        if not raw:
            return options[default_index - 1]
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print(f"Invalid. Enter a number 1-{len(options)}.")


def prompt_primary_agent(state: WizardState) -> WizardState:
    options = list(VALID_PRIMARY_AGENTS)
    default = state.primary_agent or "codex"
    choice = _prompt_numbered("Select primary orchestration agent:", options, default_value=default)
    return WizardState(
        primary_agent=choice,
        scope=state.scope,
        mode=state.mode,
        sub_agent=state.sub_agent,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_scope(state: WizardState) -> WizardState:
    options = list(VALID_SCOPES)
    default = state.scope or "project"
    choice = _prompt_numbered("Select installation scope:", options, default_value=default)
    return WizardState(
        primary_agent=state.primary_agent,
        scope=choice,
        mode=state.mode,
        sub_agent=state.sub_agent,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_mode(state: WizardState) -> WizardState | None:
    options = list(VALID_MODES)
    default = state.mode or "hybrid"
    choice = _prompt_numbered("Select delegation mode:", options, default_value=default)
    if choice == "main":
        state.mode = "main"
        return None
    return WizardState(
        primary_agent=state.primary_agent,
        scope=state.scope,
        mode=choice,
        sub_agent=state.sub_agent,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_sub_agent(state: WizardState) -> WizardState:
    options = list(VALID_SUB_AGENTS)
    default = state.sub_agent or "deepseek"
    choice = _prompt_numbered("Select sub-agent for delegated work:", options, default_value=default)
    return WizardState(
        primary_agent=state.primary_agent,
        scope=state.scope,
        mode=state.mode,
        sub_agent=choice,
        models=dict(state.models),
        cwd=state.cwd,
    )


def prompt_model(agent_name: str, role_key: str, role_label: str, state: WizardState) -> WizardState:
    catalog = get_catalog(agent_name)
    existing = state.models.get(role_key)
    default_id = existing or get_default_model(agent_name)
    default_index = 1
    for i, m in enumerate(catalog, start=1):
        if m.id == default_id:
            default_index = i
            break

    print()
    print(f"Select model for {role_label} ({agent_name}):")
    print(format_model_choices(catalog))
    print()

    if not sys.stdin.isatty():
        raise RuntimeError("stdin is not a TTY; use non-interactive flags for scripting")

    while True:
        raw = input(f"Choice [1-{len(catalog)}, default {default_index}]: ").strip()
        if not raw:
            model = find_model_by_index(catalog, default_index)
            break
        try:
            idx = int(raw)
            model = find_model_by_index(catalog, idx)
            break
        except ValueError:
            pass
        except IndexError:
            pass
        print(f"Invalid. Enter a number 1-{len(catalog)}.")

    new_models = dict(state.models)
    new_models[role_key] = model.id
    return WizardState(
        primary_agent=state.primary_agent,
        scope=state.scope,
        mode=state.mode,
        sub_agent=state.sub_agent,
        models=new_models,
        cwd=state.cwd,
    )


def confirm_and_write(state: WizardState, write_fn: Callable[[WizardState], None]) -> bool:
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

    if not sys.stdin.isatty():
        write_fn(state)
        return True

    response = input("Write configuration? [Y/n]: ").strip().lower()
    if response in ("y", "yes", ""):
        write_fn(state)
        print("Configuration written.")
        return True
    print("Aborted.")
    return False


def run_wizard(
    write_fn: Callable[[WizardState], None],
    clear_fn: Callable[[], None],
    cwd: Path | None = None,
    prefill_path: str | None = None,
) -> int:
    state = WizardState(cwd=Path(cwd) if cwd else Path.cwd())

    if prefill_path:
        state = prefill_from_existing(Path(prefill_path), state)

    try:
        state = prompt_primary_agent(state)
        state = prompt_scope(state)

        result = prompt_mode(state)
        if result is None:
            clear_fn()
            print("Delegation cleared (mode: main).")
            return 0
        state = result

        state = prompt_sub_agent(state)

        # Primary agent model
        state = prompt_model(state.primary_agent, "primary", "primary", state)
        # Sub-agent model
        state = prompt_model(state.sub_agent, "sub", "sub-agent", state)

        if confirm_and_write(state, write_fn):
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
        state.models = parsed["models"]
    if parsed.get("scope"):
        state.scope = parsed["scope"]
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
