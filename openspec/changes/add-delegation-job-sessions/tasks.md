## 1. Job Session Core

- [x] 1.1 Add a `task_relay/jobs.py` or equivalent module defining `JobSpec`, `JobStatus`, persisted metadata shape, status enum, and job id generation.
- [x] 1.2 Implement per-job runtime directories under `.task_relay/jobs/<job-id>/` with atomic `meta.json` writes and stdout/stderr log paths.
- [x] 1.3 Implement blocking job execution with stdout/stderr streaming to log files while preserving the caller-facing stdout result.
- [x] 1.4 Implement status calculation for `running`, `succeeded`, `failed`, `timeout`, `stalled`, and `killed` using process liveness, exit code, deadline, log mtimes, expected-output mtimes, and explicit stop state.
- [x] 1.5 Implement process-tree termination for timeout and stop, using POSIX process groups where available and guarded best-effort behavior elsewhere.
- [x] 1.6 Add unit tests for metadata creation/update, atomic metadata tolerance, log streaming, final status calculation, timeout, stalled status, killed status, and expected-output failure.

## 2. Jobs CLI

- [x] 2.1 Add `trly jobs list` to show recent job id, status, target, role/mode, change/task, start time, age/duration, and log path.
- [x] 2.2 Add `trly jobs status <job-id>` with detailed metadata and readable diagnostics for missing/corrupt job records.
- [x] 2.3 Add `trly jobs logs <job-id> [--stream stdout|stderr|combined] [--tail N] [--follow]`.
- [x] 2.4 Add `trly jobs stop <job-id>` that terminates the job process tree and persists `killed`.
- [x] 2.5 Add `trly jobs cleanup [--older-than DAYS] [--status STATUS]` and report the removed count.
- [x] 2.6 Add CLI tests for list/status/logs/tail/follow behavior, stop, cleanup, and unreadable metadata handling.

## 3. Runtime Integration

- [x] 3.1 Route `task_relay.agents.common.run_subprocess` through the job-session runner in blocking mode without changing successful stdout behavior.
- [x] 3.2 Thread job context fields from `core.run`, `core.run_isolated`, fallback execution, and agent adapters into `JobSpec` where available.
- [x] 3.3 Preserve quota retry logging and trace recording while adding job id/log path to trace records when a job session exists.
- [x] 3.4 Add optional `trly run --background` for supported manual runs, returning a job id without waiting; do not apply this to review gate orchestration by default.
- [x] 3.5 Add regression tests proving existing blocking `trly run`, fallback, expected-output verification, and isolated delegation behavior remain compatible.

## 4. Review / Apply Diagnostics

- [x] 4.1 Update review gate subprocess execution so each reviewer and arbiter has a job id and streamed logs.
- [x] 4.2 On reviewer/arbiter failure, timeout, or stall, include reviewer/arbiter id, target/model, job id, status, log path, expected output path, and last-output timestamp when available.
- [x] 4.3 Update high-level apply diagnostics to include job id and log path when delegated apply fails, times out, stalls, or produces no accepted output.
- [x] 4.4 Add tests for review-gate timeout/failure diagnostics and apply failure diagnostics with job context.

## 5. Documentation and Validation

- [x] 5.1 Document `trly jobs` commands in README or docs with examples for checking a long-running reviewer.
- [x] 5.2 Document the distinction between `trly jobs` (live/log/process view) and `trly trace --summary` (after-the-fact aggregate/time/token view).
- [x] 5.3 Run `openspec validate add-delegation-job-sessions` and fix any artifact issues.
- [x] 5.4 Run the relevant unit test suite for jobs, run, review gate, apply, and trace integration.
