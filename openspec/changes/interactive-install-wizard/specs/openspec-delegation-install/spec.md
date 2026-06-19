## MODIFIED Requirements

### Requirement: Install project guidance
The system SHALL install delegation guidance through the interactive `trly install` wizard at user or project scope with dynamic primary agent, sub-agent, and model selection.

#### Scenario: Install via wizard
- **WHEN** a user runs `trly install` without flags
- **THEN** the system SHALL launch an interactive wizard and write guidance to the path determined by primary agent and scope selections

#### Scenario: Install via flags
- **WHEN** a user runs `trly install --primary codex --scope project --mode hybrid --sub-agent deepseek`
- **THEN** the system SHALL write guidance to `./AGENTS.md` and skill bundle to `./.codex/skills/`

### Requirement: Update managed block in place
The system SHALL update an existing task-relay managed guidance block instead of duplicating it.

#### Scenario: Reinstall with different configuration
- **WHEN** a guidance file already contains the task-relay managed block and the user runs `trly install` with different selections
- **THEN** the system SHALL replace the existing managed block content and SHALL NOT create a second managed block

### Requirement: Uninstall project guidance
The system SHALL remove delegation guidance from user or project scope through `trly uninstall`.

#### Scenario: Remove installed guidance by auto-detection
- **WHEN** `trly uninstall` is run without `--scope`
- **THEN** the system SHALL check both user and project paths for managed blocks and remove any found

#### Scenario: Remove user-scope guidance
- **WHEN** `trly uninstall --scope user` is run
- **THEN** the system SHALL check `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` and remove any managed blocks found

#### Scenario: Preserve surrounding guidance
- **WHEN** a guidance file contains unmanaged text plus the managed block and `trly uninstall` is run
- **THEN** the system SHALL remove only the managed block and preserve unmanaged text

## REMOVED Requirements

### Requirement: Legacy install compatibility
**Reason**: The migration window from `agent-dispatch` has ended. The `agent-dispatch` compat entry point is being removed.
**Migration**: Use `trly install` (interactive wizard) or `trly install` with explicit flags for scripting.

## ADDED Requirements

### Requirement: Primary agent detection on uninstall
The system SHALL detect the primary agent from an existing managed block to determine correct file paths for cleanup.

#### Scenario: Claude primary agent detected
- **WHEN** uninstalling and the managed block contains `primary: claude`
- **THEN** the system SHALL remove skill bundle from `./.claude/skills/` or `~/.claude/skills/` as appropriate

#### Scenario: Codex primary agent detected
- **WHEN** uninstalling and the managed block contains `primary: codex`
- **THEN** the system SHALL remove skill bundle from `./.codex/skills/` or `~/.codex/skills/` as appropriate
