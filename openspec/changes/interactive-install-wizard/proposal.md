## Why

The current `trly install` is a CLI-flag-driven command that only supports project-scope delegation configuration with a hardcoded deepseek sub-agent. Users need an interactive setup wizard that guides them through scope, primary agent, delegation target, and model selection — producing appropriate guidance files and skill bundles for both Claude and Codex primary agents, at both user and project scope.

## What Changes

- **BREAKING**: Replace `trly install --mode/--level/--yes/--cwd` flags with an interactive wizard flow. Legacy flag-based invocation removed.
- **BREAKING**: Remove `~/.task-relay/config.yml` support. All configuration lives in managed blocks within guidance files.
- Add interactive wizard prompts for: primary agent → scope → mode → sub-agent → model.
- Primary agent selection determines guidance file name: `CLAUDE.md` (claude) or `AGENTS.md` (codex).
- Scope determines output location: `~/.claude/` or `~/.codex/` (user) vs `./` (project).
- Mode `main` clears the managed block and exits immediately — no sub-agent or model prompts.
- Mode `hybrid` and `delegated-apply` continue to sub-agent selection (claude/codex/deepseek).
- Model catalog hardcoded in source with GitHub Action to periodically update from official model APIs.
- Managed guidance block and skill bundle content dynamically generated from user selections.
- Skill bundle renamed from `openspec-deepseek-delegation` to `task-relay-delegation` and generalized for any sub-agent.
- `trly uninstall` detects primary agent from existing managed block to determine correct file paths.

## Capabilities

### New Capabilities

- `install-wizard`: Interactive terminal wizard for `trly install` with sequential prompts for primary agent, scope, delegation mode, sub-agent, and model selection.
- `model-catalog`: Hardcoded model registry for Claude and Codex models with GitHub Action periodic update workflow.
- `dynamic-guidance-generation`: Template-driven generation of managed guidance blocks and skill bundles from user selections.

### Modified Capabilities

- `openspec-delegation-install`: Replaced entirely. Guided install/uninstall behavior replaced by the wizard. Uninstall still functions but must detect primary agent from existing managed block content.

## Impact

- `task_relay/cli/__init__.py` — major rewrite of `handle_install`, `handle_uninstall`, `resolve_mode`, argument parser
- `task_relay/delegation.py` — full rewrite: dynamic block generation, skill bundle generation, managed block detection
- `task_relay/config.py` — removed
- `.github/workflows/publish.yml` — add model catalog update workflow
- `pyproject.toml` — remove `agent-dispatch` compat entry point (already deprecated, end of migration window)
