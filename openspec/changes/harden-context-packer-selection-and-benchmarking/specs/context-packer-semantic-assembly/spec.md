## ADDED Requirements

### Requirement: Model fallback assembly contract MUST match packet assembly behavior
The system SHALL ensure that every field accepted from model-based context resolution is either applied to packet assembly or rejected explicitly with a machine-readable reason.

#### Scenario: Model result adds supported context selectors
- **WHEN** model fallback returns supported selectors for `specs`, `design_sections`, `task_dependencies`, or `extra_reads`
- **THEN** the packet plan SHALL include the corresponding selected context in its report and final packet output

#### Scenario: Model result includes unsupported selectors
- **WHEN** model fallback returns a selector that the current packet builder does not support
- **THEN** the packet plan SHALL reject that selector with an explicit machine-readable reason instead of silently ignoring it

### Requirement: Packet selection report MUST explain semantic assembly decisions
The system SHALL expose enough structured reporting to show which semantic selection inputs were accepted, rejected, or downgraded during packet assembly.

#### Scenario: Semantic selection succeeds
- **WHEN** model fallback contributes to packet assembly
- **THEN** the packet report SHALL show the applied semantic selections and their rationale

#### Scenario: Semantic selection falls back
- **WHEN** model fallback fails or produces invalid output
- **THEN** the packet report SHALL preserve the fallback reason and the failure metadata without pretending semantic assembly succeeded

### Requirement: CLI and model-proposed extra reads MUST have defined merge semantics
The system SHALL define how CLI-supplied `extra_reads` and model-fallback-proposed `extra_reads` combine before packet trimming.

#### Scenario: CLI and model both provide extra reads
- **WHEN** the user supplies `extra_reads` and model fallback also proposes `extra_reads`
- **THEN** the packet builder SHALL merge them additively, deduplicate repeated paths, and preserve CLI-supplied reads ahead of model-proposed reads in trimming priority

#### Scenario: Extra reads are trimmed for budget
- **WHEN** the packet exceeds budget and extra reads must be trimmed
- **THEN** model-proposed extra reads SHALL be trimmed before CLI-supplied extra reads and before required task/core spec context
