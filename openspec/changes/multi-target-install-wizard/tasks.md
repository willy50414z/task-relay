## 1. Wizard and CLI Shape

- [x] 1.1 Replace the singular primary-agent wizard state with multi-target install state and add a checkbox-style target selection prompt.
- [x] 1.2 Update `trly install` argument parsing and command handling so one install invocation can target Codex, Claude, or both with one shared configuration flow.
- [x] 1.3 Preserve the `main` mode short-circuit so clearing delegation runs once per selected target and exits before delegated prompts.

## 2. Configuration Persistence

- [x] 2.1 Remove primary model selection from the interactive wizard and non-interactive install model parsing.
- [x] 2.2 Update managed block rendering, parsing, and rewrite behavior to omit persisted primary model metadata while retaining delegated sub-agent model metadata.
- [x] 2.3 Update generated `task-relay-delegation` skill metadata so it no longer records a primary model field.

## 3. Prefill and Compatibility

- [x] 3.1 Implement multi-target prefill rules for single-target, matching dual-target, and conflicting dual-target existing installs.
- [x] 3.2 Ensure legacy managed blocks that contain primary model entries are parsed safely and rewritten without those entries.
- [x] 3.3 Keep target-specific install path resolution and result reporting deterministic for single-target and dual-target installs.

## 4. Verification and Docs

- [x] 4.1 [delegate:test] Add or update tests for target multi-select state transitions, shared configuration writes, `main` clear across multiple targets, and non-interactive target selection.
- [x] 4.2 [delegate:test] Add compatibility tests for legacy managed blocks with primary model metadata and for safe prefill fallback when target configs conflict.
- [x] 4.3 Update README install documentation and examples to describe multi-target selection, shared config behavior, and the removal of primary model configuration.
