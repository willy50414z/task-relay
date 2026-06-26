## Context

The current task-relay delegation model has two roles: primary (orchestrator) and sub-agent (bounded delegated work). Delegation modes are `main` (no delegation), `hybrid` (partial delegation), and `delegated-apply` (full apply delegation). The sub-agent handles implementation drafts, tests, review, and diagnosis.

Users now need a **review agent** role specifically for the propose phase — reviewing proposals for clarity, correctness, and completeness before implementation begins. The review agent and the apply agent should be independently configurable with their own fallback chains.

The managed block format (`primary`, `mode`, `sub-agent`, `models`) and the install wizard (5 steps) were not designed for this multi-role, multi-chain configuration.

## Goals / Non-Goals

**Goals:**

- Support three agent roles: primary (path selector only), review agent, apply agent.
- Allow users to independently enable/disable review and apply features during `trly install`.
- Support ordered fallback chains for each feature, with per-agent model selection.
- Provide a `review-proposal.md` prompt template for the primary agent to use when calling the review agent.
- Maintain backward compatibility: legacy `mode`/`sub-agent` managed blocks are parsed and upgraded to the new format.
- Keep the wizard interactive experience consistent with existing keyboard-driven selection patterns (select, checkbox, confirm).

**Non-Goals:**

- No change to the runtime fallback mechanism in `core.py` — `_run_with_fallback` already supports ordered target lists.
- No change to the agent runner architecture — runners remain CLI subprocess wrappers.
- No removal of the `mode`/`sub-agent` parsing paths — they are preserved for backward compatibility, not removed.
- No web relay or async queue integration.

## Decisions

### Decision 1: Chain format — `agent=model, agent=model`

The managed block uses a comma-separated chain syntax where each entry is `agent=model` (or just `agent` for default model):

```markdown
- review-chain: claude=claude-sonnet-4-6, deepseek=deepseek-v4-pro[1m], codex=gpt-5.5-medium
- apply-chain: deepseek=deepseek-v4-pro[1m], codex
```

The first entry is the primary agent for that chain; subsequent entries are fallbacks in priority order.

**Alternatives considered:**

- Nested YAML-like sub-blocks (e.g., `- review:`, then indented `- agent:`, `- model:`, `- fallback:`): More verbose, harder to parse in the current line-by-line parser, and visually heavier in the guidance file.
- Separate `- review-model` and `- review-fallback` entries: Would not express per-agent model selection or fallback ordering as cleanly.

**Rationale:** The flat `chain` format is parseable by extending the existing `parse_existing_block()` line-by-line logic with one new parsing rule. It's human-readable in the guidance file and unambiguous.

### Decision 2: Primary agent is path-only, no model selection

The primary agent (`claude` or `codex`) determines only:
- The guidance file path (`AGENTS.md` vs `CLAUDE.md`)
- The skill bundle root (`.codex/skills` vs `.claude/skills`)

Primary agent does NOT have a model selection step in the wizard. Model selection is only for review and apply chains.

**Rationale:** The primary agent is not a runtime execution target — it's the orchestrator that reads the guidance file. The review and apply agents are the ones being invoked via `trly run --target <agent> --prompt-file <packet>`.

### Decision 3: Feature checkbox instead of mode select

Replace the current `mode` select (main/hybrid/delegated-apply) with a `features` checkbox:

```
[ ] Review 功能
[ ] Apply 功能
```

- Both unchecked → no delegation (equivalent to `mode: main`)
- Review only → only `review-chain` is configured
- Apply only → only `apply-chain` is configured
- Both → both chains are configured

**Alternatives considered:**

- Keep `mode` and add a separate features step: Redundant — `mode` becomes derivable from features.
- Radio-style single choice (review OR apply OR both OR none): Less flexible than independent checkboxes.

**Rationale:** Checkboxes naturally express independent enable/disable. The current `mode` concept maps cleanly: `main` = neither checked, `hybrid`/`delegated-apply` = apply checked (with or without review).

### Decision 4: Fallback selection as a loop, not a multi-select

The fallback selection uses a confirm loop pattern:
1. Show current chain state
2. Ask "Add fallback agent?" (confirm y/n)
3. If yes: select agent (excluding already-selected), select model
4. Repeat until user says no or all agents exhausted

**Alternatives considered:**

- Single checkbox for all fallback agents: Cannot express priority ordering.
- Numbered ranking: Complex UX for 2-3 agents.

**Rationale:** The loop naturally records priority order (first added = highest priority), shows the user the chain as it's built, and works well with the existing `select` + `confirm` prompt primitives.

### Decision 5: WizardState expansion — flat fields over nested dataclass

```python
@dataclass
class WizardState:
    target_agents: list[str]           # ["claude", "codex"]
    scope: str | None                  # "user" | "project"
    features: list[str]                # ["review", "apply"] or []

    # Review chain
    review_chain: list[tuple[str, str | None]]  # [(agent, model_or_none), ...]

    # Apply chain
    apply_chain: list[tuple[str, str | None]]   # [(agent, model_or_none), ...]

    cwd: Path
```

`review_chain` and `apply_chain` are lists of `(agent, model_or_none)` tuples. The first entry is the primary agent for the chain; subsequent entries are fallbacks. `model_or_none` is `None` when the user accepts the default model.

**Alternatives considered:**

- Nested `ChainConfig` dataclass: Cleaner in isolation but adds friction in wizard step functions that return new `WizardState` copies.
- Keep existing `models: dict` alongside chains: The `agent=model` encoding in the chain entries already captures model information.

**Rationale:** Flat fields in `WizardState` follow the existing pattern. The tuple list is simple to copy (`list(state.review_chain)`) and iterate. The managed block serializer handles the `(agent, model)` → `"agent=model"` encoding.

### Decision 6: Backward-compatible parsing and auto-upgrade

`parse_existing_block()` gains new parsing rules for `features`, `review-chain`, and `apply-chain` while preserving existing `mode`/`sub-agent`/`models` rules.

Legacy mapping:
```
mode: main              → features: (empty)
mode: hybrid            → features: apply, apply-chain extracted from sub-agent + models
mode: delegated-apply   → features: apply, apply-chain extracted from sub-agent + models
```

When a legacy block is parsed and the wizard is launched interactively, the prefill maps legacy values to the new format. On save, the new format is written — effectively upgrading the managed block.

**Rationale:** Users upgrading task-relay should not need to manually migrate their managed blocks. The first interactive `trly install` after upgrade will prefill from legacy values and write the new format.

### Decision 7: Review-proposal template as skill bundle asset

The `review-proposal.md` template is packaged as a skill bundle asset alongside existing templates. It defines:
- Review dimensions (requirement clarity, direction correctness, plan completeness, user intent)
- Output specification (`spec/delegent_review.md`)
- Interaction boundaries (ask user on ambiguity, don't modify OpenSpec state)
- Tool permissions (may use gstack skills)

The template location is `task_relay/assets/task-relay-delegation/templates/review-proposal.md`.

**Rationale:** Bundling with the skill ensures the template is available to the primary agent regardless of which primary agent target is configured.

## Risks / Trade-offs

- **Wizard complexity grew significantly** (from 5 steps to up to ~12 with conditionals): Mitigation — the steps are logically grouped (target → scope → features → review chain → apply chain → confirm). The existing prompt adapter abstraction keeps each step testable independently.
- **Managed block line count increased**: Mitigation — the block remains under 15 lines for typical configurations. The `chain` format compresses what would otherwise be 6-8 lines into 1-2.
- **Legacy format parsing may miss edge cases**: Mitigation — all existing test fixtures for `parse_existing_block` are preserved and extended with new format test cases before any parser changes.
- **Fallback chain may reference unavailable agents**: Mitigation — health check output already reports agent availability. The wizard only offers agents available in the registry.
- **Backward compat with very old blocks** (pre-`task-relay:start` marker): Mitigation — the legacy marker `task-relay:openspec-delegation:start` is still recognized by the parser.
