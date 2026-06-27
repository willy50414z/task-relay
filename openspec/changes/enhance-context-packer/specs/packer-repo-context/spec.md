## ADDED Requirements

### Requirement: Point-to repo files by default, not inline
Because the delegate runs in a worktree containing the full repository, the system SHALL by default
declare relevant repo files for the delegate to read rather than inlining their content into the
packet.

#### Scenario: Repo file is referenced, not inlined, by default
- **WHEN** the packer identifies a relevant repo file for a task
- **THEN** the default packet SHALL reference the file path for the delegate to read rather than embed its content

#### Scenario: Inlining is opt-in and guarded
- **WHEN** the operator opts to inline repo file content
- **THEN** the system SHALL enforce a size/count guard so inlining cannot re-bloat the packet beyond a bound

### Requirement: Dynamic test-mode scope from an explicit diff source
The system SHALL allow a test-mode packet to scope from an explicit dynamic source produced during
an apply session, not only from static OpenSpec artifacts.

#### Scenario: Test packet scopes to changed files from a provided diff source
- **WHEN** a test-mode packet is generated with a caller-provided base ref, diff ref, or diff file
- **THEN** the packer SHALL be able to scope to the files changed in that diff and their tests

#### Scenario: No dynamic diff falls back to static scope
- **WHEN** no dynamic diff source is available for a test-mode packet
- **THEN** the packer SHALL fall back to static artifact scope without error

#### Scenario: Dynamic source is visible in diagnostics
- **WHEN** a dynamic diff source contributes to repo context selection
- **THEN** the diagnostics SHALL identify the source used so the packet can be audited and reproduced
