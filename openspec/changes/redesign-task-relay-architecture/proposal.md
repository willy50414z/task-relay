## Why

`agent-cli-dispatcher` has outgrown its original `llm_eval` shape: target selection, subprocess command construction, environment mutation, retry behavior, health checks, CLI parsing, and OpenSpec delegation guidance are tightly coupled around `LLMTarget` and `llm_svc.run()`. The migration to `task-relay` is the right moment to fix the architecture, not just rename files.

The new project should preserve the working behavior users already rely on while making future agents, custom configuration, and OpenCLI-style web relay integration additive rather than core rewrites.

## What Changes

- **BREAKING**: Create the new distribution `task-relay`, package `task_relay`, and CLI command `trly` in `E:/code/task-relay`.
- Preserve compatibility through a temporary `llm_eval` import shim and legacy `agent-dispatch` console entry point that warn instead of breaking immediately.
- Replace the hardcoded `LLMTarget` enum dispatch path with a ports-and-adapters architecture:
  - Core request/result and outcome routing stay target-agnostic.
  - Each built-in agent owns its command, environment, health check, and output parsing.
  - Registry resolution maps names to built-in or configured agents.
- Split CLI parsing from business logic:
  - `trly run`
  - `trly evaluate`
  - `trly health`
  - `trly install`
  - `trly uninstall`
- Add `~/.task-relay/config.yml` support for default agent, per-agent model defaults, effort defaults, and future custom agent declarations.
- Keep OpenCLI/web relay out of v0.2 runtime implementation, but reserve clean extension points so it can be added without changing the core task execution API.
- Move tests to the new package shape and add regression coverage for compatibility, registry resolution, config merging, CLI behavior, fallback, cleanup, and error handling.

## Capabilities

### New Capabilities

- `task-execution-core`: Target-agnostic API for raw prompt execution and outcome-routed evaluation.
- `agent-adapter-registry`: Built-in and configured agent resolution through isolated runner adapters.
- `task-relay-cli`: `trly` command-line interface for run, evaluate, health, install, and uninstall workflows.
- `compatibility-migration`: Transitional compatibility behavior for old package imports and old console command usage.
- `openspec-delegation-install`: Project-local OpenSpec delegation guidance installation under the new command and package names.

### Modified Capabilities

- None. This is a new repository migration; there are no existing OpenSpec base specs in `E:/code/task-relay` to modify.

## Impact

- New source tree under `task_relay/` with a small compatibility `llm_eval/` shim.
- New package metadata for `task-relay`, version `0.2.0`, and console scripts for `trly` plus transitional `agent-dispatch`.
- CLI behavior remains functionally equivalent for run/evaluate/health/install flows, with renamed commands and compatibility warnings where appropriate.
- Agent behavior remains synchronous and local-process based in v0.2; async jobs, persistent storage, HTTP APIs, webhooks, API-key management, npm packaging, and full OpenCLI browser relay are explicitly out of scope.
- Tests need to cover both the new public surface and the temporary compatibility surface so migration regressions are visible.
