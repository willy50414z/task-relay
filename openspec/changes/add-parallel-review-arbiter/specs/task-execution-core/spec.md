## ADDED Requirements

### Requirement: Parallel subprocess review execution
The execution layer SHALL provide a review gate runner that can start reviewer subprocesses concurrently with asynchronous subprocess execution and wait for all required reviewer results.

#### Scenario: Reviewer subprocess commands
- **WHEN** the review gate starts reviewer execution
- **THEN** each reviewer SHALL be invoked through the existing task-relay agent execution path or equivalent `trly run --target <agent> --prompt-file <packet> --expect-output <unique-path>` command

#### Scenario: Async subprocess fan-out
- **WHEN** more than one reviewer is configured
- **THEN** the execution layer SHALL start reviewer `trly run` subprocesses through an asynchronous fan-out mechanism and wait for them as a group

#### Scenario: Gather reviewer results
- **WHEN** all reviewer subprocesses finish successfully
- **THEN** the execution layer SHALL return the collected reviewer artifact metadata to arbiter execution

### Requirement: Serial arbiter subprocess execution
The execution layer SHALL provide an arbiter runner that invokes arbiter stages one at a time in configured order.

#### Scenario: First arbiter rejects
- **WHEN** the first arbiter emits valid JSON with `decision` equal to `REJECT`
- **THEN** the execution layer MAY stop subsequent arbiter execution and SHALL return final gate decision `REJECT`

#### Scenario: First arbiter approves
- **WHEN** the first arbiter emits valid JSON with `decision` equal to `APPROVE` and another arbiter remains
- **THEN** the execution layer SHALL invoke the next arbiter with the first arbiter JSON included in its packet

### Requirement: Review gate errors are typed
The execution layer SHALL expose named failures for review gate timeout, reviewer output verification failure, arbiter output verification failure, and final decision aggregation failure.

#### Scenario: Invalid arbiter schema
- **WHEN** an arbiter output is invalid JSON
- **THEN** the execution layer SHALL raise or report a named arbiter output verification failure rather than returning generic success

#### Scenario: No arbiter configured
- **WHEN** reviewers are configured but no arbiter is configured
- **THEN** the execution layer SHALL reject the review gate configuration because final DAG decision cannot be computed independently

### Requirement: Review gate revision and stop are not infrastructure failures
The execution layer SHALL distinguish final arbiter decisions from infrastructure failures so the Primary can programmatically choose the next workflow step.

#### Scenario: Revision decision returned
- **WHEN** arbiter aggregation returns `REVISE`
- **THEN** the execution layer SHALL expose a structured result that identifies revision as a valid gate outcome rather than an exception

#### Scenario: Stop decision returned
- **WHEN** arbiter aggregation returns `REJECT`
- **THEN** the execution layer SHALL expose a structured result that identifies stop as a valid gate outcome rather than an exception
