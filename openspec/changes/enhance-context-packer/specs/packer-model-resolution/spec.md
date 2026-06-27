## ADDED Requirements

### Requirement: Model-assisted resolution is opt-in and last-resort
The system SHALL keep deterministic scope selection as the default and use model-assisted
resolution only when explicitly enabled and only when deterministic rules cannot uniquely resolve
scope.

#### Scenario: Deterministic resolution needs no model
- **WHEN** deterministic rules uniquely resolve a task's scope
- **THEN** the system SHALL NOT invoke the model resolver

#### Scenario: Model resolver disabled by default
- **WHEN** model-assisted resolution is not enabled
- **THEN** the system SHALL fall back to the conservative all-specs scope with a visible note rather than calling a model

### Requirement: Model resolves from a constrained set and never authors the packet
The system SHALL constrain the model resolver to selecting from a candidate set and returning a
structured result; the final packet SHALL be rendered locally.

#### Scenario: Structured result, not free-form packet
- **WHEN** the model resolver runs
- **THEN** it SHALL return a structured selection (specs, design sections, dependencies, repo-file candidates, and reason) and SHALL NOT produce the final packet text

#### Scenario: Choices restricted to real candidates
- **WHEN** the model selects scope
- **THEN** its choices SHALL be restricted to the provided candidate set rather than inventing paths

### Requirement: Local deterministic validation, not self-reported confidence
The system SHALL accept or reject the model's structured result by local deterministic checks, not
by the model's self-reported confidence alone.

#### Scenario: Invalid structured pick is rejected
- **WHEN** the model selects a spec, section, or file that does not exist in the candidate set
- **THEN** the system SHALL reject that selection rather than trust it

#### Scenario: Deterministic scores are a soft outlier check
- **WHEN** the model's selection is evaluated
- **THEN** the system SHALL compare it with deterministic candidate scores to identify outliers
- **AND** the system SHALL NOT reject a valid candidate solely because it was outside the token-overlap top candidates

#### Scenario: Unsupported pick falls back conservatively
- **WHEN** the validated result has no deterministic support, no explicit signal support, and no grounded reason
- **THEN** the system SHALL fall back to the conservative all-specs scope with a visible note

### Requirement: Resolver results are reproducible, visible, and call-bounded
The system SHALL cache resolver results so a given input packs the same way until inputs change,
SHALL make model involvement visible, and SHALL bound model call volume separately from fallback-rate
measurement.

#### Scenario: Same inputs reuse the cached result
- **WHEN** a task, its OpenSpec artifacts, sidecar signals, candidate set, resolver configuration, and dynamic diff fingerprint are unchanged since a prior resolution
- **THEN** the system SHALL reuse the cached resolver result rather than calling the model again

#### Scenario: Model involvement is visible in diagnostics
- **WHEN** the model resolver contributed to a packet's scope
- **THEN** the diagnostics SHALL show that model-assisted resolution was used and why

#### Scenario: Model call limits are enforced separately from fallback rate
- **WHEN** the model resolver is enabled
- **THEN** the system SHALL enforce explicit per-run or per-pack call limits
- **AND** fallback rate SHALL be reported as an observed accuracy metric rather than treated as a directly enforceable control
