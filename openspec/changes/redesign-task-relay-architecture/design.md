## Context

This change migrates the existing `agent-cli-dispatcher` idea into a new `task-relay` project at `E:/code/task-relay`. The current implementation has proven the product shape: callers can run raw prompts through local agent CLIs, or run outcome-routed evaluations where the agent writes status files and declared output files into an isolated workspace.

The current architecture is too centered on `LLMTarget` and a single runner function. Adding or changing agents currently requires edits across target parsing, subprocess command construction, environment setup, health checks, CLI choices, tests, and documentation. The new design keeps the synchronous local-process model, but moves target-specific behavior behind agent adapters.

Current pressure points:

- `llm_svc.run()` owns command construction, env mutation, quota retry, temp I/O, subprocess execution, and target branching.
- `cli.py` parses arguments and also contains evaluation orchestration, fallback, JSON serialization, and install flow dispatch.
- `LLMTarget` is a closed enum, which conflicts with user-configured agents and future web relay adapters.
- Error handling is mostly one exception type, which makes user-facing diagnostics and retry decisions less precise than they should be.

Target architecture:

```text
             Python API                         CLI
      task_relay.evaluate/run             trly run/evaluate
                │                                │
                └──────────────┬─────────────────┘
                               ▼
                     task_relay.core/service
              TaskRequest, OutcomeSpec, JobResult
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
       workspace.py        prompt.py         resolver.py
        create/clean      output contract     status files
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                     agents.resolve(name)
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
     ClaudeRunner         CodexRunner        DeepSeekRunner
     command/env/check    command/env/check  command/env/check
```

## Goals / Non-Goals

**Goals:**

- Preserve current public behavior for `run()`, `evaluate()`, status-file routing, output-file collection, workspace cleanup, fallback targets, and OpenSpec delegation guidance.
- Introduce `task_relay` as the canonical Python package and `trly` as the canonical CLI.
- Keep old imports and old CLI command usable temporarily through compatibility warnings.
- Make built-in agents isolated adapters with their own command building, environment setup, health check, and error classification.
- Add config loading from `~/.task-relay/config.yml` with deterministic defaults and validation.
- Keep v0.2 implementation small enough to ship as a migration, not a platform rewrite.

**Non-Goals:**

- No async queue, persistent job storage, HTTP server, webhook callback, or job database.
- No complete OpenCLI browser relay implementation in v0.2.
- No API-key manager. Agent CLIs and environment variables remain responsible for credentials.
- No npm package or JavaScript wrapper.
- No removal of the compatibility shim before the documented deprecation version.

## Decisions

### Decision 1: Use ports-and-adapters, not a renamed enum

Core code will accept agent names as strings and resolve them through `task_relay.agents.resolve()`. The core execution service will depend on an `AgentRunner` protocol, not `ClaudeRunner`, `CodexRunner`, `DeepSeekRunner`, or an enum.

Alternatives considered:

- Minimal rename: lowest diff, but keeps the original god node and makes custom agents awkward.
- Full plugin platform now: strongest long-term platform, but too much for v0.2 and not needed to preserve current behavior.

Rationale: adapters are enough to make new agents additive while keeping the migration bounded.

### Decision 2: Keep v0.2 registry explicit, reserve plugin entry points for later

`task_relay.agents` will contain built-in registrations for `claude`, `codex`, and `deepseek`. `config.py` may define configured CLI agents, but Python packaging entry point discovery is a Phase 2 extension, not required for v0.2.

Rationale: explicit registry is easier to test and avoids plugin discovery complexity before there is a real third-party adapter use case.

### Decision 3: Agent adapters own command, env, health, and error classification

Each adapter exposes:

```python
class AgentRunner(Protocol):
    name: str

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        ...

    def check(self) -> TargetStatus:
        ...
```

The adapter is responsible for binary resolution, model/effort flags, environment variables, stderr/stdout interpretation, and mapping subprocess failures to typed runner errors.

Rationale: target-specific behavior changes at different speeds. Keeping it beside the adapter prevents core execution from accumulating target branches.

### Decision 4: Core owns workspace, prompt contract, fallback, and cleanup

The core service owns:

- Creating `.task_relay/<job_id>/` workspaces.
- Building prompts that tell agents exactly where to write output files.
- Calling adapters in ordered fallback.
- Resolving status files.
- Calling callbacks.
- Cleaning workspaces in `finally` paths.

Rationale: workspace and outcome semantics are product behavior, not agent behavior. They must stay consistent across all agents.

### Decision 5: Use typed errors internally and preserve simple public failures

Introduce a small hierarchy:

- `TaskRelayError`
- `AgentNotFoundError`
- `AgentExecutionError`
- `AgentTimeoutError`
- `AgentQuotaError`
- `OutcomeResolutionError`
- `ConfigError`

Public APIs may still call `on_exception(exc)` or propagate exceptions, but internal tests should assert specific error classes where behavior differs.

Rationale: retry, fallback, diagnostics, and user-facing stderr need named failure modes. One catch-all runner error is not enough for the architecture being introduced.

### Decision 6: CLI is an adapter over library functions

`task_relay/cli/` will parse arguments, load input text, call library services, serialize output, and map exceptions to exit codes. It will not implement fallback, workspace cleanup, status resolution, or guidance installation rules directly.

Rationale: keeping CLI thin prevents future Python API and CLI behavior from drifting.

### Decision 7: Web relay is a reserved adapter type, not implemented runtime scope

The config schema can reserve `type: opencli`, but v0.2 MUST reject it with a clear "not supported in this version" error. No browser automation code ships in v0.2.

Rationale: this keeps the architecture pointed at the 12-month target without accepting untested runtime complexity now.

## Risks / Trade-offs

- Compatibility shim hides migration issues → Mitigation: every shim path emits `DeprecationWarning`, and tests assert both warning and behavior.
- New adapter layer could be overbuilt → Mitigation: keep protocol small and only model behavior already required by existing Claude/Codex/DeepSeek flows.
- Config files can make behavior surprising → Mitigation: CLI flags override config, config overrides built-in defaults, and health output reports the effective agent/model.
- DeepSeek depends on Claude-compatible environment variables → Mitigation: isolate that setup in `DeepSeekRunner` and test env mutation without real network calls.
- Fallback can mask degraded primary agents → Mitigation: log fallback failures with target name and expose winning target in `JobResult`.
- Workspace cleanup can delete debugging evidence → Mitigation: keep `TASK_RELAY_KEEP_IO=1` debug escape hatch equivalent to the existing keep-I/O behavior.
- Legacy and new command names can drift → Mitigation: route both console scripts into the same CLI implementation and test both entry behaviors.

## Migration Plan

1. Create new package skeleton in `E:/code/task-relay`:
   - `task_relay/`
   - `task_relay/agents/`
   - `task_relay/cli/`
   - compatibility `llm_eval/`
   - `tests/`
2. Port dataclasses and core behavior first: types, workspace, prompt, resolver, core service.
3. Implement built-in agent adapters from the current subprocess behavior.
4. Implement config loading and agent resolution.
5. Implement `trly` CLI and transitional `agent-dispatch` entry point.
6. Port OpenSpec delegation installer and update managed block names/commands.
7. Port and expand tests.
8. Update README and package metadata.
9. Run test suite from `E:/code/task-relay`.

Rollback strategy:

- This is a new repository path. If the migration fails, do not publish `task-relay`; keep using the existing `agent-cli-dispatcher` package.
- If a released `task-relay` v0.2 has a regression, publish a patch release from the compatibility-preserving branch. The old package remains available during the transition.

## Open Questions

- Should the compatibility `agent-dispatch` console script be included only in v0.2.x or kept through v0.3.0? Default plan: include in v0.2.x and remove in v0.3.0 with documented migration.
- Should configured custom CLI agents support arbitrary command templates in v0.2, or only built-in agents with per-agent defaults? Default plan: support built-in agents plus validated future config fields, but reject arbitrary command templates until there is a concrete use case.
