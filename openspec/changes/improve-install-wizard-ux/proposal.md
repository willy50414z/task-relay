## Why

The current `trly install` wizard is interactive only in the narrow sense that it asks numbered questions; it does not provide the arrow-key selection experience users expect from `openspec init`. Re-running or uninstalling the installer also exposes path and state-management issues that can leave stale skill bundles or fallback templates in place.

## What Changes

- Replace numbered `input()` prompts with a terminal select experience that supports up/down navigation and Enter selection for primary agent, scope, mode, sub-agent, model, and confirmation.
- Preserve scriptable non-interactive installs through explicit flags.
- Auto-detect existing managed blocks for prefill when `trly install` is run without flags.
- Normalize model state so prefilled defaults correctly map to primary and sub-agent roles.
- Fix user/project guidance and skill path cleanup so install, main-mode clear, and uninstall all target the same paths.
- Rename packaged assets from the old `openspec-deepseek-delegation` identity to `task-relay-delegation` and install the full templates instead of fallback stubs.
- Remove or migrate stale legacy `openspec-deepseek-delegation` project skill bundles when installing the new skill bundle.

## Capabilities

### New Capabilities

- `keyboard-install-wizard`: Keyboard-driven install wizard behavior, including interactive select prompts, prefill, confirmation, and non-interactive fallback.
- `delegation-install-paths`: Deterministic guidance-file and skill-bundle path resolution for install, clear, uninstall, and legacy skill cleanup.

### Modified Capabilities

- None.

## Impact

- Affected code: `task_relay/wizard.py`, `task_relay/cli/__init__.py`, `task_relay/delegation.py`, `task_relay/models.py` display helpers, and package assets under `task_relay/assets/`.
- Tests: wizard prompt abstraction tests, delegation path tests, CLI install/uninstall tests, and asset/template installation tests.
- Dependencies: likely add one Python TTY prompt dependency such as `questionary` or `InquirerPy`; keep non-interactive mode dependency-light and CI-safe.
