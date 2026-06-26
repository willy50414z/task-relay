## ADDED Requirements

### Requirement: Review agent role definition
The system SHALL support a review agent role that reviews OpenSpec proposals for requirement clarity, direction correctness, and implementation plan completeness. The review agent SHALL operate independently from the apply agent and SHALL be called by the primary agent during the propose phase.

#### Scenario: Review agent is configured separately from apply agent
- **WHEN** a user installs task-relay delegation with review feature enabled
- **THEN** the managed block SHALL contain a `review-chain` entry independent from `apply-chain`

#### Scenario: Review agent reviews proposal content
- **WHEN** the primary agent calls the review agent with a proposal for review
- **THEN** the review agent SHALL evaluate requirement clarity, direction correctness, and implementation plan completeness

### Requirement: Review proposal prompt template
The system SHALL provide a `review-proposal.md` prompt template in the task-relay-delegation skill bundle. The template SHALL define review dimensions including requirement clarity, direction correctness, implementation plan completeness, and user intent alignment.

#### Scenario: Template is installed with skill bundle
- **WHEN** `trly install` creates a `task-relay-delegation` skill bundle with review feature enabled
- **THEN** the bundle SHALL include `templates/review-proposal.md` copied from package assets

#### Scenario: Template defines review dimensions
- **WHEN** the primary agent reads the review-proposal template
- **THEN** the template SHALL include sections for requirement clarity, direction correctness, implementation plan completeness, and guidance to ask the user rather than defining solutions independently

### Requirement: Review agent output specification
The review agent SHALL write its review findings to `spec/delegent_review.md` within the relevant OpenSpec change directory. The output SHALL be a structured report with findings ordered by severity.

#### Scenario: Review agent writes findings
- **WHEN** the review agent completes its review
- **THEN** it SHALL create `spec/delegent_review.md` in the change directory with severity-ranked findings

#### Scenario: Primary agent references review findings
- **WHEN** the review agent completes and writes `spec/delegent_review.md`
- **THEN** the primary agent SHALL read the review findings and may modify the proposal, design, or tasks based on the feedback

### Requirement: Review agent interaction boundaries
The review agent SHALL NOT modify OpenSpec state, mark tasks checkboxes, perform destructive operations, or make architecture decisions. The review agent SHALL ask the user when encountering ambiguity rather than defining solutions independently.

#### Scenario: Review agent asks user on ambiguity
- **WHEN** the review agent encounters an unclear requirement or ambiguous design decision
- **THEN** the review agent SHALL raise the question to the user instead of assuming or defining a solution

#### Scenario: Review agent does not modify OpenSpec artifacts
- **WHEN** the review agent completes its review
- **THEN** it SHALL NOT modify `tasks.md` checkboxes or change `proposal.md`, `design.md`, or other OpenSpec artifact files

### Requirement: Review agent tool access
The review agent MAY use gstack-related skills and other available tools to validate existing behavior, explore the codebase, or verify claims made in the proposal when such validation supports the review.

#### Scenario: Review agent uses gstack for validation
- **WHEN** the review agent needs to verify existing application behavior referenced in a proposal
- **THEN** the review agent MAY invoke gstack browser testing skills to confirm the behavior
