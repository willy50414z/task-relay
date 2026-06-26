## ADDED Requirements

### Requirement: Feature checkbox selection
The system SHALL present a checkbox step during `trly install` that allows users to independently select which delegation features to enable: review, apply, both, or neither. Selecting neither SHALL be equivalent to mode=main (no delegation).

#### Scenario: User selects both review and apply
- **WHEN** a user runs `trly install` and checks both "Review" and "Apply" in the feature selection step
- **THEN** the wizard SHALL proceed to configure review chain and apply chain independently

#### Scenario: User selects review only
- **WHEN** a user checks only "Review" in the feature selection step
- **THEN** the wizard SHALL proceed to configure the review chain and skip the apply chain configuration

#### Scenario: User selects apply only
- **WHEN** a user checks only "Apply" in the feature selection step
- **THEN** the wizard SHALL proceed to configure the apply chain and skip the review chain configuration

#### Scenario: User selects neither feature
- **WHEN** a user unchecks both "Review" and "Apply" in the feature selection step
- **THEN** the wizard SHALL clear any existing managed block and exit, equivalent to mode=main

### Requirement: Review chain configuration wizard
When the review feature is selected, the system SHALL guide the user through selecting a primary review agent, its model, and optional fallback agents with models in a loop until the user declines or no more agents are available.

#### Scenario: Primary review agent and model selection
- **WHEN** the user proceeds to review chain configuration
- **THEN** the wizard SHALL prompt for a primary review agent (select from claude, codex, deepseek) followed by model selection

#### Scenario: Fallback agent loop
- **WHEN** the user has selected a primary review agent and model
- **THEN** the wizard SHALL ask whether to add a fallback agent, prompt for agent selection (excluding already-selected agents), prompt for model, and repeat until the user declines or all agents are exhausted

#### Scenario: Current chain display during fallback loop
- **WHEN** the user is adding fallback agents
- **THEN** the wizard SHALL display the current review chain (agent=model pairs in order) before each fallback prompt

### Requirement: Apply chain configuration wizard
When the apply feature is selected, the system SHALL guide the user through the same chain configuration pattern as review: primary apply agent, model, and optional fallback agents with models.

#### Scenario: Primary apply agent and model selection
- **WHEN** the user proceeds to apply chain configuration
- **THEN** the wizard SHALL prompt for a primary apply agent (select from claude, codex, deepseek) followed by model selection

#### Scenario: Apply fallback loop mirrors review fallback loop
- **WHEN** the user adds fallback agents for the apply chain
- **THEN** the wizard SHALL use the same loop pattern as review fallback configuration

### Requirement: Installation summary confirmation
The system SHALL display a structured summary of all selected configuration before writing, including installation targets, scope, enabled features, each chain (agent=model pairs), and confirm before writing.

#### Scenario: Summary shows all configuration
- **WHEN** the user reaches the confirmation step
- **THEN** the wizard SHALL display installation targets, scope, each enabled feature with its agent chain (formatted as "agent (model) → agent (model)"), and require confirmation before writing

### Requirement: Non-interactive feature flags
The system SHALL support non-interactive installation of review and apply chains via CLI flags `--feature`, `--review-chain`, and `--apply-chain`.

#### Scenario: Non-interactive install with review and apply chains
- **WHEN** a user runs `trly install --primary codex --scope project --feature review,apply --review-chain "claude=claude-sonnet-4-6,deepseek=deepseek-v4-pro[1m]" --apply-chain "deepseek=deepseek-v4-pro[1m],codex=gpt-5.5-medium"`
- **THEN** the installer SHALL write the managed block with both chains without prompting

#### Scenario: Non-interactive install with feature=none clears delegation
- **WHEN** a user runs `trly install --primary codex --scope project --feature none`
- **THEN** the installer SHALL clear any existing managed block, equivalent to mode=main
