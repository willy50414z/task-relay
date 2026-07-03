## ADDED Requirements

### Requirement: Reviewer profiles select personas
The review gate SHALL support explicit reviewer profiles that expand to reviewer persona lists. Reviewer profiles SHALL select personas only and SHALL NOT select concrete agent/model entries.

#### Scenario: Standard reviewer profile expands to two personas
- **WHEN** the review gate runs with the default reviewer profile
- **THEN** it SHALL select the `standard` reviewer profile
- **AND** it SHALL run `/review` and `/devils-advocate` reviewer personas

#### Scenario: Strict reviewer profile expands to all required review personas
- **WHEN** the review gate runs with reviewer profile `strict`
- **THEN** it SHALL run `/review`, `/devils-advocate`, `/qa-only`, and `/cso` reviewer personas

### Requirement: Review agents are fallback execution candidates
The review gate SHALL treat configured review agents as fallback execution candidates. For profile-based review, the gate SHALL select one effective review agent/model and SHALL run each selected reviewer persona through that same selected agent/model.

#### Scenario: One selected agent runs multiple personas
- **WHEN** a managed review config contains one or more reviewer entries
- **AND** the selected reviewer profile contains multiple personas
- **THEN** the gate SHALL select one effective reviewer agent/model from the configured reviewer entries
- **AND** it SHALL run every selected reviewer persona through that same agent/model

#### Scenario: Reviewer personas run in parallel
- **WHEN** the selected reviewer profile contains multiple personas
- **THEN** the gate SHALL launch the reviewer persona jobs in parallel
- **AND** each persona job SHALL receive a unique expected output path

### Requirement: Arbiter profiles select arbitration personas
The review gate SHALL support explicit arbiter profiles that expand to arbiter persona lists. The default arbiter profile SHALL be `engineering`, and product-heavy review SHALL be selectable through an arbiter profile override.

#### Scenario: Default arbiter profile is engineering
- **WHEN** the review gate needs arbitration and no arbiter profile override is provided
- **THEN** it SHALL use the `engineering` arbiter profile
- **AND** it SHALL run `/plan-eng-review`

#### Scenario: Product arbiter profile uses product arbitration
- **WHEN** the review gate needs arbitration with arbiter profile `product`
- **THEN** it SHALL run `/plan-ceo-review`

#### Scenario: Strict arbiter profile runs serial arbitration
- **WHEN** the review gate needs arbitration with arbiter profile `strict`
- **THEN** it SHALL run `/plan-eng-review` and `/plan-ceo-review` as serial arbiter personas

### Requirement: Reducer approves only clean PASS results
The review gate SHALL use a deterministic reducer before arbitration. The reducer SHALL approve and skip arbitration only when every required reviewer persona produced a valid artifact with verdict `PASS`.

#### Scenario: All reviewers pass
- **WHEN** every selected reviewer persona produces a valid artifact
- **AND** every artifact has verdict `PASS`
- **THEN** the review gate SHALL produce an `APPROVE` result
- **AND** it SHALL skip arbiter execution

#### Scenario: Concerns require arbitration
- **WHEN** any valid reviewer artifact has verdict `CONCERNS`
- **THEN** the review gate SHALL run the selected arbiter profile

#### Scenario: Blocked review requires arbitration
- **WHEN** any valid reviewer artifact has verdict `BLOCKED`
- **THEN** the review gate SHALL run the selected arbiter profile

#### Scenario: Strict reviewer profile does not force arbitration on clean pass
- **WHEN** the selected reviewer profile is `strict`
- **AND** every selected reviewer artifact is valid and has verdict `PASS`
- **THEN** the review gate SHALL skip arbiter execution

### Requirement: Reviewer artifact validation is enforced
The review gate SHALL validate reviewer artifacts before reducer decisions. Reviewer artifacts MUST be valid JSON objects with required fields, valid verdicts, valid findings, and persona-specific required fields.

#### Scenario: PASS artifact with findings is invalid
- **WHEN** a reviewer artifact has verdict `PASS`
- **AND** the artifact contains one or more findings
- **THEN** the gate SHALL reject the artifact as invalid
- **AND** it SHALL trigger reviewer artifact retry behavior

#### Scenario: Devils advocate artifact requires adversarial fields
- **WHEN** the reviewer persona is `/devils-advocate`
- **THEN** the reviewer artifact MUST include `fatal_flaw`, `simpler_alternative`, and `reverse_case`
- **AND** the gate SHALL reject the artifact as invalid when any required adversarial field is missing

### Requirement: Invalid reviewer artifacts are retried once
When a reviewer artifact is missing, invalid JSON, schema-invalid, or semantically inconsistent, the review gate SHALL retry the same selected agent/persona once with a corrective prompt. If the retry artifact is still invalid, the gate SHALL abandon that reviewer persona and record failure metadata.

#### Scenario: Retry prompt includes validation details
- **WHEN** a reviewer artifact is invalid
- **THEN** the gate SHALL launch one retry for the same selected agent and persona
- **AND** the retry prompt SHALL include validation errors, the required output path, schema rules, and a valid JSON example

#### Scenario: Invalid retry is abandoned
- **WHEN** a reviewer artifact retry also produces an invalid artifact
- **THEN** the gate SHALL mark that reviewer persona as abandoned
- **AND** it SHALL record validation errors and retry metadata in the review result

#### Scenario: All reviewers abandoned fails the gate
- **WHEN** every selected reviewer persona is abandoned after retry
- **THEN** the review gate SHALL fail rather than approve or arbitrate

#### Scenario: Abandoned persona prevents PASS-only approval
- **WHEN** at least one selected reviewer persona is abandoned after retry
- **AND** at least one valid reviewer artifact exists
- **AND** every valid reviewer artifact has verdict `PASS`
- **THEN** the review gate SHALL run the selected arbiter profile
- **AND** it SHALL include abandoned reviewer metadata for the arbiter

### Requirement: Reviewer verdict vocabulary includes concerns
Reviewer artifacts SHALL support verdict values `PASS`, `CONCERNS`, and `BLOCKED`. `CONCERNS` SHALL represent ambiguous risk that requires arbiter judgment.

#### Scenario: Concerns are not final approval
- **WHEN** a reviewer artifact has verdict `CONCERNS`
- **THEN** the deterministic reducer SHALL NOT approve the review step
- **AND** the selected arbiter profile SHALL determine the final decision

### Requirement: Canonical artifact helper is available
The system SHALL provide a canonical Python helper for writing and validating reviewer and arbiter artifacts. The helper SHALL normalize stable JSON formatting and SHALL enforce the same schema rules used by the review gate.

#### Scenario: Reviewer helper writes stable artifact JSON
- **WHEN** a delegate uses the reviewer artifact helper with a valid reviewer payload and output path
- **THEN** the helper SHALL write a stable JSON object to the output path
- **AND** the review gate SHALL accept the artifact during validation

#### Scenario: Invalid helper payload is rejected
- **WHEN** a delegate calls the artifact helper with an invalid payload
- **THEN** the helper SHALL reject the payload
- **AND** it SHALL report validation errors instead of writing a misleading successful artifact

### Requirement: Review result records profile and reducer metadata
The review gate SHALL record reviewer profile, arbiter profile, selected personas, selected execution agent, reducer decision, arbiter invocation state, retry attempts, abandoned reviewers, and skip reasons in the machine-readable review result.

#### Scenario: Clean PASS result records skipped arbitration
- **WHEN** the reducer approves a review because every reviewer passed
- **THEN** the review result SHALL include the selected reviewer profile
- **AND** it SHALL include the selected arbiter profile
- **AND** it SHALL record that arbiter execution was skipped because all reviewer artifacts passed

#### Scenario: Abandoned reviewer metadata is visible
- **WHEN** a reviewer persona is abandoned after retry
- **THEN** the review result SHALL include the abandoned persona, retry count, and validation errors

### Requirement: Existing explicit overrides remain compatible
The review gate SHALL preserve explicit reviewer and arbiter override behavior. Explicit reviewer overrides SHALL bypass reviewer profile expansion and SHALL be recorded as manual override profile source. Explicit arbiter overrides SHALL replace the selected arbiter profile when arbitration is required.

#### Scenario: Explicit reviewers bypass reviewer profile
- **WHEN** the caller provides explicit reviewer entries
- **THEN** the gate SHALL use those reviewer entries instead of expanding the reviewer profile
- **AND** the review result SHALL record profile source `manual_override`

#### Scenario: Explicit arbiter override is conditional
- **WHEN** the caller provides explicit arbiter entries
- **AND** every reviewer artifact is valid and has verdict `PASS`
- **THEN** the gate SHALL skip arbiter execution
- **AND** it SHALL record that explicit arbiters were not invoked because arbitration was not required
