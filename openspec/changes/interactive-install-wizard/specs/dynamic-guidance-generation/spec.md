## ADDED Requirements

### Requirement: Managed block generation
The system SHALL dynamically generate managed guidance blocks from user selections.

#### Scenario: Block includes primary agent
- **WHEN** a managed block is generated with primary agent `claude`
- **THEN** the block SHALL contain `primary: claude` in its metadata section

#### Scenario: Block includes mode
- **WHEN** a managed block is generated with mode `hybrid`
- **THEN** the block SHALL contain `mode: hybrid` in its metadata section

#### Scenario: Block includes sub-agent
- **WHEN** a managed block is generated with sub-agent `deepseek`
- **THEN** the block SHALL contain `sub-agent: deepseek` in its metadata section

#### Scenario: Block includes model assignments
- **WHEN** a managed block is generated with models `{"claude": "claude-sonnet-4-6", "deepseek": "deepseek-v4-pro[1m]"}`
- **THEN** the block SHALL list each agent-model pair in its metadata section

#### Scenario: Block markers are consistent
- **WHEN** a managed block is generated
- **THEN** the block SHALL be wrapped in `<!-- task-relay:start -->` and `<!-- task-relay:end -->` markers

#### Scenario: Block preserves surrounding content
- **WHEN** a managed block is written to an existing guidance file with unrelated content
- **THEN** the existing content outside the markers SHALL remain unchanged

### Requirement: Policy template by mode
The system SHALL include policy instructions in the managed block that match the selected mode.

#### Scenario: Main mode policy
- **WHEN** mode is `main`
- **THEN** the managed block SHALL state that automatic submodel delegation is disabled

#### Scenario: Hybrid mode policy
- **WHEN** mode is `hybrid`
- **THEN** the managed block SHALL describe propose-time routing and delegation-first apply for tagged work

#### Scenario: Delegated-apply mode policy
- **WHEN** mode is `delegated-apply`
- **THEN** the managed block SHALL state that the primary model delegates apply implementation to the sub-agent and verifies completion

### Requirement: Managed block replacement in place
The system SHALL update an existing managed block without duplicating it.

#### Scenario: Reinstall replaces existing block
- **WHEN** a guidance file already contains a `<!-- task-relay:start -->` block
- **THEN** the system SHALL replace the entire block content between the markers and SHALL NOT create a second block

### Requirement: Skill bundle generation
The system SHALL dynamically generate a skill bundle named `task-relay-delegation` for the selected sub-agent.

#### Scenario: Skill bundle created for deepseek sub-agent
- **WHEN** sub-agent is `deepseek` and scope is `project`
- **THEN** the skill bundle SHALL be written to `./.claude/skills/task-relay-delegation/` (or `./.codex/skills/`) with appropriate agent config

#### Scenario: Skill bundle created for claude sub-agent
- **WHEN** sub-agent is `claude`
- **THEN** the skill bundle SHALL include claude-specific agent configuration

#### Scenario: Skill bundle created for codex sub-agent
- **WHEN** sub-agent is `codex`
- **THEN** the skill bundle SHALL include codex-specific agent configuration

#### Scenario: Skill bundle always includes templates
- **WHEN** a skill bundle is generated for any sub-agent
- **THEN** the bundle SHALL include `templates/implementation-draft.md`, `templates/test-draft.md`, `templates/review.md`, and `templates/diagnosis.md`

#### Scenario: SKILL.md is dynamic
- **WHEN** a skill bundle is generated
- **THEN** `SKILL.md` SHALL reflect the selected primary agent, sub-agent, and model assignments

### Requirement: Skill bundle removal on uninstall
The system SHALL remove the `task-relay-delegation` skill directory when uninstalling.

#### Scenario: Uninstall removes skill bundle
- **WHEN** `trly uninstall` is run and a skill bundle exists
- **THEN** the `task-relay-delegation` skill directory SHALL be removed

#### Scenario: Uninstall with no skill bundle
- **WHEN** `trly uninstall` is run but no skill bundle exists
- **THEN** the system SHALL complete without error

### Requirement: Legacy marker migration
The system SHALL detect and migrate managed blocks using the old `task-relay:openspec-delegation` markers.

#### Scenario: Old markers detected
- **WHEN** a guidance file contains `<!-- task-relay:openspec-delegation:start -->`
- **THEN** the system SHALL replace it with the new `<!-- task-relay:start -->` marker format during install
