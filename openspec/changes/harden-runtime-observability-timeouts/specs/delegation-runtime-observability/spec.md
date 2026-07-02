## ADDED Requirements

### Requirement: Delegate jobs expose runtime diagnostics
The system SHALL persist structured runtime diagnostics for managed delegate jobs so operators can understand process status, semantic contract status, timeout policy, activity timestamps, and related artifacts after the job completes or fails.

#### Scenario: Job diagnostics are written for a managed delegate
- **WHEN** a managed delegate job starts through blocking, async, apply, or review orchestration
- **THEN** the system SHALL create a diagnostics artifact for the job or record a diagnostics write error in job metadata
- **AND** the diagnostics SHALL include job id, target, model when known, role when known, change/task when known, timeout policy summary, log paths, expected outputs, and current diagnostic schema version

#### Scenario: Metadata links to diagnostics
- **WHEN** a diagnostics artifact is created for a job
- **THEN** the job metadata SHALL include the diagnostics artifact path
- **AND** `trly jobs status <job-id>` SHALL expose that path without requiring the operator to inspect the filesystem manually

### Requirement: Context-packer report is captured before delegation
The system SHALL capture a structured context-packer report before invoking a delegate with a generated packet.

#### Scenario: Apply captures packet diagnostics
- **WHEN** `trly apply` builds an implementation-draft or test-draft packet
- **THEN** the system SHALL write a machine-readable context-packer report before starting the delegate job
- **AND** the report SHALL include `selection_mode`, `byte_estimate`, `budget_status`, `budget_limit_bytes`, `trimmed_sections`, `missing_signals`, `repo_context_gap`, selected `sections`, selected `repo_references`, cache-layout byte counts when enabled, and a packet hash

#### Scenario: Review captures packet diagnostics
- **WHEN** the review gate builds a reviewer or arbiter packet
- **THEN** the system SHALL write a machine-readable context-packer report associated with the reviewer or arbiter id before starting that subprocess
- **AND** the review job diagnostics SHALL link to the report path

#### Scenario: Missing packer signals are visible
- **WHEN** packet assembly reports missing signals, repo context gaps, budget trimming, or a budget violation
- **THEN** the apply or review debug summary SHALL mark the context-packer observation as `warn` or `fail`
- **AND** the summary SHALL include enough detail for the primary agent to decide whether to accept, retry with more context, or revise task metadata

### Requirement: Trace records link runtime, packer, and job artifacts
The system SHALL enrich delegation trace records with references needed to correlate runtime behavior, packet construction, and job logs.

#### Scenario: Successful delegation trace links artifacts
- **WHEN** a delegate job completes successfully and a trace record is appended
- **THEN** the trace record SHALL include job id, job log path, diagnostics path when available, packer report path when available, target, model, role, change/task, duration, outcome, retries, and token usage when available

#### Scenario: Failed delegation trace links artifacts
- **WHEN** a delegate job fails due to timeout, quota, process error, semantic contract failure, or output validation failure
- **THEN** the trace record SHALL include the same artifact links as a successful delegation when available
- **AND** it SHALL include a machine-readable failure kind

### Requirement: Semantic contract failures are not reported as success
The system SHALL distinguish process success from pipeline semantic success.

#### Scenario: Process exits zero but expected output is missing
- **WHEN** a delegate process exits with code zero but a declared expected output is missing, empty, or unreadable
- **THEN** the final job status SHALL NOT be `succeeded`
- **AND** diagnostics SHALL record `process_status` as successful and `contract_status` as failed with the expected output reason

#### Scenario: Review JSON fails schema validation
- **WHEN** a reviewer or arbiter writes a JSON artifact that is invalid JSON or does not match the required review schema
- **THEN** the review gate SHALL treat the artifact as a semantic contract failure
- **AND** diagnostics SHALL include the artifact path and validation error

#### Scenario: Interactive delegate output is not accepted as review success
- **WHEN** a review delegate exits zero and stdout asks for routing, confirmation, or user preference instead of producing the required artifact
- **THEN** the job SHALL fail through expected-output or schema validation
- **AND** diagnostics SHALL identify the output as semantically unusable when that can be detected from stdout/stderr

### Requirement: Parent quota failures are resumable orchestration failures
The system SHALL record hard quota or usage-limit failures in parent orchestration as resumable failures when enough workflow context is known.

#### Scenario: Codex parent hits usage limit
- **WHEN** a Codex parent orchestration job fails with a hard quota or usage-limit message
- **THEN** the system SHALL classify the failure as `parent_quota_exhausted`
- **AND** it SHALL write resume metadata including target, model, job id, log path, workflow phase when known, last known change/task/session when known, retry-after or next-available hint when parsable, and suggested resume action

#### Scenario: Resume metadata is visible in diagnostics
- **WHEN** a parent quota failure has resume metadata
- **THEN** job diagnostics and trace records SHALL expose the resume metadata path or inline summary
- **AND** the parent flow SHALL NOT attribute the failure to the delegate backend that was not running
