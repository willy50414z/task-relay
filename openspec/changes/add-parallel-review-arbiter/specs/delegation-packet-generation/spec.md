## ADDED Requirements

### Requirement: Arbiter packet generation
The system SHALL generate an arbiter packet that includes original OpenSpec planning artifacts, all reviewer outputs, and prior arbiter outputs when applicable.

#### Scenario: Generate first arbiter packet
- **WHEN** the CEO/product arbiter stage is about to run
- **THEN** the packet SHALL include `proposal.md`, `design.md` when present, `tasks.md` when present, delta specs, and every verified reviewer JSON

#### Scenario: Generate later arbiter packet
- **WHEN** a non-first arbiter stage is about to run
- **THEN** the packet SHALL include every prior arbiter JSON in addition to the original artifacts and reviewer JSON

### Requirement: Review arbiter template
The system SHALL install `templates/review-arbiter.md` in the task-relay-delegation skill bundle. The template MUST define a neutral arbiter role, noise filtering, conflict resolution, strict JSON output, and the arbiter non-editor boundary.

#### Scenario: Template installed
- **WHEN** `trly install` creates or updates the task-relay-delegation skill bundle with review enabled
- **THEN** the bundle SHALL include `templates/review-arbiter.md`

#### Scenario: Template requires strict JSON
- **WHEN** an arbiter receives a packet generated from `review-arbiter.md`
- **THEN** the packet SHALL instruct the arbiter to output no extra prose outside the required JSON object

### Requirement: Reviewer packet generation
The system SHALL generate reviewer packets that include the relevant OpenSpec planning artifacts and a single reviewer persona instruction. Reviewer packets MUST declare the reviewer's unique expected output path.

#### Scenario: Generate security reviewer packet
- **WHEN** the review gate invokes `deepseek:/cso`
- **THEN** the packet SHALL include the security reviewer persona and declare a unique security reviewer output path

#### Scenario: Generate QA reviewer packet without runnable app
- **WHEN** no runnable application URL or command is available in the proposal context
- **THEN** the QA reviewer packet SHALL instruct the reviewer to evaluate QA testability and acceptance criteria rather than requiring live browser testing

