## Context

Task Relay currently executes delegated agents through synchronous subprocess helpers. The operator gets a final result, timeout, or error, but not a live handle for long-running work. `harden-delegation-runtime` adds JSONL execution trace and `trly trace --summary`; that is the after-the-fact audit trail. This change adds the live/historical job session layer needed to inspect a running delegate, tail logs, stop the process tree, and diagnose which reviewer/apply job is stuck.

Current relevant state:
- `task_relay/agents/common.py` uses blocking subprocess execution for agent adapters.
- `task_relay/workflow/review_gate.py` fans out reviewers with asyncio subprocesses and waits for completion.
- `task_relay/core.py` already has expected-output verification and isolated worktree delegation.
- `.task_relay/` is already intended as ignored local runtime state.

## Goals / Non-Goals

**Goals:**
- Give every long-running delegate a stable job id, metadata file, and stdout/stderr logs.
- Let users inspect live and recently completed delegations through `trly jobs`.
- Preserve existing blocking behavior by default so current review/apply flows still wait for results.
- Add stall visibility based on process liveness, log progress, expected-output progress, and deadlines.
- Make review-gate failure diagnostics point to the specific reviewer/arbiter job and log path.
- Keep the implementation small enough to land before any broader workflow-engine refactor.

**Non-Goals:**
- Replacing `trly trace --summary`; trace remains the aggregate audit/cost view.
- Building a daemon server, web UI, restart policy, scheduler, or distributed queue.
- Full OS sandboxing or malicious-agent confinement.
- Making every `trly run` background-only. Background mode is optional and only where the caller can handle an async job id.
- Detecting semantic LLM progress. v1 observes process/log/artifact activity; it does not infer whether reasoning is useful.

## Decisions

### D1: Use a Task Relay job-session abstraction, not a generic bg-tm clone

The public model is `JobSpec` and `JobStatus`, not a raw `RunningProcess`. Task Relay needs to know target/model, role, change/task, expected outputs, timeout, and worktree branch. A generic PID wrapper cannot decide whether a review succeeded because the JSON artifact exists and is non-empty.

The internal implementation can still have a small `RunningProcess` helper with pid/process-group/log paths. That helper is not the stable API.

### D2: Default execution remains blocking; `--background` is opt-in

Existing callers expect `trly run` and review gate steps to return a final stdout or fail. Changing default behavior to return immediately would break orchestration. v1 wraps the subprocess in a job session even for blocking calls, streams logs while waiting, and records final status. Optional background execution may return the job id immediately where the caller explicitly asks for it.

### D3: Persist one directory per job under `.task_relay/jobs/<job-id>/`

Each job directory contains:
- `meta.json`: command, cwd, target/model, role, change/task, pid, process group id when known, status, timestamps, timeout, stall timeout, expected outputs, worktree branch, exit code, and error summary.
- `stdout.log`: stdout stream.
- `stderr.log`: stderr stream.
- `combined.log`: optional merged stream for human tailing, if cheap to maintain.

One directory per job makes cleanup and post-failure sharing straightforward. A global index is optional; `trly jobs list` can scan recent metadata files first and add an index later only if performance requires it.

### D4: Compute status from multiple signals

Status is not just `pid exists`.

State model:

```text
created
  │
  ▼
running ────────┬────────▶ succeeded
  │             ├────────▶ failed
  │             ├────────▶ timeout
  │             ├────────▶ killed
  │             └────────▶ stalled
  │
  └─ if process exits, final status wins over stale stall state
```

Rules:
- `running`: process is alive and hard deadline has not expired.
- `stalled`: process is alive, hard deadline has not expired, but neither logs nor expected outputs have changed for the configured stall window.
- `timeout`: hard deadline expired and the manager terminated the process tree.
- `succeeded`: process exit code is zero and declared expected outputs pass their verification.
- `failed`: non-zero exit, missing/empty expected output, unreadable expected output, or manager error.
- `killed`: user requested stop and the process tree was terminated.

### D5: Keep hard timeout; add stall detection as diagnosis, not automatic success/failure replacement

Timeout remains the hard upper bound. Stall detection gives earlier visibility and better diagnostics. v1 may mark a job `stalled` while leaving it alive until timeout or explicit stop. Auto-killing on stall should be opt-in later, because agent CLIs can be quiet during long reasoning.

Default stall window: 900 seconds. Make it configurable via flag or env, e.g. `TASK_RELAY_STALL_TIMEOUT`.

### D6: Stop process groups, not only parent PIDs

Agent CLIs can spawn child processes. On POSIX, start delegated jobs with a new process session/process group and terminate the group on timeout or `trly jobs stop`. On platforms where process groups differ, provide a best-effort implementation and test the behavior that is portable. If `psutil` is adopted, use it only for process-tree inspection/termination; do not make it responsible for core status semantics.

### D7: Review gate emits job-aware diagnostics

Each reviewer and arbiter invocation receives a job id. On failure, timeout, or stall, the review gate error includes:
- reviewer/arbiter id
- target/model
- job id
- status
- log path
- expected output path
- last output timestamp

This lets the operator run `trly jobs logs <job-id> --tail 200 --follow` instead of guessing which subprocess hung.

### D8: Integrate with trace without duplicating responsibilities

Job metadata is live/historical process state. Trace JSONL is the durable execution audit. When a job completes, the existing trace record should include the job id and log path when available. `trly jobs` does not compute token/cost summaries; `trly trace --summary` does.

### D9: Background mode is a narrow CLI feature

`trly run --background` may start a job and return its id. It MUST NOT silently make review gate asynchronous. Review/apply orchestration still decides whether it can continue without a result. Background mode is mainly for manual delegate calls and debugging long-running agents.

## Risks / Trade-offs

- [False stall classification during quiet LLM reasoning] → Do not auto-kill by default; make stall a visible status until hard timeout or explicit stop.
- [Cross-platform process-tree termination is uneven] → Implement POSIX process groups first, add platform guards, and cover Windows behavior with best-effort tests where available.
- [Log files grow without bounds] → Provide `trly jobs cleanup`; defer rotation until real log sizes require it.
- [Metadata corruption on crash] → Write metadata atomically via temp file + rename; status command should tolerate partial/corrupt job records and report them as unreadable.
- [Race between expected-output verification and process exit] → Final status calculation runs after process exit and reuses existing expected-output verification logic.
- [Operator confuses jobs with trace] → CLI help and docs distinguish `trly jobs` for live/log/process inspection from `trly trace` for aggregate cost/time audit.

## Migration Plan

1. Add the job-session module and tests without changing public behavior.
2. Route `trly run` through the job-session manager in blocking mode while preserving stdout return behavior.
3. Add `trly jobs list/status/logs/stop/cleanup`.
4. Add job-aware diagnostics to review gate.
5. Add optional `--background` only after blocking parity is covered by tests.

Rollback: keep the previous direct subprocess helper path behind a small internal switch during implementation. If job-session streaming has regressions, callers can temporarily fall back to direct blocking execution while the CLI surface remains disabled.

## Open Questions

- Should v1 maintain separate stdout/stderr only, or also a combined log? Recommendation: separate logs are required; combined log is optional if implementation stays simple.
- Should `psutil` be a required dependency? Recommendation: avoid it in v1 unless process-tree termination on target platforms is too fragile without it.
- Should `stalled` ever become an exit condition? Recommendation: not in v1. Add an explicit `--fail-on-stall` later only if real runs show value.
