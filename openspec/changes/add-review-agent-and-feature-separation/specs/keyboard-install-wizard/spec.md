## MODIFIED Requirements

### Requirement: Keyboard-driven selection prompts
The system SHALL present `trly install` interactive choices as keyboard-driven selection prompts when stdin is a TTY and required non-interactive flags are not fully provided. The selection SHALL include a new feature checkbox step and conditional chain configuration steps.

#### Scenario: User navigates choices with keyboard
- **WHEN** a user runs `trly install` in an interactive terminal
- **THEN** the installer SHALL let the user move through installation targets, scope, feature checkboxes, and chain configuration choices with up/down navigation and confirm each choice with Enter

#### Scenario: No features selected exits after clearing
- **WHEN** a user unchecks both review and apply in the feature selection step
- **THEN** the installer SHALL clear the managed block for the selected primary agent and scope and exit without prompting for chains or models

### Requirement: Prompt adapter abstraction
The system SHALL isolate terminal prompting behind an adapter so wizard state transitions can be tested without a real TTY. The adapter SHALL continue to support select, checkbox, and confirm prompt types for all new steps.

#### Scenario: Unit tests supply fake choices
- **WHEN** tests run wizard steps with a fake prompt adapter
- **THEN** the wizard SHALL return the same `WizardState` values that the production prompt would produce for those choices, including the new feature, chain, and fallback fields

#### Scenario: Prompt dependency is unavailable in non-interactive mode
- **WHEN** a user runs a complete non-interactive install with all required flags
- **THEN** the installer SHALL complete without importing or invoking the interactive prompt adapter

### Requirement: Non-interactive fallback
The system SHALL preserve a non-interactive install path for scripts and CI, extended with new flags for features and chains.

#### Scenario: Complete flag set skips prompts
- **WHEN** a user runs `trly install --primary codex --scope project --feature review,apply --review-chain "claude=claude-sonnet-4-6" --apply-chain "deepseek=deepseek-v4-pro[1m]"`
- **THEN** the installer SHALL skip all prompts and write the selected configuration directly

#### Scenario: Missing flags without TTY fails clearly
- **WHEN** stdin is not a TTY and a user runs `trly install` without enough flags to complete installation
- **THEN** the command SHALL fail with a message listing the required non-interactive flags

### Requirement: Existing configuration prefill
The system SHALL prefill interactive defaults from an existing task-relay managed block when the target can be determined unambiguously. Prefill SHALL map legacy mode/sub-agent entries to the new features/chains format.

#### Scenario: Project block seeds defaults
- **WHEN** `./AGENTS.md` contains a task-relay managed block for `primary: codex` and `scope: project`
- **THEN** `trly install` SHALL default the wizard to codex, project scope, the recorded features, and the recorded chain configurations

#### Scenario: Legacy block prefills to new format
- **WHEN** an existing block contains `mode: hybrid` and `sub-agent: deepseek` with model `deepseek-v4-pro[1m]`
- **THEN** the wizard SHALL prefill features with `["apply"]` and the apply-chain with `deepseek=deepseek-v4-pro[1m]`

#### Scenario: Ambiguous existing blocks do not guess
- **WHEN** more than one candidate guidance file contains a task-relay managed block and the user did not provide primary or scope flags
- **THEN** the wizard SHALL use safe defaults and update only the primary and scope selected by the user

## ADDED Requirements

### Requirement: Fallback agent selection loop
The wizard SHALL provide a loop interface for adding fallback agents to a chain. Each iteration SHALL display the current chain state, ask the user to confirm adding another fallback, and if confirmed, prompt for agent selection excluding already-selected agents followed by model selection.

#### Scenario: Fallback loop displays current chain
- **WHEN** the user is in the fallback loop for the review chain and has already selected `claude (claude-sonnet-4-6)`
- **THEN** the wizard SHALL display "Current review chain: claude (sonnet-4-6)" before asking to add a fallback

#### Scenario: Fallback loop excludes already-selected agents
- **WHEN** claude is already the primary and deepseek was added as first fallback
- **THEN** the fallback agent selection SHALL exclude both claude and deepseek, offering only codex

#### Scenario: Fallback loop ends when all agents exhausted
- **WHEN** all three agents have been added to a chain
- **THEN** the wizard SHALL automatically end the fallback loop without prompting

#### Scenario: Fallback agent model selection
- **WHEN** the user selects a fallback agent
- **THEN** the wizard SHALL prompt for the model for that agent, defaulting to the agent's default model
