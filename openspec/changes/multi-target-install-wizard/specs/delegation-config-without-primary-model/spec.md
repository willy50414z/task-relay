## ADDED Requirements

### Requirement: Install flow omits primary model selection
The system SHALL not prompt for, require, or persist a primary model when installing task-relay delegation guidance.

#### Scenario: Interactive install skips primary model prompt
- **WHEN** a user runs `trly install` interactively and selects a delegated mode
- **THEN** the installer SHALL prompt for a sub-agent model without showing a primary model selection step

#### Scenario: Non-interactive install does not require a primary model flag
- **WHEN** a user runs a complete non-interactive install with target selection, scope, mode, and sub-agent inputs
- **THEN** the installer SHALL complete without requiring a `primary` model role in the install command

### Requirement: Persisted configuration excludes primary model metadata
The system SHALL rewrite managed block and generated skill metadata without storing a primary model entry.

#### Scenario: Managed block stores only delegated model metadata
- **WHEN** the installer writes delegation guidance for a delegated mode
- **THEN** the resulting managed block SHALL omit any persisted primary model entry and SHALL keep only the delegated model metadata needed for the selected sub-agent

#### Scenario: Legacy managed block primary model is discarded on rewrite
- **WHEN** an existing managed block contains a primary model entry from an older install
- **THEN** a subsequent install update SHALL remove that persisted primary model entry from the rewritten managed block
