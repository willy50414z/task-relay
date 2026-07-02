## ADDED Requirements

### Requirement: Timeout policy separates soft deadlines from hard caps
The system SHALL support timeout policies that separate soft deadlines, hard timeout caps, idle/stall windows, extension limits, and termination grace periods for managed delegate jobs.

#### Scenario: Hard timeout remains absolute
- **WHEN** a managed delegate job reaches its hard timeout
- **THEN** the system SHALL NOT extend the job further
- **AND** it SHALL begin the configured termination sequence after recording timeout diagnostics

#### Scenario: Soft deadline can extend within hard cap
- **WHEN** a managed delegate job reaches its soft deadline before the hard timeout
- **AND** the process is still alive
- **AND** the job has recent activity within the configured activity window
- **THEN** the system SHALL extend the soft deadline by the configured extension interval
- **AND** it SHALL record the extension reason, activity source, previous deadline, new deadline, and remaining hard timeout budget

#### Scenario: Manual hard timeout override is visible
- **WHEN** a caller supplies a shorter timeout than the role-aware default
- **THEN** the system SHALL honor the caller override as the hard timeout
- **AND** diagnostics SHALL record that the timeout source was a user override

### Requirement: Timeout decisions use process liveness and activity diagnostics
The system SHALL inspect process liveness and recent activity before terminating a managed delegate for timeout.

#### Scenario: Process already exited before timeout handling
- **WHEN** timeout handling runs and the process is no longer alive
- **THEN** the system SHALL NOT send a termination signal
- **AND** it SHALL resolve the job from the process exit result and semantic contract validation

#### Scenario: Process alive at timeout
- **WHEN** timeout handling runs and the process is still alive
- **THEN** diagnostics SHALL record pid, process group id when available, process liveness, last stdout timestamp, last stderr timestamp, last expected-output timestamp, last activity timestamp, and timeout reason before sending a termination signal

#### Scenario: Activity includes expected output changes
- **WHEN** a job declares expected output artifacts
- **THEN** timeout and stall diagnostics SHALL treat expected-output mtime changes as job activity alongside stdout and stderr activity

### Requirement: Termination sequence is observable and bounded
The system SHALL terminate timed-out delegate process trees using a bounded, observable sequence.

#### Scenario: Graceful terminate before force kill
- **WHEN** a managed delegate job must be terminated for hard timeout or explicit stop
- **THEN** the system SHALL first send a graceful termination signal to the process tree when supported
- **AND** it SHALL wait for the configured grace period before sending a force-kill signal to any still-live process tree

#### Scenario: Termination events are recorded
- **WHEN** the system sends graceful or forceful termination signals
- **THEN** diagnostics SHALL record signal type, timestamp, target pid/process group, and whether the process was still alive after each step

#### Scenario: Stop command uses same termination diagnostics
- **WHEN** the operator runs `trly jobs stop <job-id>` for a running managed job
- **THEN** the stop path SHALL use the same termination event recording as timeout termination
- **AND** the final job status SHALL be `killed`

### Requirement: Stalled jobs are diagnosed separately from hard timeouts
The system SHALL distinguish stalled jobs from hard timeouts and SHALL NOT conflate a quiet process with an expired hard timeout.

#### Scenario: Quiet live process is marked stalled
- **WHEN** a managed delegate process is alive
- **AND** the hard timeout has not expired
- **AND** neither logs nor expected outputs have changed within the configured stall window
- **THEN** the job status or diagnostics SHALL report `stalled`
- **AND** the system SHALL include the last activity timestamp and stall window in diagnostics

#### Scenario: Stall does not terminate by default
- **WHEN** a managed foreground delegate is stalled but has not reached hard timeout
- **THEN** the system SHALL NOT terminate the process unless stall termination is explicitly enabled for that job or command

### Requirement: Role-aware timeout defaults are visible and testable
The system SHALL provide role-aware timeout defaults for common Task Relay delegation roles and expose the chosen policy in job metadata.

#### Scenario: DeepSeek apply uses long hard timeout by default
- **WHEN** a DeepSeek apply implementation-draft or test-draft delegation starts without a caller timeout override
- **THEN** the hard timeout SHALL be at least 1800 seconds
- **AND** diagnostics SHALL record the policy source as a role-aware default

#### Scenario: Full review gate uses global hard timeout suited for reviewers and arbiters
- **WHEN** the review gate starts without a caller global-timeout override
- **THEN** the global hard timeout SHALL be at least 2400 seconds
- **AND** reviewer and arbiter subprocess diagnostics SHALL record their remaining hard timeout budget at start

#### Scenario: Timeout policy appears in jobs status
- **WHEN** the operator inspects a job with `trly jobs status <job-id>`
- **THEN** the output SHALL show hard timeout, soft deadline when configured, stall window, last activity time, timeout source, and diagnostics path
