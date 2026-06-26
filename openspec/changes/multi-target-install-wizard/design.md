## Context

`trly install` currently models installation around a single `primary_agent` value that drives wizard prompts, path resolution, managed block rendering, and generated skill metadata. That shape matches one-target installs, but it makes two new UX requirements awkward:

- The wizard should let the user select both Codex and Claude targets in one run.
- The install flow should stop asking for and persisting a primary model that is not required for target selection or delegated execution.

This change crosses the wizard, CLI parsing, guidance generation, and prefill logic. It also changes the persisted managed block format, so the design needs to define compatibility behavior for existing installs.

## Goals / Non-Goals

**Goals:**
- Replace the single-target primary-agent wizard step with a keyboard-driven multi-select target step.
- Apply one shared install configuration (`scope`, `mode`, `sub-agent`, `sub-agent model`) to every selected target.
- Remove primary model selection and primary model persistence from interactive and non-interactive install paths.
- Keep install path resolution deterministic per target agent and preserve existing clear/uninstall semantics.
- Allow re-running the wizard against an existing install without restoring obsolete primary-model state.

**Non-Goals:**
- Support different mode, sub-agent, or model settings per selected target within the same install run.
- Generalize install targets beyond the existing `codex` and `claude` environments.
- Change delegated runtime selection outside the install/configuration workflow.
- Redesign uninstall into a multi-select flow as part of this change.

## Decisions

### D1: Treat the first wizard step as target selection, not primary selection

The first interactive step becomes a checkbox-style prompt that returns one or more install targets:

```text
Select installation targets:
[ ] codex
[ ] claude

Space toggles, Enter submits
```

Internally, wizard state should store `target_agents: list[str]` instead of a singular `primary_agent`. Install execution iterates over that list and performs one write per target using the same shared configuration.

Rationale: this matches the requested UX directly and avoids overloading the term "primary" with batch-install semantics it no longer represents.

Alternative considered: keep the single-select primary prompt and add a later "install for both" confirmation. Rejected because it preserves misleading terminology and complicates prefill/update rules.

### D2: Keep configuration shared across selected targets

After target selection, the wizard asks for `scope`, `mode`, `sub-agent`, and `sub-agent model` exactly once. The resulting configuration is applied to every selected target agent.

If the mode is `main`, the clear operation should run for each selected target and then exit without asking for sub-agent or model details.

Rationale: the user explicitly wants Codex and Claude to share one configuration. A single shared flow keeps the wizard short and avoids target-by-target branching.

Alternative considered: prompt separately per target after the multi-select step. Rejected because it negates most of the UX gain and creates mixed-config edge cases that are not requested.

### D3: Remove primary model from the configuration contract

Primary model selection is removed from:

- the interactive wizard
- `trly install --model ...` role handling for primary
- managed block `models:` output
- generated skill metadata summaries
- prefill state restoration

The persisted configuration keeps only the sub-agent model, keyed by delegated role or agent as needed by the installer implementation.

Rationale: the install target determines file paths and guidance location; delegated execution is the part that still benefits from an explicit model choice. Removing primary model persistence aligns the stored contract with actual install behavior.

Alternative considered: stop prompting for primary model but continue writing the default primary model implicitly. Rejected because it retains unused state and makes future prefill behavior harder to reason about.

### D4: Preserve target-specific path resolution and write independently per target

`resolve_install_paths(agent, scope, cwd)` remains the single source of truth for path calculation. Multi-target install is implemented as a loop over selected agents:

1. Resolve guidance path and skill root for each target.
2. Render the managed block for that target.
3. Write or update the guidance file.
4. Install or refresh the target-local skill bundle.

This preserves the current Codex/Claude file layout:

- Codex project: `<cwd>/AGENTS.md` and `<cwd>/.codex/skills`
- Claude project: `<cwd>/CLAUDE.md` and `<cwd>/.claude/skills`

Rationale: batching should compose existing target-specific install behavior, not replace it with a new storage model.

Alternative considered: write one combined config file that covers both agents. Rejected because the repo already uses agent-specific guidance files and skill roots.

### D5: Prefill should derive shared defaults from selected or unambiguous installs

Prefill behavior should continue only when existing configuration can be interpreted safely:

- If exactly one install target has an existing managed block, its scope/mode/sub-agent/sub-model seed defaults.
- If both targets already have managed blocks and their shared fields match, those shared values seed defaults and both targets can be preselected.
- If both targets exist but conflict, the wizard should fall back to safe defaults for shared fields and let the user choose targets explicitly.

Primary model values from older managed blocks must be ignored during parsing.

Rationale: multi-target batch install needs deterministic defaults, but it should not guess across divergent existing target configs.

## Risks / Trade-offs

- Existing code and tests assume a singular `primary_agent` state shape → Mitigation: introduce explicit `target_agents` naming at the wizard boundary and adapt downstream install APIs deliberately instead of carrying dual semantics.
- Old managed blocks may still contain primary model entries → Mitigation: keep parsing backward-compatible but drop those fields during normalization and rewrite.
- Multi-target writes can partially succeed if one target path fails → Mitigation: define install result reporting per target and ensure failures surface clearly instead of pretending the batch fully succeeded.
- Shared configuration across targets limits flexibility → Mitigation: document that mixed Codex/Claude configs still require separate install runs.

## Migration Plan

1. Introduce multi-target wizard state and checkbox prompt support.
2. Update CLI install handling to accept and execute batched target installs.
3. Remove primary model role parsing and persistence from install flows.
4. Adjust managed block rendering and skill metadata generation to omit primary model.
5. Update prefill logic to ignore legacy primary-model entries and derive shared defaults safely.
6. Add tests for single-target and dual-target interactive/non-interactive installs, plus legacy-block rewrite behavior.
7. Update README examples and wizard interaction documentation.

Rollback: revert the wizard to single-target selection and keep parsing legacy managed blocks. Existing installs remain recoverable because target-specific guidance paths do not change.

## Open Questions

- Should non-interactive multi-target install use repeated `--primary` flags, a new `--targets` flag, or both?
- Should a conflicting prefill across Codex and Claude preselect both targets but blank shared defaults, or should it preselect nothing?
