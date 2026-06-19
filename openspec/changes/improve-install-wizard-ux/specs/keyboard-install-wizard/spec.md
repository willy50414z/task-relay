## ADDED Requirements

### Requirement: Keyboard-driven selection prompts
The system SHALL present `trly install` interactive choices as keyboard-driven selection prompts when stdin is a TTY and required non-interactive flags are not fully provided.

#### Scenario: User navigates choices with keyboard
- **WHEN** a user runs `trly install` in an interactive terminal
- **THEN** the installer SHALL let the user move through primary agent, scope, mode, sub-agent, and model choices with up/down navigation and confirm each choice with Enter

#### Scenario: Main mode exits after clearing
- **WHEN** a user selects `main` mode in the interactive wizard
- **THEN** the installer SHALL clear the managed block for the selected primary agent and scope and exit without prompting for sub-agent or models

### Requirement: Prompt adapter abstraction
The system SHALL isolate terminal prompting behind an adapter so wizard state transitions can be tested without a real TTY.

#### Scenario: Unit tests supply fake choices
- **WHEN** tests run wizard steps with a fake prompt adapter
- **THEN** the wizard SHALL return the same `WizardState` values that the production prompt would produce for those choices

#### Scenario: Prompt dependency is unavailable in non-interactive mode
- **WHEN** a user runs a complete non-interactive install with all required flags
- **THEN** the installer SHALL complete without importing or invoking the interactive prompt adapter

### Requirement: Non-interactive fallback
The system SHALL preserve a non-interactive install path for scripts and CI.

#### Scenario: Complete flag set skips prompts
- **WHEN** a user runs `trly install --primary codex --scope project --mode hybrid --sub-agent deepseek --model primary=gpt-5.5-medium --model sub=deepseek-v4-pro[1m]`
- **THEN** the installer SHALL skip all prompts and write the selected configuration directly

#### Scenario: Missing flags without TTY fails clearly
- **WHEN** stdin is not a TTY and a user runs `trly install` without enough flags to complete installation
- **THEN** the command SHALL fail with a message listing the required non-interactive flags

### Requirement: Existing configuration prefill
The system SHALL prefill interactive defaults from an existing task-relay managed block when the target can be determined unambiguously.

#### Scenario: Project block seeds defaults
- **WHEN** `./AGENTS.md` contains a task-relay managed block for `primary: codex` and `scope: project`
- **THEN** `trly install` SHALL default the wizard to codex, project scope, the recorded mode, the recorded sub-agent, and the recorded models

#### Scenario: Agent-keyed models normalize to role-keyed state
- **WHEN** an existing block contains model entries keyed by agent name
- **THEN** the wizard SHALL map the primary agent model to `models["primary"]` and the sub-agent model to `models["sub"]`

#### Scenario: Ambiguous existing blocks do not guess
- **WHEN** more than one candidate guidance file contains a task-relay managed block and the user did not provide primary or scope flags
- **THEN** the wizard SHALL use safe defaults and update only the primary and scope selected by the user
