## ADDED Requirements

### Requirement: Canonical install path resolution
The system SHALL resolve guidance files and skill roots from the selected primary agent, scope, and working directory using a single canonical path resolver.

#### Scenario: Codex project path
- **WHEN** primary agent is `codex`, scope is `project`, and cwd is `<project>`
- **THEN** the guidance file SHALL be `<project>/AGENTS.md` and the skill root SHALL be `<project>/.codex/skills`

#### Scenario: Codex user path
- **WHEN** primary agent is `codex` and scope is `user`
- **THEN** the guidance file SHALL be `~/.codex/AGENTS.md` and the skill root SHALL be `~/.codex/skills`

#### Scenario: Claude project path
- **WHEN** primary agent is `claude`, scope is `project`, and cwd is `<project>`
- **THEN** the guidance file SHALL be `<project>/CLAUDE.md` and the skill root SHALL be `<project>/.claude/skills`

#### Scenario: Claude user path
- **WHEN** primary agent is `claude` and scope is `user`
- **THEN** the guidance file SHALL be `~/.claude/CLAUDE.md` and the skill root SHALL be `~/.claude/skills`

### Requirement: Clear and uninstall use canonical paths
The system SHALL use the canonical path resolver for install, main-mode clear, and uninstall cleanup.

#### Scenario: Main mode clears selected target only
- **WHEN** a user selects `main` mode for primary agent `codex` and scope `project`
- **THEN** the installer SHALL clear only the task-relay managed block and skill bundle resolved for codex project scope

#### Scenario: User-scope uninstall removes user skill bundle
- **WHEN** `trly uninstall --scope user` removes a codex user managed block
- **THEN** it SHALL remove `~/.codex/skills/task-relay-delegation` and SHALL NOT derive a duplicated path such as `~/.codex/.codex/skills`

#### Scenario: Project-scope uninstall preserves user scope
- **WHEN** `trly uninstall --scope project` is run from a project that has project and user managed blocks
- **THEN** it SHALL remove only project-scope managed blocks and project-scope skill bundles

### Requirement: Complete task-relay skill assets
The system SHALL install the `task-relay-delegation` skill bundle from packaged `task-relay-delegation` assets.

#### Scenario: Full templates are copied
- **WHEN** `trly install` creates a `task-relay-delegation` skill bundle
- **THEN** the bundle SHALL include non-empty implementation-draft, test-draft, review, and diagnosis templates copied from package assets

#### Scenario: Sub-agent config is written
- **WHEN** the selected sub-agent is `deepseek`
- **THEN** the bundle SHALL include a sub-agent config file for DeepSeek under the skill bundle's `agents` directory

### Requirement: Legacy skill cleanup
The system SHALL remove stale legacy `openspec-deepseek-delegation` skill bundles from the resolved skill root when installing or uninstalling task-relay delegation.

#### Scenario: Install removes legacy project skill
- **WHEN** a project contains `.codex/skills/openspec-deepseek-delegation` and the user installs codex project delegation
- **THEN** the installer SHALL remove the legacy skill directory after writing `.codex/skills/task-relay-delegation`

#### Scenario: Uninstall removes new and legacy skill directories
- **WHEN** `trly uninstall` removes a task-relay managed block for a resolved primary/scope
- **THEN** it SHALL remove both `task-relay-delegation` and `openspec-deepseek-delegation` directories from the resolved skill root if they exist

#### Scenario: Unmanaged guidance text is preserved
- **WHEN** a guidance file contains unmanaged text before or after the task-relay managed block
- **THEN** install, clear, and uninstall SHALL preserve the unmanaged text while replacing or removing only the managed block
