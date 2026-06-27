## ADDED Requirements

### Requirement: Packer-consumable explicit signals
The system SHALL allow OpenSpec changes to declare explicit signals that the packer consumes before
falling back to heuristic token overlap.

#### Scenario: Signals are loaded from a change-local sidecar
- **WHEN** a change contains the packer signals sidecar
- **THEN** the packer SHALL load task-to-capability mappings, task dependencies, declared design sections, and declared repo-file references from that sidecar
- **AND** the packer SHALL NOT require these signals to be embedded inline in `tasks.md`

#### Scenario: Explicit task-to-capability mapping is used first
- **WHEN** a task declares the capability it belongs to and that capability has a delta spec
- **THEN** the packer SHALL select that spec from the declaration rather than guessing by token overlap

#### Scenario: Declared task dependencies inform scope
- **WHEN** a task declares prerequisite tasks
- **THEN** the packer SHALL be able to include the declared dependency context

### Requirement: Declare only what cannot be derived
The system SHALL prefer deterministic derivation and require explicit signals only for what
derivation cannot reliably produce.

#### Scenario: Derivable signal is not required to be declared
- **WHEN** a signal can be derived deterministically from existing artifacts
- **THEN** the system SHALL NOT require an author to declare it redundantly

### Requirement: Packetability lint validates signals
The system SHALL provide a `pack-lint` check that validates explicit signals and reports problems
without modifying the artifacts.

#### Scenario: Stale or invalid signal is reported
- **WHEN** a declared capability, dependency task, design section, or file does not resolve to something real
- **THEN** `pack-lint` SHALL report it as actionable diagnostic output

#### Scenario: Lint is advisory by default
- **WHEN** `pack-lint` finds problems during normal use
- **THEN** it SHALL report them and SHALL NOT auto-edit the proposal, design, tasks, or sidecar
- **AND** it SHALL NOT block delegation unless a caller explicitly opts into a gating mode

#### Scenario: Lint flags tasks that will fall back
- **WHEN** a task cannot be uniquely mapped to a spec or a sensible task block cannot be extracted
- **THEN** `pack-lint` SHALL flag that the task will fall back to the conservative scope
