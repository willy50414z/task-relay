## Why

Delegated review/apply calls can run for many minutes, but today the operator mostly sees either eventual success or a timeout. Existing trace work records what happened after a delegation finishes; it does not let the operator inspect a live delegate, tail logs, distinguish a live-but-stalled agent from a dead process, or find the exact reviewer job that blocked a review gate.

## What Changes

- Add a lightweight delegation job session layer around long-running agent subprocesses.
- Stream each delegated subprocess stdout/stderr to per-job log files while it runs.
- Persist per-job metadata including target/model, role, change/task, pid, status, timestamps, log paths, timeout settings, and expected output artifacts.
- Add `trly jobs` commands for `list`, `status`, `logs`, `stop`, and `cleanup`.
- Update review/apply orchestration to surface job ids, log paths, and expected artifact paths when a delegate fails, stalls, or times out.
- Keep existing blocking `trly run` behavior by default; optional background execution may return a job id without waiting for completion.
- Preserve hard timeout semantics; job sessions add observability and stall detection, not unbounded execution.

## Capabilities

### New Capabilities
- `delegation-job-sessions`: Live and historical job sessions for delegated agent subprocesses, including metadata, logs, status, stop, cleanup, and integration with review/apply failures.

### Modified Capabilities
- None. There are no base specs under `openspec/specs/`; this change complements the in-progress `harden-delegation-runtime` observability trace rather than modifying an archived base capability.

## Impact

- **Code:** new job/session module under `task_relay/` for process lifecycle, metadata persistence, log streaming, process-group termination, and status calculation; updates to `task_relay/agents/common.py`, `task_relay/core.py`, `task_relay/workflow/review_gate.py`, and CLI parsers/handlers.
- **CLI:** add `trly jobs list/status/logs/stop/cleanup`; add optional background execution flag only where behavior is well-defined.
- **Storage:** add per-job files under `.task_relay/jobs/`; continue relying on existing `/.task_relay/` gitignore.
- **Tests:** add deterministic tests for metadata persistence, log tailing, status transitions, stall detection, process-group stop, expected-output success criteria, cleanup, and review-gate failure messages.
- **Compatibility:** default blocking command behavior remains unchanged. Existing `trly trace --summary` remains the after-the-fact aggregate view; `trly jobs` becomes the live/historical process view.
