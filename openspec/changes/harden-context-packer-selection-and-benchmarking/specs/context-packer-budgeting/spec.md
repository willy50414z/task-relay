## ADDED Requirements

### Requirement: Packet assembly MUST enforce a bounded context budget
The system SHALL compute packet size against a configured byte budget and report whether the assembled context fits within that budget.

#### Scenario: Packet fits within budget
- **WHEN** the selected sections and repo references are within the configured byte budget
- **THEN** the packet report SHALL mark the packet as within budget and emit the full selected context

#### Scenario: Packet exceeds budget
- **WHEN** the selected sections and repo references exceed the configured byte budget
- **THEN** the packet builder SHALL apply deterministic trimming and report which sections were removed

### Requirement: Trimming MUST be deterministic and inspectable
The system SHALL apply packet trimming in a fixed priority order so repeated runs over the same inputs produce the same trimmed output and diagnostics.

#### Scenario: Optional context is trimmed first
- **WHEN** trimming is required
- **THEN** optional context such as extra reads or secondary context SHALL be removed before required task and core spec context

#### Scenario: Trimming changes packet output
- **WHEN** one or more sections are removed to satisfy budget
- **THEN** the packet report SHALL list the removed sections and the final budget status

#### Scenario: Core context still exceeds budget
- **WHEN** even the required task and core spec context exceed the configured byte budget
- **THEN** the packet builder SHALL return a machine-readable budget violation instead of silently trimming required core context
