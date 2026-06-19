## 1. Prompt Experience

- [x] 1.1 [codex-only] Choose the Python prompt dependency (`questionary` or `InquirerPy`) and add it to `pyproject.toml` with a short rationale in implementation notes.
- [x] 1.2 Implement a prompt adapter abstraction for select and confirm prompts, with a fake adapter suitable for unit tests.
- [x] 1.3 Replace numbered wizard prompts in `task_relay/wizard.py` with adapter-backed select prompts for primary agent, scope, mode, sub-agent, and models.
- [x] 1.4 Preserve complete non-interactive install behavior so fully specified flags bypass prompt imports and prompt execution.
- [x] 1.5 Add tests for keyboard-wizard state transitions using the fake prompt adapter.

## 2. Prefill and State Normalization

- [x] 2.1 [delegate:deepseek] Draft a helper that scans project and user guidance candidates for task-relay managed blocks and returns unambiguous existing configuration metadata.
- [x] 2.2 Normalize parsed model entries from agent-keyed metadata into role-keyed wizard state (`primary`, `sub`), including same-agent primary/sub scenarios.
- [x] 2.3 Update `handle_install()` to prefill `trly install` defaults from unambiguous existing configuration when no explicit primary/scope target is provided.
- [x] 2.4 Add tests for project prefill, user prefill, ambiguous-block fallback, and agent-keyed model normalization.

## 3. Path Resolution and Cleanup

- [x] 3.1 [codex-only] Audit all install, clear, and uninstall code paths and route guidance path plus skill root calculation through `resolve_install_paths()`.
- [x] 3.2 Fix main-mode clear so it removes only the managed block and skill bundle for the selected primary agent and scope.
- [x] 3.3 Fix user-scope uninstall and clear cleanup so user skill roots resolve to `~/.claude/skills` or `~/.codex/skills` without duplicated agent directories.
- [x] 3.4 Add tests for codex/claude user and project install, clear, and uninstall path behavior.

## 4. Skill Assets and Legacy Migration

- [x] 4.1 [delegate:deepseek] Rename packaged delegation assets from `openspec-deepseek-delegation` to `task-relay-delegation` and update package data expectations.
- [x] 4.2 Ensure installed `task-relay-delegation` bundles copy full implementation, test, review, and diagnosis templates from package assets instead of fallback stubs.
- [x] 4.3 Implement cleanup of legacy `openspec-deepseek-delegation` skill directories from the resolved skill root during install and uninstall.
- [x] 4.4 Add tests that assert full templates are installed and legacy skill directories are removed.

## 5. Verification and Documentation

- [x] 5.1 [delegate:test] Update CLI and wizard tests for non-TTY incomplete install failures, complete flag installs, prefill, main clear, and uninstall.
- [x] 5.2 Update README install documentation to describe arrow-key interaction, non-interactive flags, and exact user/project paths.
- [x] 5.3 Run the unit test suite with `pytest`.
- [x] 5.4 Run a manual smoke test for `trly install` in a temporary project, re-run prefill, `main` clear, and `trly uninstall`; document observed output in the final implementation summary.
