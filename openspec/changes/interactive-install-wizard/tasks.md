## 1. Model catalog

- [x] 1.1 Create `task_relay/models.py` with `ModelInfo` dataclass and hardcoded `CLAUDE_MODELS`, `CODEX_MODELS`, `DEEPSEEK_MODELS` lists
- [x] 1.2 Add `get_catalog(agent_name)` and `format_model_choices(catalog)` functions
- [x] 1.3 Create `.github/workflows/update-models.yml` with weekly schedule and `workflow_dispatch` trigger

## 2. Wizard state and prompts

- [x] 2.1 Create `task_relay/wizard.py` with `WizardState` dataclass
- [x] 2.2 Implement `prompt_primary_agent()` step function
- [x] 2.3 Implement `prompt_scope()` step function
- [x] 2.4 Implement `prompt_mode()` step function (returns early if main)
- [x] 2.5 Implement `prompt_sub_agent()` step function
- [x] 2.6 Implement `prompt_model(agent_name, catalog)` step function
- [x] 2.7 Implement `confirm_and_write(state)` summary display and confirmation
- [x] 2.8 Implement `run_wizard()` orchestrator that chains all steps
- [x] 2.9 Implement `prefill_from_existing(path)` to parse existing managed block and seed state

## 3. Path resolution

- [x] 3.1 Implement `resolve_install_paths(primary, scope, cwd)` function returning `(guidance_path, skill_root)`
- [x] 3.2 Implement `detect_managed_blocks(scope)` for uninstall auto-detection

## 4. Managed block generation

- [x] 4.1 Rewrite `build_guidance_block()` in `task_relay/delegation.py` to accept `WizardState` and generate dynamic content
- [x] 4.2 Implement policy template functions for each mode (main, hybrid, delegated-apply)
- [x] 4.3 Update marker constants from `task-relay:openspec-delegation` to `task-relay`
- [x] 4.4 Implement `_replace_managed_block()` with new marker format and legacy marker detection
- [x] 4.5 Implement `parse_existing_block(path)` to extract primary, mode, sub-agent, models from an existing block

## 5. Skill bundle generation

- [x] 5.1 Rename skill from `openspec-deepseek-delegation` to `task-relay-delegation`
- [x] 5.2 Create generalized `SKILL.md` template with `{primary}`, `{sub_agent}`, `{model}` placeholders
- [x] 5.3 Implement `_install_skill_bundle()` that accepts sub-agent parameter and writes appropriate agent config
- [x] 5.4 Add agent config files for claude (new) and codex (existing openai.yaml)
- [x] 5.5 Implement `_remove_skill_bundle()` that finds and removes `task-relay-delegation` directory

## 6. CLI rewrite

- [x] 6.1 Rewrite `handle_install()` in `task_relay/cli/__init__.py` to launch wizard or parse non-interactive flags
- [x] 6.2 Update install argument parser: add `--primary`, `--scope`, `--sub-agent`, `--model`; remove `--mode`, `--level`, `--yes`
- [x] 6.3 Keep `--cwd` as optional override
- [x] 6.4 Rewrite `handle_uninstall()` to auto-detect scope and primary agent
- [x] 6.5 Update uninstall argument parser: add `--scope`, keep `--cwd`
- [x] 6.6 Remove `resolve_mode()` and `LEVEL_TO_MODE` mapping
- [x] 6.7 Remove `handle_compat_install()` and compat command support

## 7. Remove config.yml support

- [x] 7.1 Delete `task_relay/config.py`
- [x] 7.2 Remove `config_path` parameter from `run()`, `evaluate()`, `evaluate_result()` in `task_relay/core.py`
- [x] 7.3 Remove `config_path` parameter from `resolve()`, `check_target()`, `check_all()` in `task_relay/agents/__init__.py`
- [x] 7.4 Update `_run_with_fallback()` to not pass `config_path`
- [x] 7.5 Update CLI handlers to not reference config_path

## 8. Remove agent-dispatch compat

- [x] 8.1 Remove `agent-dispatch` entry point from `pyproject.toml`
- [x] 8.2 Remove `compat_main()` and `compat_build_parser()` from `task_relay/cli/__init__.py`

## 9. Tests

- [x] 9.1 Add tests for `WizardState` and step functions in `tests/test_wizard.py`
- [x] 9.2 Add tests for model catalog access and formatting in `tests/test_models.py`
- [x] 9.3 Add tests for path resolution in `tests/test_delegation.py`
- [x] 9.4 Add tests for dynamic managed block generation with all mode/agent combinations
- [x] 9.5 Add tests for legacy marker migration
- [x] 9.6 Add tests for managed block parsing (prefill_from_existing)
- [x] 9.7 Add tests for skill bundle generation with different sub-agents
- [x] 9.8 Add tests for uninstall auto-detection of primary agent
- [x] 9.9 Update existing CLI tests for new install/uninstall behavior in `tests/test_cli.py`
- [x] 9.10 Add tests for non-interactive flag mode
- [x] 9.11 Remove config-related test cases from `tests/test_config.py`

## 10. Cleanup

- [x] 10.1 Remove `agreement` script block from existing AGENTS.md if present (no longer relevant — no AGENTS.md at repo root)
- [x] 10.2 Update `README.md` to reflect new install flow and remove config.yml references
- [x] 10.3 Remove `AGENTS.md` if it exists at repo root and is no longer needed (no AGENTS.md at repo root)
