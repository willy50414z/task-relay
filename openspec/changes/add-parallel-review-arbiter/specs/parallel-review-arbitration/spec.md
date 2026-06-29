## ADDED Requirements

### Requirement: Parallel reviewer fan-out
The system SHALL execute configured proposal reviewers in parallel during the review gate. Each reviewer invocation MUST receive an isolated output path and MUST NOT overwrite another reviewer's artifact.

#### Scenario: Multiple reviewers run concurrently
- **WHEN** the review gate is configured with reviewers `claude:/review,deepseek:/cso,codex:/qa-only`
- **THEN** the system SHALL start all configured reviewer invocations without waiting for an earlier reviewer to finish before starting the next reviewer

#### Scenario: Reviewer artifacts are isolated
- **WHEN** multiple reviewers are invoked for the same OpenSpec change
- **THEN** each reviewer SHALL receive a unique expected output path such as `spec/delegation_review_review.json`, `spec/delegation_review_cso.json`, or `spec/delegation_review_qa-only.json`

#### Scenario: Same agent appears more than once
- **WHEN** the reviewer list contains the same agent with different personas
- **THEN** the system SHALL generate distinct reviewer ids and distinct expected output paths for each invocation

#### Scenario: Different agents use the same persona
- **WHEN** the reviewer list contains `claude:/review` and `deepseek:/review`
- **THEN** the system SHALL include both agent and persona in each reviewer id so the two reviewers write different artifacts

### Requirement: Serial arbiter chain
The system SHALL execute configured arbiters serially after all required reviewer artifacts have been collected. Each arbiter stage MUST read the original OpenSpec artifacts, all reviewer outputs, and any prior arbiter outputs.

#### Scenario: CEO arbiter precedes engineering arbiter
- **WHEN** the arbiter chain is configured as `claude:/plan-ceo-review,claude:/plan-eng-review`
- **THEN** the system SHALL run the CEO/product arbiter first and the engineering arbiter second

#### Scenario: Later arbiter receives previous decision
- **WHEN** an earlier arbiter stage emits a valid decision JSON
- **THEN** the next arbiter stage SHALL receive that JSON as part of its arbitration packet

#### Scenario: Arbiter is required
- **WHEN** the review gate configuration contains reviewers but no arbiter entries
- **THEN** the system SHALL reject the configuration before invoking reviewers because no independent final decision source exists

### Requirement: Programmatic gate decision
The system SHALL compute the final review gate result from arbiter JSON decisions in CLI/runtime code. The arbiter prompt MUST NOT contain the DAG transition logic.

#### Scenario: All arbiters approve
- **WHEN** every arbiter output has `decision` equal to `APPROVE`
- **THEN** the review gate SHALL return final decision `APPROVE` and unlock the subsequent Apply Wave

#### Scenario: Any arbiter requests revision
- **WHEN** no arbiter rejects and at least one arbiter output has `decision` equal to `REVISE`
- **THEN** the review gate SHALL return final decision `REVISE`, require the Primary agent to revise OpenSpec artifacts, and allow apply after the revision contract is satisfied

#### Scenario: Any arbiter rejects
- **WHEN** any arbiter output has `decision` equal to `REJECT`
- **THEN** the review gate SHALL return final decision `REJECT` and enter STOP without unlocking apply

### Requirement: Global timeout
The system SHALL support a global timeout for the complete review gate. Timeout handling MUST fail loudly and MUST NOT silently treat missing reviewer or arbiter artifacts as approval.

#### Scenario: Reviewer exceeds timeout
- **WHEN** a reviewer subprocess does not finish before the configured global timeout
- **THEN** the system SHALL stop waiting for the gate, report a timeout failure, and not run apply

#### Scenario: Arbiter exceeds timeout
- **WHEN** an arbiter subprocess does not finish before the configured global timeout
- **THEN** the system SHALL report a timeout failure and not infer a decision from partial output

### Requirement: Reviewer failure policy
The system SHALL treat every configured reviewer as required in the first review gate version. Any reviewer execution, timeout, output verification, or schema failure MUST fail the gate before arbiter execution.

#### Scenario: One reviewer fails
- **WHEN** three reviewers are configured and one reviewer fails to produce valid JSON
- **THEN** the system SHALL fail the review gate and SHALL NOT send the two successful reviewer reports to arbiters as a partial review

#### Scenario: Reviewer verdict is blocked
- **WHEN** a reviewer emits valid JSON with advisory `verdict` equal to `BLOCKED`
- **THEN** the system SHALL still pass the report to arbiter execution and SHALL NOT compute the final DAG decision from reviewer verdict alone

### Requirement: Review gate command exit codes
The review gate CLI SHALL expose stable exit codes for programmatic Primary decisions.

#### Scenario: Gate approves
- **WHEN** the final decision is `APPROVE`
- **THEN** the review gate command SHALL exit with code `0`

#### Scenario: Gate requests revision
- **WHEN** the final decision is `REVISE`
- **THEN** the review gate command SHALL exit with a documented nonzero revision code distinct from runtime failure

#### Scenario: Gate rejects
- **WHEN** the final decision is `REJECT`
- **THEN** the review gate command SHALL exit with a documented nonzero stop code distinct from revision and runtime failure

#### Scenario: Gate infrastructure fails
- **WHEN** reviewer execution, arbiter execution, schema validation, configuration validation, or timeout fails
- **THEN** the review gate command SHALL exit with an infrastructure failure code and SHALL NOT encode the failure as `REVISE` or `REJECT`
