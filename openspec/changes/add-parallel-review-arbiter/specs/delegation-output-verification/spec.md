## ADDED Requirements

### Requirement: Multi-review artifact verification
The system SHALL verify every declared reviewer artifact before starting arbiter execution. Missing, empty, or invalid reviewer output MUST fail the review gate loudly.

#### Scenario: Reviewer artifact missing
- **WHEN** a reviewer invocation exits without creating its declared `delegation_review_<id>.json`
- **THEN** the system SHALL report a named output verification failure and SHALL NOT run arbiters

#### Scenario: Reviewer artifact empty
- **WHEN** a reviewer creates its declared output file but leaves it empty
- **THEN** the system SHALL report a named output verification failure and SHALL NOT treat the reviewer as successful

#### Scenario: Reviewer JSON invalid
- **WHEN** a reviewer output cannot be parsed as JSON or misses required reviewer fields
- **THEN** the system SHALL report a schema verification failure and SHALL NOT run arbiters

### Requirement: Arbiter decision verification
The system SHALL parse and validate every arbiter JSON output before computing the final gate decision.

#### Scenario: Arbiter JSON has invalid decision
- **WHEN** an arbiter output contains `decision` outside `APPROVE`, `REVISE`, or `REJECT`
- **THEN** the system SHALL reject the arbiter output and fail the gate

#### Scenario: Arbiter JSON misses actionable items
- **WHEN** an arbiter output does not contain `actionable_items` as an array
- **THEN** the system SHALL reject the arbiter output and fail the gate

#### Scenario: Revision contract is incomplete
- **WHEN** an arbiter output has `decision` equal to `REVISE` and any actionable item lacks target artifact, required change, or acceptance criteria
- **THEN** the system SHALL reject the arbiter output as an incomplete revision contract and fail the gate

#### Scenario: Arbiter output is valid
- **WHEN** every required arbiter field is present with a valid type and enum value
- **THEN** the system SHALL allow final decision aggregation to proceed

### Requirement: Final review summary artifact
The system SHALL produce or update a final human-readable review summary artifact after successful arbiter verification. The summary MUST preserve links or paths to individual reviewer and arbiter JSON files.

#### Scenario: Gate completes with revise
- **WHEN** the review gate returns `REVISE`
- **THEN** the final summary SHALL include the final decision, arbiter summaries, actionable items, and reviewer artifact paths

#### Scenario: Gate completes with approve
- **WHEN** the review gate returns `APPROVE`
- **THEN** the final summary SHALL include the approval decision and reviewer/arbiter artifact paths for auditability
