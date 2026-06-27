## ADDED Requirements

### Requirement: Observable quota waiting
The system SHALL emit a visible log entry each time it waits and retries on a quota or
rate-limit error, including the agent name, the attempt number, and the wait interval.

#### Scenario: Quota retry is logged
- **WHEN** an agent returns a quota or rate-limit error and the system decides to wait and retry
- **THEN** the system SHALL emit a log entry identifying the agent, attempt number, and wait duration before sleeping

### Requirement: Bounded retry budget
The system SHALL bound the total quota-retry wall-time by a configurable limit rather than a
fixed approximately-24-hour default.

#### Scenario: Retry budget is configurable
- **WHEN** an operator configures a total quota-retry budget
- **THEN** the system SHALL stop retrying and surface a quota failure once that budget is exceeded

#### Scenario: Default budget is not a silent day-long hang
- **WHEN** no retry budget is explicitly configured
- **THEN** the system SHALL apply a bounded default that does not silently block for approximately 24 hours

### Requirement: Transient versus hard quota classification
The system SHALL distinguish transient throttling from hard quota exhaustion so that each is
handled appropriately.

#### Scenario: Transient throttle waits briefly
- **WHEN** an agent returns a transient throttling signal (e.g. `429` with a retry-after hint)
- **THEN** the system SHALL apply a short, bounded wait before retrying the same agent

#### Scenario: Hard exhaustion does not exhaust a long retry loop
- **WHEN** an agent returns a hard-exhaustion signal (e.g. out-of-credits or monthly limit reached)
- **THEN** the system SHALL NOT consume a long single-agent retry loop before acting

### Requirement: Opt-in fast fallback on hard exhaustion
The system SHALL treat fast fallback to the next chain agent on hard quota exhaustion as an
opt-in policy that is disabled by default, preserving the default behavior of waiting for the
configured (cheaper) agent.

#### Scenario: Fast fallback disabled by default
- **WHEN** the primary agent in a chain hits hard quota exhaustion and fast fallback is not enabled
- **THEN** the system SHALL wait (within the bounded budget) for the configured agent rather than immediately switching agents

#### Scenario: Fast fallback enabled
- **WHEN** fast fallback is enabled and the primary agent hits hard quota exhaustion with another agent available in the chain
- **THEN** the system SHALL move to the next agent rather than continuing to wait on the exhausted one
