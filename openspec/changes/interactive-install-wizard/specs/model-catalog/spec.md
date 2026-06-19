## ADDED Requirements

### Requirement: Hardcoded model registry
The system SHALL maintain a hardcoded model catalog in `task_relay/models.py` with models for Claude, Codex, and DeepSeek.

#### Scenario: Claude models defined
- **WHEN** the model catalog is imported
- **THEN** `CLAUDE_MODELS` SHALL contain entries for all current Claude models with `id`, `name`, `tier`, and `provider` fields

#### Scenario: Codex models defined
- **WHEN** the model catalog is imported
- **THEN** `CODEX_MODELS` SHALL contain entries for all current Codex models with `id`, `name`, `tier`, and `provider` fields

#### Scenario: DeepSeek models defined
- **WHEN** the model catalog is imported
- **THEN** `DEEPSEEK_MODELS` SHALL contain at minimum `deepseek-v4-pro[1m]`

### Requirement: Model catalog accessor
The system SHALL provide a function to retrieve the model catalog for a given agent name.

#### Scenario: Get catalog for claude
- **WHEN** `get_catalog("claude")` is called
- **THEN** the function SHALL return the Claude model list

#### Scenario: Get catalog for codex
- **WHEN** `get_catalog("codex")` is called
- **THEN** the function SHALL return the Codex model list

#### Scenario: Get catalog for deepseek
- **WHEN** `get_catalog("deepseek")` is called
- **THEN** the function SHALL return the DeepSeek model list

#### Scenario: Unknown agent raises error
- **WHEN** `get_catalog("unknown")` is called
- **THEN** the function SHALL raise `ValueError`

### Requirement: Model display formatting
The system SHALL format model lists for terminal display with numeric selection.

#### Scenario: Display with tier info
- **WHEN** a model catalog is formatted for display
- **THEN** each model SHALL be shown with a number, model ID, display name, and tier description

### Requirement: GitHub Action update workflow
The system SHALL include a GitHub Actions workflow that periodically updates the model catalog.

#### Scenario: Scheduled weekly run
- **WHEN** the scheduled workflow triggers (weekly)
- **THEN** the workflow SHALL fetch current model lists from Anthropic and OpenAI APIs, compare with `task_relay/models.py`, and create a PR if differences exist

#### Scenario: Manual trigger
- **WHEN** a maintainer triggers the workflow via `workflow_dispatch`
- **THEN** the workflow SHALL run the same update-and-PR process

#### Scenario: No changes detected
- **WHEN** the fetched model lists match the current hardcoded catalog
- **THEN** the workflow SHALL exit without creating a PR
