## ADDED Requirements

### Requirement: Packet generation command
The system SHALL provide a command that generates a delegation packet for a given mode and task
so the delegate does not cold-start re-explore the repository.

#### Scenario: Generate a packet for a mode and task
- **WHEN** a user requests a packet for a given mode (e.g. `implementation-draft`) and a target task
- **THEN** the system SHALL produce a packet pre-filled with the template structure and the selected inlined context

#### Scenario: Generated packet is consumable by the delegation path
- **WHEN** a generated packet is passed to the delegation execution path
- **THEN** the delegate SHALL be able to act on the inlined context without re-reading the source repository to reconstruct it

### Requirement: Deterministic scoped defaults
The system SHALL, by default, inline a small deterministic scope rather than the entire change, so
the packet does not carry unrelated context. Scope selection SHALL be local deterministic code
(no model call).

#### Scenario: Target task block is inlined
- **WHEN** a packet is generated for a specific task
- **THEN** the system SHALL inline that task's block (with its parent heading) and SHALL NOT inline the full `tasks.md` by default

#### Scenario: Implementer-relevant design sections are inlined
- **WHEN** a packet is generated and `design.md` exists
- **THEN** the system SHALL inline its `Decisions`, `Risks / Trade-offs`, and `Open Questions` sections when present, not the whole document by default

#### Scenario: Relevant capability spec is selected
- **WHEN** the task heading or text names a capability that has a delta spec
- **THEN** the system SHALL inline that capability's spec and SHALL NOT inline unrelated capability specs by default

### Requirement: Visible fallback on unresolved scope
The system SHALL make any precision downgrade visible rather than silently widening scope.

#### Scenario: Capability relevance cannot be resolved
- **WHEN** the system cannot map the task to a specific capability spec
- **THEN** it SHALL fall back to inlining all delta specs AND include a visible scope note in the packet stating that the fallback occurred

### Requirement: Full-context escape hatch and dry-run transparency
The system SHALL provide an explicit way to request the full change context and a way to inspect
scope selection without emitting a full packet.

#### Scenario: Full-change context on request
- **WHEN** the user requests full-change context explicitly
- **THEN** the system SHALL inline the whole change (proposal, design, tasks, all specs)

#### Scenario: Dry-run reports selection
- **WHEN** the user requests a dry run
- **THEN** the system SHALL report the selected files/sections, an estimated size, and any fallback reason without emitting the full packet

### Requirement: Unresolvable extra read is reported
The system SHALL report, not silently drop, an explicitly requested extra read that cannot be
located.

#### Scenario: Named extra read is missing
- **WHEN** the user names an extra file to inline and it cannot be resolved
- **THEN** the system SHALL fail loudly rather than emit a packet with silently missing context
