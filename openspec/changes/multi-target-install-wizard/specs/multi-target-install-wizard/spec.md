## ADDED Requirements

### Requirement: Multi-target install selection
The system SHALL let `trly install` select one or more installation targets in a single interactive run instead of requiring exactly one primary orchestration agent.

#### Scenario: User selects both target agents
- **WHEN** a user runs `trly install` in an interactive terminal and selects both `codex` and `claude` in the install target prompt
- **THEN** the installer SHALL accept the selection and continue with one shared configuration flow for both targets

#### Scenario: Keyboard behavior for target selection
- **WHEN** the interactive install target prompt is shown
- **THEN** the installer SHALL support Space to toggle each target and Enter to submit the selected targets

### Requirement: Shared configuration across selected targets
The system SHALL apply the same selected scope, mode, sub-agent, and sub-agent model configuration to every install target chosen in the wizard run.

#### Scenario: Shared delegated configuration is written to both targets
- **WHEN** a user selects `codex` and `claude`, chooses `project` scope, `hybrid` mode, `deepseek` as sub-agent, and a sub-agent model
- **THEN** the installer SHALL write matching delegation settings to `AGENTS.md` and `CLAUDE.md` for the selected project

#### Scenario: Main mode clears every selected target
- **WHEN** a user selects more than one install target and then selects `main` mode
- **THEN** the installer SHALL clear managed delegation state for each selected target and exit without prompting for sub-agent or model choices

### Requirement: Safe multi-target prefill
The system SHALL prefill shared wizard defaults only from unambiguous or compatible existing installs.

#### Scenario: Matching existing target installs seed shared defaults
- **WHEN** both selected targets already contain managed blocks with the same scope, mode, sub-agent, and sub-agent model
- **THEN** the installer SHALL prefill those shared values in the wizard

#### Scenario: Conflicting existing target installs do not guess shared values
- **WHEN** multiple existing target installs contain different scope, mode, sub-agent, or sub-agent model values
- **THEN** the installer SHALL fall back to safe defaults for the shared wizard fields instead of choosing one target's configuration implicitly
