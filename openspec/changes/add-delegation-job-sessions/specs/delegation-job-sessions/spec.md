## ADDED Requirements

### Requirement: Delegated subprocesses have job sessions
The system SHALL create a job session for each long-running delegated agent subprocess that is managed by Task Relay.

#### Scenario: Blocking run creates a job session
- **WHEN** a delegated agent subprocess starts through the normal blocking run path
- **THEN** the system SHALL create a job id and persist metadata for that job before waiting for completion

#### Scenario: Review gate creates per-agent jobs
- **WHEN** the review gate invokes parallel reviewers or serial arbiters
- **THEN** each reviewer and arbiter subprocess SHALL have its own job session

### Requirement: Job metadata is persisted
The system SHALL persist metadata for each job session under the Task Relay runtime directory.

#### Scenario: Metadata records execution identity
- **WHEN** a job session is created
- **THEN** its metadata SHALL include the job id, command, cwd, target, model when known, role or mode when known, change or task when known, status, pid when known, timestamps, timeout settings, log paths, expected outputs, and exit code when complete

#### Scenario: Metadata is updated on completion
- **WHEN** a job exits, times out, fails output verification, or is stopped
- **THEN** the system SHALL update the job metadata with the final status, exit code when available, end timestamp, and error summary when available

#### Scenario: Corrupt metadata does not break listing
- **WHEN** a jobs command encounters an unreadable or corrupt metadata file
- **THEN** the command SHALL report that record as unreadable or skip it with a warning rather than failing the entire jobs command

### Requirement: Job logs are streamable while running
The system SHALL stream delegated subprocess stdout and stderr to per-job log files while the process is running.

#### Scenario: Logs are available before completion
- **WHEN** a delegated subprocess writes stdout or stderr before it exits
- **THEN** the corresponding job log SHALL be readable through the jobs CLI before the subprocess completes

#### Scenario: Tail returns recent log output
- **WHEN** the operator requests the last N log lines for a job
- **THEN** the system SHALL return at most N recent lines from the selected job log stream

#### Scenario: Follow streams appended log output
- **WHEN** the operator follows a running job log
- **THEN** the system SHALL print new log content as it is appended until the follow is interrupted or the job finishes

### Requirement: Job status combines process, log, artifact, and deadline signals
The system SHALL compute job status from process liveness, exit result, hard timeout, recent log activity, expected-output activity, and explicit stop requests.

#### Scenario: Running process reports running
- **WHEN** the process is alive and neither the hard timeout nor stall threshold has been reached
- **THEN** the job status SHALL be `running`

#### Scenario: Successful process with expected output reports succeeded
- **WHEN** the process exits with code zero and all declared expected outputs pass verification
- **THEN** the job status SHALL be `succeeded`

#### Scenario: Missing expected output reports failed
- **WHEN** the process exits with code zero but a declared expected output is missing, empty, or unreadable
- **THEN** the job status SHALL be `failed`

#### Scenario: Non-zero exit reports failed
- **WHEN** the process exits with a non-zero code
- **THEN** the job status SHALL be `failed`

#### Scenario: Hard timeout reports timeout
- **WHEN** the job exceeds its hard timeout
- **THEN** the system SHALL terminate the job process tree and set the job status to `timeout`

#### Scenario: Quiet live process reports stalled
- **WHEN** the process is alive, the hard timeout has not expired, and neither logs nor expected outputs have changed within the configured stall window
- **THEN** the job status SHALL be `stalled`

### Requirement: Jobs CLI exposes live and historical jobs
The system SHALL provide jobs commands for listing, inspecting, tailing, stopping, and cleaning up job sessions.

#### Scenario: List jobs
- **WHEN** the operator runs `trly jobs list`
- **THEN** the command SHALL print recent jobs with job id, status, target, role or mode when known, change or task when known, start time, duration or age, and log path

#### Scenario: Inspect job status
- **WHEN** the operator runs `trly jobs status <job-id>`
- **THEN** the command SHALL print detailed metadata for that job including status, pid when known, exit code when known, timestamps, expected outputs, and log paths

#### Scenario: Read job logs
- **WHEN** the operator runs `trly jobs logs <job-id>`
- **THEN** the command SHALL print the selected job log output without requiring the job to still be running

#### Scenario: Stop job
- **WHEN** the operator runs `trly jobs stop <job-id>` for a running job
- **THEN** the system SHALL terminate the job process tree and update the job status to `killed`

#### Scenario: Cleanup old jobs
- **WHEN** the operator runs `trly jobs cleanup`
- **THEN** the command SHALL remove job session files that match the configured age or status cleanup policy and report how many jobs were removed

### Requirement: Blocking behavior remains compatible
The system SHALL preserve existing blocking command behavior unless the operator explicitly requests background execution.

#### Scenario: Blocking run still returns stdout
- **WHEN** the operator runs a delegated command without background mode
- **THEN** the command SHALL wait for the delegate to complete and return stdout through the existing caller-facing behavior

#### Scenario: Background run returns job id
- **WHEN** the operator runs a supported delegated command with background mode enabled
- **THEN** the command SHALL start the delegate, persist its job session, print the job id, and return without waiting for completion

#### Scenario: Review gate remains blocking
- **WHEN** the review gate invokes reviewers and arbiters
- **THEN** the review gate SHALL wait for required job completion and SHALL NOT silently switch to background-only orchestration

### Requirement: Review and apply diagnostics include job context
The system SHALL include job context in user-visible delegation failures that involve managed agent subprocesses.

#### Scenario: Review gate timeout identifies the job
- **WHEN** a reviewer or arbiter job times out
- **THEN** the review gate error SHALL include the reviewer or arbiter id, job id, status, log path, and expected output path when one was declared

#### Scenario: Review gate stall identifies the job
- **WHEN** a reviewer or arbiter job is stalled at the time diagnostics are reported
- **THEN** the review gate diagnostic SHALL include the job id, last output timestamp when known, log path, and expected output path when one was declared

#### Scenario: Apply failure identifies the job
- **WHEN** an apply delegation fails, times out, stalls, or produces no accepted output
- **THEN** the apply-facing diagnostic SHALL include the job id and log path for the delegated subprocess

### Requirement: Trace records link to job sessions
The system SHALL link after-the-fact delegation trace records to job sessions when both are available.

#### Scenario: Completed job writes trace reference
- **WHEN** a delegation completes and a trace record is appended
- **THEN** the trace record SHALL include the job id and log path when the delegation was run under a job session
