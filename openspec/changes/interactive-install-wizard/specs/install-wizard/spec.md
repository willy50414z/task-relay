## ADDED Requirements

### Requirement: Interactive wizard flow
The system SHALL guide the user through an interactive terminal prompt sequence when `trly install` is invoked without flags.

#### Scenario: Wizard starts without flags
- **WHEN** a user runs `trly install` without any CLI flags
- **THEN** the system SHALL present an interactive prompt sequence: primary agent → scope → mode → (if mode is not main) sub-agent → (for each selected agent) model

#### Scenario: Wizard skipped with flags
- **WHEN** a user runs `trly install` with `--primary`, `--scope`, `--mode`, and optionally `--sub-agent` and `--model` flags
- **THEN** the system SHALL skip the interactive wizard and proceed directly to writing output files

### Requirement: Primary agent selection
The first prompt SHALL ask the user to select a primary orchestration agent.

#### Scenario: User selects claude
- **WHEN** the user selects `claude` as primary agent
- **THEN** the system SHALL use `CLAUDE.md` as the guidance file name and `~/.claude/skills/` (user) or `./.claude/skills/` (project) as the skill path

#### Scenario: User selects codex
- **WHEN** the user selects `codex` as primary agent
- **THEN** the system SHALL use `AGENTS.md` as the guidance file name and `~/.codex/skills/` (user) or `./.codex/skills/` (project) as the skill path

### Requirement: Scope selection
The second prompt SHALL ask the user to select installation scope.

#### Scenario: User scope selected
- **WHEN** the user selects `user` scope
- **THEN** the system SHALL write guidance to the user home directory under the primary agent's native path (`~/.claude/` or `~/.codex/`)

#### Scenario: Project scope selected
- **WHEN** the user selects `project` scope
- **THEN** the system SHALL write guidance to the current working directory (`./CLAUDE.md` or `./AGENTS.md`) and skill bundle to the project-local skill path

### Requirement: Mode selection
The third prompt SHALL ask the user to select a delegation mode.

#### Scenario: Main mode ends wizard
- **WHEN** the user selects `main` mode
- **THEN** the system SHALL clear any existing task-relay managed block from the guidance file and exit without further prompts

#### Scenario: Hybrid mode continues wizard
- **WHEN** the user selects `hybrid` mode
- **THEN** the system SHALL proceed to sub-agent selection

#### Scenario: Delegated-apply mode continues wizard
- **WHEN** the user selects `delegated-apply` mode
- **THEN** the system SHALL proceed to sub-agent selection

### Requirement: Sub-agent selection
When mode is not `main`, the fourth prompt SHALL ask the user to select a sub-agent for delegated work.

#### Scenario: Valid sub-agent chosen
- **WHEN** the user selects `claude`, `codex`, or `deepseek` as sub-agent
- **THEN** the system SHALL record the choice and proceed to model selection for that agent (if applicable)

### Requirement: Model selection
For each agent selected (primary and sub), the system SHALL prompt for a specific model unless a default is sufficient.

#### Scenario: Model prompt for claude agent
- **WHEN** the primary or sub-agent is `claude`
- **THEN** the system SHALL present the Claude model catalog and ask the user to choose one

#### Scenario: Model prompt for codex agent
- **WHEN** the primary or sub-agent is `codex`
- **THEN** the system SHALL present the Codex model catalog and ask the user to choose one

#### Scenario: Default model for deepseek
- **WHEN** the sub-agent is `deepseek`
- **THEN** the system SHALL use `deepseek-v4-pro[1m]` as the default and SHALL ask the user to confirm or override

#### Scenario: Same agent used for both roles
- **WHEN** the primary agent and sub-agent are the same (e.g., both `claude`)
- **THEN** the system SHALL prompt for each role's model separately

### Requirement: Confirmation before write
After all selections, the system SHALL display a summary and ask for confirmation before writing.

#### Scenario: User confirms
- **WHEN** the user confirms the summary
- **THEN** the system SHALL write the managed block and skill bundle

#### Scenario: User declines
- **WHEN** the user declines the summary
- **THEN** the system SHALL exit without writing anything

### Requirement: Non-interactive flag mode
The system SHALL support a non-interactive invocation with flags for scripting use.

#### Scenario: Full non-interactive install
- **WHEN** a user runs `trly install --primary codex --scope project --mode hybrid --sub-agent deepseek --model deepseek=deepseek-v4-pro[1m]`
- **THEN** the system SHALL skip all prompts and write output files directly

#### Scenario: Partial non-interactive requires missing flags
- **WHEN** a user runs `trly install --primary claude` without required flags for the full configuration
- **THEN** the system SHALL fall back to the interactive wizard for remaining choices

### Requirement: Re-run pre-fills from existing state
When a managed block already exists, the wizard SHALL pre-fill defaults from the existing configuration.

#### Scenario: Re-install with existing block
- **WHEN** `trly install` is run in a directory that already has a task-relay managed block
- **THEN** each prompt SHALL show the existing value as the default option
