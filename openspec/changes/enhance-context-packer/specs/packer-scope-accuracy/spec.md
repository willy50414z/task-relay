## ADDED Requirements

### Requirement: Scope-selection accuracy metric
The system SHALL define a measurable scope-selection accuracy metric so that any change to
selection behavior can be evaluated rather than assumed.

#### Scenario: Metric is computable against labeled data
- **WHEN** a labeled set of `(task -> expected scope)` examples is provided
- **THEN** the system SHALL compute spec precision/recall, task-block precision/recall, fallback rate, and packet size for that set
- **AND** the system SHALL report design-section recall as a secondary signal rather than as the primary accuracy score

#### Scenario: A change in selection rules is evaluated, not assumed
- **WHEN** the deterministic selection rules change
- **THEN** the system SHALL be able to report whether the metric improved or regressed against the labeled set

### Requirement: Labeled evaluation set
The system SHALL maintain a small labeled evaluation set used as the source of truth for the
accuracy metric.

#### Scenario: Eval label records expected scope with evidence
- **WHEN** an eval example is added
- **THEN** it SHALL record the task, expected specs, expected task blocks, expected design sections when applicable, expected repo-file references when applicable, and evidence explaining why each expected item is required

#### Scenario: Eval set reports coverage, not just aggregate score
- **WHEN** the metric runner reports results
- **THEN** it SHALL include sample count and category coverage for narrow deterministic cases, ambiguous fallback cases, explicit-signal cases, and test-mode/diff cases

#### Scenario: Eval set drives phase validation
- **WHEN** a later enhancement phase claims improved accuracy
- **THEN** that claim SHALL be backed by the metric computed over the labeled evaluation set

### Requirement: Per-pack selection diagnostics as metric data
The system SHALL emit per-pack selection diagnostics that double as the raw data for the accuracy
metric.

#### Scenario: Diagnostics expose the selection decision
- **WHEN** a packet is generated or dry-run
- **THEN** the diagnostics SHALL include the selection mode, the spec candidates with their scores, and the fallback reason when one applies

#### Scenario: Diagnostics aggregate into a fallback rate
- **WHEN** diagnostics from many packs are aggregated
- **THEN** the system SHALL be able to report how often selection fell back to the conservative all-specs scope
