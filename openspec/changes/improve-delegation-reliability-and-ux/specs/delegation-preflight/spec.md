## ADDED Requirements

### Requirement: Doctor reports delegation readiness across agent, repo, and config layers
The system SHALL provide a `trly doctor` command that evaluates delegation readiness across agent availability, model configuration, repo/worktree conditions, and managed block integrity.

#### Scenario: Doctor reports blocking environment issues
- **WHEN** the user runs `trly doctor` and a required dependency is missing, such as an auth token, CLI binary, or writable guidance path
- **THEN** the command SHALL report the failing check with a blocking status and a concrete remediation message

#### Scenario: Doctor reports overall success
- **WHEN** the user runs `trly doctor` and all required checks pass
- **THEN** the command SHALL report that delegation is ready and include a machine-readable success result

### Requirement: Doctor validates configured targets and models honestly
The system SHALL validate each configured agent target and model reference without reporting success for an unavailable or unusable target.

#### Scenario: DeepSeek check fails without token
- **WHEN** the configured target is `deepseek` and `DEEPSEEK_AUTH_TOKEN` is absent
- **THEN** the corresponding doctor and health checks SHALL report failure instead of `ok=true`

#### Scenario: Configured model is unknown to the local catalog
- **WHEN** a managed block references a model identifier that is not present in the local model catalog
- **THEN** doctor SHALL report the model mismatch and identify the invalid model entry

### Requirement: Doctor detects managed block and scope conflicts
The system SHALL detect conflicting or incomplete delegation configuration across project and user scopes.

#### Scenario: Review feature is enabled without reviewers
- **WHEN** a managed block enables `review` but does not define reviewers
- **THEN** doctor SHALL report the configuration as invalid and explain the missing field

#### Scenario: User and project scopes conflict
- **WHEN** both user-level and project-level managed blocks exist with conflicting target or feature settings
- **THEN** doctor SHALL report the conflict and identify the conflicting files
