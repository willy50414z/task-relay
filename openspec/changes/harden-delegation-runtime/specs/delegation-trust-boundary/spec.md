## ADDED Requirements

### Requirement: Enforced delegation trust boundary
The system SHALL enforce the delegation trust boundary through execution constraints, not only
through prompt instructions, so that a delegated agent cannot clobber the user's real working
tree or push to the user's real remotes.

#### Scenario: Delegate writes do not touch the real working tree
- **WHEN** a delegated agent edits files during a delegation
- **THEN** those edits SHALL land in an isolated working area rather than the user's real working tree

#### Scenario: Delegate cannot push to real remotes
- **WHEN** a delegated agent attempts `git push` during a delegation
- **THEN** the execution environment SHALL reject it rather than relying on the agent honoring a prompt non-goal

### Requirement: Uniform ephemeral worktree mechanism
The system SHALL isolate delegated agents using a single ephemeral git worktree mechanism that
is identical across all supported agent CLIs, rather than per-CLI sandbox profiles.

#### Scenario: Delegate runs in an ephemeral worktree
- **WHEN** any supported agent (claude, deepseek, or codex) is invoked as a delegate
- **THEN** the system SHALL run it with its working directory set to an ephemeral worktree on a throwaway branch

#### Scenario: Worktree is cleaned up
- **WHEN** a delegation that used an ephemeral worktree completes
- **THEN** the system SHALL remove the worktree and its throwaway branch unless debug retention is enabled

#### Scenario: Worktree, not flag removal, is the isolation strategy
- **WHEN** a delegate is invoked under isolation
- **THEN** the system SHALL rely on the ephemeral worktree + push neutralization as the boundary; the CLI's own headless-execution flags may remain (removing them would break headless writes), and full read/network confinement via an OS sandbox is deferred as follow-up

### Requirement: Process-local push neutralization
The system SHALL neutralize `git push` for the delegate without mutating the repository's shared
git configuration.

#### Scenario: Push override is process-scoped
- **WHEN** the system disables push for a delegate
- **THEN** it SHALL apply the override via the delegate subprocess environment and SHALL leave the repository's real git configuration unchanged after the delegation

### Requirement: Pre-delegation working-tree guard
Because the ephemeral worktree is a clean `HEAD` checkout, the system SHALL detect a dirty main
working tree at the start of an isolated delegation and stop with guidance rather than silently
delegating from a stale base, unless the caller explicitly opts out.

#### Scenario: Dirty tree stops the delegation
- **WHEN** an isolated delegation starts and the main working tree has uncommitted or untracked changes and no override is given
- **THEN** the system SHALL stop with a named error advising the user to commit and re-run, and SHALL NOT create a worktree or branch

#### Scenario: Override delegates from HEAD anyway
- **WHEN** an isolated delegation starts on a dirty main tree and the caller passes the allow-dirty override
- **THEN** the system SHALL proceed, delegating from the clean `HEAD` state

#### Scenario: Clean tree proceeds
- **WHEN** an isolated delegation starts and the main working tree is clean
- **THEN** the system SHALL proceed without the guard interrupting

### Requirement: Empty delegation output is loud
The system SHALL surface a failure when a delegation produces no changes in its worktree where
changes were expected, rather than silently reporting success.

#### Scenario: Delegate produced nothing
- **WHEN** an apply delegation completes with no changes in the ephemeral worktree
- **THEN** the system SHALL surface a named failure for the primary to act on

### Requirement: Change-level integration worktree for multi-task apply
The system SHALL support a change-level integration worktree that serves as the sandbox for a
multi-task apply session, so intermediate commits and merges do not touch the real working branch
until a single final integration.

#### Scenario: Integration worktree opened at apply start
- **WHEN** a multi-task apply session begins
- **THEN** the system SHALL be able to open a change-level integration worktree branched from the current branch's HEAD

#### Scenario: Task delegation branches from the change branch tip
- **WHEN** a task delegation runs within an apply session that has a change integration branch
- **THEN** the task worktree SHALL be branchable from the change branch tip (not only from HEAD), so a dependent task sees prior accepted work

#### Scenario: Accepted task merges back into the change branch
- **WHEN** the primary accepts a task delegation's branch
- **THEN** the system SHALL support merging it back into the change branch so subsequent tasks build on it

#### Scenario: Final integration is a single merge to the real branch
- **WHEN** all tasks in the apply session are accepted
- **THEN** the system SHALL integrate the change branch into the real working branch as a single step

#### Scenario: Single delegation may skip the integration worktree
- **WHEN** an apply consists of a single trivial delegation
- **THEN** the system SHALL allow skipping the change-level integration worktree

#### Scenario: Cleanup removes change and task worktrees
- **WHEN** an apply session ends (accepted or abandoned)
- **THEN** the system SHALL remove the change and task worktrees and their throwaway branches unless debug retention is enabled

### Requirement: Parallel tests run from the accumulated change branch
The system SHALL allow test delegations to run in parallel from the accumulated change branch so
they see all committed development for the change.

#### Scenario: Parallel test delegates branch from the change branch
- **WHEN** development for a change is committed onto the change branch and multiple test delegations are launched
- **THEN** each test delegation SHALL branch from the change branch (seeing all committed development) and run independently in its own worktree
