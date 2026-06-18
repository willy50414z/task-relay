## 1. Project Skeleton and Migration Boundary

- [ ] 1.1 Initialize `pyproject.toml` for distribution `task-relay` version `0.2.0`, Python `>=3.11`, package discovery for `task_relay*` and compatibility `llm_eval*`, and console scripts `trly` plus transitional `agent-dispatch`; verify with `python -m pip install -e .`.
- [x] 1.2 Create package directories `task_relay/`, `task_relay/agents/`, `task_relay/cli/`, `llm_eval/`, and `tests/`; verify imports do not fail with `python -c "import task_relay"`.
- [x] 1.3 Copy existing behavior from `E:/code/agent_cli_dispatcher` as read-only reference only; do not modify that source repository.
- [x] 1.4 Add baseline README with new install command, new imports, new CLI examples, migration notes, and explicit v0.2 non-goals.

## 2. Core Execution Implementation

- [x] 2.1 Implement `task_relay/types.py` with frozen `Outcome`, `JobResult`, `TargetStatus`, `AgentRunRequest`, and `AgentRunResult`; verify with unit tests for defaults and byte file payloads.
- [x] 2.2 Implement `task_relay/errors.py` with `TaskRelayError`, `AgentNotFoundError`, `AgentExecutionError`, `AgentTimeoutError`, `AgentQuotaError`, `OutcomeResolutionError`, and `ConfigError`; verify specific exception imports.
- [x] 2.3 Implement `task_relay/workspace.py` using `.task_relay/<job_id>/` workspaces and `TASK_RELAY_KEEP_IO=1` retention; verify cleanup on success and failure.
- [x] 2.4 Implement `task_relay/prompt.py` to build output-file instructions with absolute workspace paths; verify declared output-file prompt content.
- [x] 2.5 Implement `task_relay/resolver.py` to resolve `status_*` files, handle missing status through `error` outcome, reject unknown status, reject missing declared files, and warn on multiple status files; verify every shadow path.
- [ ] 2.6 Implement `task_relay/core.py` with `run()` and `evaluate()` orchestration, ordered fallback, callback invocation, `on_exception`, duration tracking, and workspace cleanup; verify all scenarios in `task-execution-core`.

## 3. Agent Adapter Registry and Config

- [ ] 3.1 Implement `task_relay/agents/base.py` with the runner protocol and helper types; verify core code depends on the protocol rather than concrete adapters.
- [ ] 3.2 Implement `task_relay/agents/claude.py` with Windows `.cmd` binary resolution, stdin prompt delivery, `--print`, `--dangerously-skip-permissions`, model override, health check, and typed subprocess errors.
- [ ] 3.3 Implement `task_relay/agents/codex.py` with stdin prompt delivery, `codex exec`, sandbox bypass flags matching existing behavior, model override, reasoning effort config, health check, and typed subprocess errors.
- [ ] 3.4 Implement `task_relay/agents/deepseek.py` using the Claude CLI plus Anthropic-compatible DeepSeek environment variables, token validation, default model, subagent model, effort default, health behavior, and typed subprocess errors.
- [ ] 3.5 Implement quota/rate-limit detection shared by adapters and map quota failures to `AgentQuotaError`; verify common 429/quota strings.
- [x] 3.6 Implement `task_relay/config.py` to load `~/.task-relay/config.yml`, tolerate missing config, validate known fields, apply defaults, reject unsupported `type: opencli`, and expose deterministic precedence rules.
- [x] 3.7 Implement `task_relay/agents/__init__.py` registry with built-in resolution, config-aware defaults, unknown-agent errors, and no core enum branching; verify all scenarios in `agent-adapter-registry`.

## 4. Public API and CLI

- [x] 4.1 Implement `task_relay/__init__.py` public API exports: `evaluate`, `run`, `Outcome`, `JobResult`, `TargetStatus`, errors, and health helpers.
- [x] 4.2 Implement `task_relay/cli/__init__.py` parser and `main()` with subcommands `run`, `evaluate`, `health`, `install`, and `uninstall`; verify `trly --help` and subcommand help.
- [x] 4.3 Implement `task_relay/cli/run.py` input loading from `--prompt`, `--prompt-file`, and `--stdin`, target parsing, library dispatch, stdout-only success, and stderr diagnostics on failure.
- [x] 4.4 Implement `task_relay/cli/evaluate.py` purpose input loading, `STATUS=DESCRIPTION` outcome parsing, `STATUS=PATH` output-file parsing, JSON serialization, and argument validation.
- [x] 4.5 Implement `task_relay/cli/health.py` for all-agent and single-agent JSON health output using registry-resolved adapters.
- [x] 4.6 Implement exit code behavior: `0` success, `1` runtime failure, `2` argument or validation failure; verify with CLI tests.

## 5. OpenSpec Delegation and Compatibility

- [x] 5.1 Port OpenSpec guidance installer to `task_relay/delegation.py` with task-relay managed block markers and command examples using `trly`.
- [x] 5.2 Implement `trly install --mode <main|hybrid|delegated-apply> --cwd <project> [--yes]` and `trly uninstall --cwd <project>`; verify create, update-in-place, uninstall, and preserve-surrounding-text behavior.
- [x] 5.3 Implement compatibility `llm_eval/__init__.py` shim that re-exports supported public API and emits `DeprecationWarning`; verify legacy imports.
- [x] 5.4 Implement compatibility console behavior for `agent-dispatch`, including `install_delegant`, `--level` mapping, and stderr deprecation warning; verify old command routes to new implementation.
- [x] 5.5 Document planned compatibility removal version in README and warning messages.

## 6. Test Coverage and Release Readiness

- [ ] 6.1 Port existing test coverage from the source repository into `tests/` under the new package names and update expected command names.
- [x] 6.2 Add `tests/test_config.py` for missing config, config defaults, CLI override precedence, invalid config, and unsupported `opencli` rejection.
- [x] 6.3 Add `tests/test_agent_registry.py` for built-in resolution, unknown agent errors, configured defaults, and no enum dependency in core paths.
- [ ] 6.4 Add adapter subprocess tests for Claude, Codex, and DeepSeek command construction, env mutation, stdin behavior, timeout handling, quota errors, and non-zero exit diagnostics.
- [ ] 6.5 Add core chaos tests for missing status, unknown status, multiple statuses, missing output files, callback exception cleanup, all-fallbacks-fail, and `TASK_RELAY_KEEP_IO=1`.
- [x] 6.6 Run `pytest` and fix all failures before marking implementation complete.
- [ ] 6.7 Run `python -m build` or equivalent packaging verification and inspect wheel metadata for `task-relay`, `trly`, and transitional `agent-dispatch`.
- [ ] 6.8 Perform a manual smoke test with mocked subprocesses or installed local CLIs for `trly run`, `trly evaluate --json`, `trly health --json`, `trly install`, and legacy `agent-dispatch`.
