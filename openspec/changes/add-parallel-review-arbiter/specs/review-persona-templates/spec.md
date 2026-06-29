## ADDED Requirements

### Requirement: Reviewer persona templates
The system SHALL provide reviewer persona templates derived from gstack expert skills. Templates MUST be read-only review instructions and MUST require structured JSON output.

#### Scenario: Code review persona
- **WHEN** a reviewer uses the `/review` persona
- **THEN** the template SHALL instruct the reviewer to inspect plan intent, scope drift, data safety, LLM trust boundaries, edge cases, and missing tests without modifying project files

#### Scenario: Security persona
- **WHEN** a reviewer uses the `/cso` persona
- **THEN** the template SHALL instruct the reviewer to inspect threat model, secrets, dependency supply chain, CI/CD, LLM security, OWASP/STRIDE risks, and exploitability without modifying project files

#### Scenario: QA persona
- **WHEN** a reviewer uses the `/qa-only` persona for a proposal that does not expose a running application
- **THEN** the template SHALL instruct the reviewer to evaluate testability, user-facing acceptance criteria, likely regression areas, and missing verification steps without requiring browser execution

#### Scenario: Persona source recorded
- **WHEN** a reviewer persona template is installed
- **THEN** the template SHALL record the source gstack skill name and extraction date or equivalent provenance metadata

### Requirement: Arbiter persona templates
The system SHALL provide arbiter persona templates for serial product and engineering arbitration. Arbiter templates MUST require strict JSON output and MUST prohibit modifying code or OpenSpec artifacts.

#### Scenario: CEO product arbiter
- **WHEN** an arbiter uses the `/plan-ceo-review` persona
- **THEN** the template SHALL instruct the arbiter to judge product value, scope correctness, requirement completeness, and whether the proposal is worth applying before technical feasibility is considered

#### Scenario: Engineering arbiter
- **WHEN** an arbiter uses the `/plan-eng-review` persona
- **THEN** the template SHALL instruct the arbiter to judge architecture, data flow, migration risk, test coverage, performance, deployment safety, and implementation feasibility

### Requirement: Strict arbiter JSON schema
The review arbiter template SHALL require the arbiter to output only JSON with `decision`, `confidence`, `summary`, `actionable_items`, and `conflict_resolution` fields. When `decision` is `REVISE`, `actionable_items` MUST form a binding revision contract with affected artifacts, required changes, and acceptance criteria.

#### Scenario: Arbiter outputs valid approval
- **WHEN** an arbiter decides the proposal can proceed
- **THEN** it SHALL output JSON whose `decision` is `APPROVE`, `confidence` is a number from 0.0 to 1.0, and `actionable_items` is an array

#### Scenario: Arbiter outputs valid revision
- **WHEN** an arbiter decides the proposal requires revision
- **THEN** it SHALL output `actionable_items` that identify the target artifact, required change, and acceptance criteria for each required revision

#### Scenario: Arbiter resolves reviewer conflict
- **WHEN** reviewer reports disagree on a material issue
- **THEN** the arbiter JSON SHALL explain the adopted position in `conflict_resolution`

#### Scenario: Arbiter has no conflicts
- **WHEN** reviewer reports do not materially conflict
- **THEN** the arbiter JSON SHALL set `conflict_resolution` to `No conflicts`

### Requirement: Arbiter role boundary
The review arbiter template SHALL state that the arbiter is a model call responsible for decision JSON and binding revision contract, but not direct file edits. The CLI/runtime MUST own all DAG transition logic, and the Primary MUST only apply the revision contract without re-arbitrating reviewer conflicts.

#### Scenario: Arbiter requests revision
- **WHEN** the arbiter emits `decision` equal to `REVISE`
- **THEN** the arbiter SHALL NOT edit proposal files and the Primary agent SHALL apply the Arbiter's required changes without changing the Arbiter's decision

#### Scenario: Advisory fields do not override decision
- **WHEN** the arbiter emits advisory fields such as `confidence`
- **THEN** the CLI/runtime SHALL not use those advisory fields to override the explicit `decision` enum in the first implementation version
