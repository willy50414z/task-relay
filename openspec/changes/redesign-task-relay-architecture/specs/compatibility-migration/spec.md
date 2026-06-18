## ADDED Requirements

### Requirement: Import compatibility shim
The system SHALL provide a temporary `llm_eval` package shim that re-exports the supported public API from `task_relay`.

#### Scenario: Legacy import works
- **WHEN** existing code imports `evaluate`, `run`, `Outcome`, or `JobResult` from `llm_eval`
- **THEN** the import SHALL succeed and resolve to the task-relay implementation

#### Scenario: Legacy import warns
- **WHEN** code imports from the compatibility `llm_eval` package
- **THEN** the system SHALL emit a `DeprecationWarning` that identifies `task_relay` as the replacement

### Requirement: Legacy console entry point
The system SHALL provide a temporary `agent-dispatch` console entry point that routes to the same CLI implementation as `trly`.

#### Scenario: Legacy command runs
- **WHEN** a user invokes `agent-dispatch run --target claude --prompt "hello"`
- **THEN** the command SHALL execute through the same implementation as `trly run`

#### Scenario: Legacy command warns
- **WHEN** a user invokes `agent-dispatch`
- **THEN** the command SHALL write a deprecation warning to stderr naming `trly` as the replacement

### Requirement: Package migration metadata
The system SHALL publish package metadata under the new `task-relay` identity while keeping migration information visible.

#### Scenario: New package metadata
- **WHEN** the project is built
- **THEN** the distribution metadata SHALL use name `task-relay` and version `0.2.0`

#### Scenario: README migration guidance
- **WHEN** a user reads the project README
- **THEN** the README SHALL show the new install command, new imports, new CLI command, and legacy migration notes

### Requirement: Compatibility removal is documented
The system SHALL document the planned removal version for legacy imports and command aliases.

#### Scenario: Deprecation schedule present
- **WHEN** a user reads compatibility documentation or warnings
- **THEN** the system SHALL state that the shim is temporary and identify the planned removal version
