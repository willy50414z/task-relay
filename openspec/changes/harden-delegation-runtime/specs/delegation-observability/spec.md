## ADDED Requirements

### Requirement: Per-delegation execution trace
The system SHALL append one structured trace record per delegation to a JSONL trace sink, so the
operator can verify the multi-agent flow ran and inspect each step after the fact.

#### Scenario: Successful delegation is recorded
- **WHEN** a delegation completes successfully
- **THEN** the system SHALL append a record with at least a timestamp, the agent, the model, the role/mode, the change/task when known, the duration, and the outcome

#### Scenario: Failed or quota-exhausted delegation is recorded
- **WHEN** a delegation fails or exhausts its quota budget
- **THEN** the system SHALL append a record whose outcome reflects the failure class rather than omitting the delegation

#### Scenario: Fallback is recorded
- **WHEN** a chain falls back from one agent to another
- **THEN** the trace SHALL record which agent actually ran and that a fallback occurred

### Requirement: Token usage captured when available, never fabricated
The system SHALL record token usage for a delegation when the agent CLI exposes it, and SHALL
record it as unavailable rather than estimating when the CLI does not.

#### Scenario: Claude/DeepSeek usage captured
- **WHEN** a delegation runs through the claude CLI (claude or deepseek) with a JSON output mode that reports usage
- **THEN** the system SHALL record the input and output token counts (and cost when reported)

#### Scenario: Usage unavailable is explicit
- **WHEN** the agent CLI does not report token usage (e.g. codex)
- **THEN** the system SHALL record the token fields as null/unavailable rather than a guessed value

### Requirement: Duration is measured per delegation
The system SHALL measure and record the wall-clock duration of each delegation.

#### Scenario: Duration recorded
- **WHEN** a delegation completes (success or failure)
- **THEN** the recorded trace SHALL include its wall-clock duration

### Requirement: Configurable trace sink and log level
The system SHALL allow the operator to configure where the trace is written and the verbosity of
the human-readable log stream.

#### Scenario: Trace sink is configurable
- **WHEN** the operator configures a trace file path
- **THEN** the system SHALL write trace records there instead of the default location

#### Scenario: Log level is configurable
- **WHEN** the operator sets the log level
- **THEN** the system SHALL emit human-readable progress at that level

### Requirement: Session summary
The system SHALL provide a way to aggregate a session's trace into totals.

#### Scenario: Summarize a session
- **WHEN** the operator requests a summary of a session's trace
- **THEN** the system SHALL report total duration, total token usage (where available), and a per-agent breakdown
