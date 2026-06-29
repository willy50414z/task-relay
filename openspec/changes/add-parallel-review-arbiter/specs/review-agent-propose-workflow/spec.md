## ADDED Requirements

### Requirement: Proposal review gate workflow
The system SHALL review OpenSpec proposals through a gate composed of parallel reviewer invocations followed by serial arbiter invocations. The Primary agent SHALL execute apply only when the arbiter outcome is not `REJECT`; `REVISE` requires revision contract application first.

#### Scenario: Proposal enters review gate
- **WHEN** a proposal is ready for delegated review
- **THEN** the Primary agent SHALL package the proposal context and invoke the configured review gate rather than a sequential review-chain

#### Scenario: Review gate returns revise
- **WHEN** the review gate returns final decision `REVISE`
- **THEN** the Primary agent SHALL apply the arbiter's binding revision contract to the relevant OpenSpec artifacts before apply and SHALL NOT be forced to rerun the review gate in the first implementation version

#### Scenario: Revised proposal is optionally resubmitted
- **WHEN** the Primary agent has modified OpenSpec artifacts after a `REVISE` decision and chooses to rerun review
- **THEN** the next review gate run SHALL rerun all configured reviewers and all configured arbiters rather than relying on prior partial artifacts

### Requirement: Machine-readable review-to-apply handoff
The system SHALL write a machine-readable review result artifact after a successful gate run so the Primary agent can programmatically inspect apply readiness.

#### Scenario: Gate writes result artifact
- **WHEN** the review gate completes with `APPROVE`, `REVISE`, or `REJECT`
- **THEN** the system SHALL write a machine-readable result artifact that includes the final decision, reviewer artifact paths, arbiter artifact paths, and aggregated actionable revision items

#### Scenario: Revise records target artifact baselines
- **WHEN** the review gate completes with `REVISE`
- **THEN** the machine-readable result artifact SHALL record the target artifacts referenced by the arbiter contract together with a baseline digest captured at gate time

### Requirement: Revision readiness verification
The system SHALL provide a deterministic revision readiness check for `REVISE` outcomes before apply.

#### Scenario: Pending revision target blocks readiness
- **WHEN** the review result artifact shows `REVISE` and a targeted artifact still matches its gate-time baseline digest
- **THEN** the verification command SHALL report that apply is not yet ready

#### Scenario: Changed revision targets satisfy readiness
- **WHEN** every targeted artifact referenced by the `REVISE` contract differs from its gate-time baseline digest
- **THEN** the verification command SHALL report that apply may proceed

#### Scenario: Review gate returns reject
- **WHEN** the review gate returns final decision `REJECT`
- **THEN** the Primary agent SHALL stop before apply and return the change to propose/explore rather than automatically rewriting the proposal

#### Scenario: Stop does not apply
- **WHEN** the review gate is in STOP due to `REJECT`
- **THEN** the Primary agent SHALL NOT start implementation tasks, apply waves, or delegated apply work for that change

### Requirement: Reviewer non-goals
Proposal reviewers SHALL NOT modify OpenSpec state, mark task checkboxes, perform destructive operations, or make final architecture decisions. Reviewers SHALL only emit independent review JSON.

#### Scenario: Reviewer finds unclear scope
- **WHEN** a reviewer identifies ambiguous scope
- **THEN** the reviewer SHALL report the ambiguity in its JSON findings and SHALL NOT directly edit `proposal.md`, `design.md`, `tasks.md`, or delta specs

### Requirement: Arbiter owns arbitration and Primary applies revisions
The Arbiter SHALL own conflict resolution, final decision, and binding revision requirements. The Primary agent SHALL only edit OpenSpec artifacts to satisfy the Arbiter's revision contract and MUST NOT re-arbitrate reviewer findings or override Arbiter decisions.

#### Scenario: Arbiter gives revision contract
- **WHEN** an arbiter JSON includes binding actionable revision items
- **THEN** the Primary agent SHALL apply those required changes to the specified proposal/design/tasks/spec artifacts and SHALL NOT choose a different reviewer position

#### Scenario: Unadjudicated reviewer suggestion is ignored
- **WHEN** a reviewer suggests a change that the arbiter does not include in the revision contract
- **THEN** the Primary agent SHALL NOT apply that reviewer suggestion directly because revision direction comes only from the arbiter's adjudicated result

#### Scenario: Revision contract is ambiguous
- **WHEN** the Arbiter returns `REVISE` but the actionable items are contradictory, impossible to apply, or do not identify the affected artifact
- **THEN** the Primary agent SHALL request clarification or rerun arbitration rather than inventing its own resolution

#### Scenario: Primary cannot override rejection
- **WHEN** the Arbiter returns `REJECT`
- **THEN** the Primary agent SHALL NOT rewrite the rejection into a revision plan or proceed to apply
