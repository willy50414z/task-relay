## ADDED Requirements

### Requirement: Install project guidance
The system SHALL install project-local OpenSpec delegation guidance through the new `trly install` command.

#### Scenario: Install hybrid mode
- **WHEN** a user runs `trly install --mode hybrid --cwd <project>`
- **THEN** the system SHALL create or update a managed OpenSpec delegation block in `<project>/AGENTS.md`

#### Scenario: Install main mode
- **WHEN** a user runs `trly install --mode main --cwd <project>`
- **THEN** the managed guidance SHALL state that automatic submodel delegation is disabled

#### Scenario: Install delegated-apply mode
- **WHEN** a user runs `trly install --mode delegated-apply --cwd <project>`
- **THEN** the managed guidance SHALL state that the main model delegates eligible apply implementation and verifies completion

### Requirement: Update managed block in place
The system SHALL update an existing managed guidance block instead of duplicating it.

#### Scenario: Reinstall with different mode
- **WHEN** `AGENTS.md` already contains the task-relay managed block and the user runs `trly install --mode delegated-apply`
- **THEN** the system SHALL replace the existing managed block and SHALL NOT create a second managed block

### Requirement: Uninstall project guidance
The system SHALL remove project-local OpenSpec delegation guidance through `trly uninstall`.

#### Scenario: Remove installed guidance
- **WHEN** `AGENTS.md` contains only the managed guidance block and the user runs `trly uninstall --cwd <project>`
- **THEN** the system SHALL remove the guidance file

#### Scenario: Preserve surrounding guidance
- **WHEN** `AGENTS.md` contains unmanaged text plus the managed guidance block and the user runs `trly uninstall --cwd <project>`
- **THEN** the system SHALL remove only the managed block and preserve unmanaged text

### Requirement: Legacy install compatibility
The system SHALL preserve the legacy install command shape through the compatibility command during the migration window.

#### Scenario: Legacy install_delegant maps to install
- **WHEN** a user runs `agent-dispatch install_delegant --mode hybrid --cwd <project>`
- **THEN** the system SHALL perform the same operation as `trly install --mode hybrid --cwd <project>` and emit a deprecation warning

#### Scenario: Deprecated level flag maps to mode
- **WHEN** a user runs the compatibility command with `--level 1`
- **THEN** the system SHALL map it to `hybrid`
