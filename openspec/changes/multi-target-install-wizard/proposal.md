## Why

`trly install` currently treats the primary orchestration agent as a single interactive choice and persists a primary model selection that is not needed to determine install targets. That creates extra prompt friction and prevents a single wizard run from installing the same delegation configuration for both Codex and Claude environments.

## What Changes

- Replace the single-select primary agent prompt with a multi-select install target prompt that supports Space to toggle agents and Enter to submit.
- Let one interactive install session write the same scope, mode, sub-agent, and sub-agent model configuration to every selected target agent.
- Remove primary model selection from the wizard, non-interactive install contract, managed block output, and generated skill metadata.
- Preserve existing non-interactive install and clear/uninstall behavior while extending install to support multiple target agents in one invocation.
- Update prefill behavior so existing installs seed shared defaults without reintroducing persisted primary model state.

## Capabilities

### New Capabilities

- `multi-target-install-wizard`: Keyboard-driven multi-target install flow, shared configuration application, and target-aware prefill behavior for `trly install`.
- `delegation-config-without-primary-model`: Managed block and skill-bundle configuration that no longer persists a primary model while preserving delegated sub-agent model selection.

### Modified Capabilities

- None.

## Impact

- Affected code: `task_relay/wizard.py`, `task_relay/cli/__init__.py`, `task_relay/delegation.py`, and install-related tests/documentation.
- CLI/API impact: `trly install` interactive behavior changes, and non-interactive model flags no longer include a persisted primary-model role.
- Data impact: managed blocks and generated `task-relay-delegation` skill bundles stop writing primary model metadata.
