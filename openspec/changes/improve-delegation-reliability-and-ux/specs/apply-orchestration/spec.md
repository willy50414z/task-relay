## ADDED Requirements

### Requirement: CLI provides a high-level apply command
The system SHALL provide a high-level apply command that wraps packet generation, isolated delegation, and result summarization for implementation work.

#### Scenario: Apply runs an implementation task end-to-end
- **WHEN** the user runs the high-level apply command for an implementation task
- **THEN** the CLI SHALL generate the implementation packet, execute the delegate through isolated worktree delegation, and print the resulting branch and summary

#### Scenario: Apply can target test drafting
- **WHEN** the user requests test-oriented delegation through the high-level apply command
- **THEN** the CLI SHALL generate a `test-draft` packet instead of an `implementation-draft` packet

### Requirement: Apply fails loudly on empty delegated output
The high-level apply workflow SHALL treat an empty delegated branch as a failure rather than a successful run.

#### Scenario: Delegate produces no changes
- **WHEN** isolated delegation exits successfully but produces no committed changes
- **THEN** the high-level apply command SHALL fail loudly and report that no branch output was produced

### Requirement: Apply summarizes branch output for primary review
The high-level apply workflow SHALL produce a branch-oriented summary suitable for the primary agent or human operator to review before integration.

#### Scenario: Apply reports branch and diff summary
- **WHEN** isolated delegation produces a throwaway branch with changes
- **THEN** the high-level apply command SHALL report the branch name and a summary of changed files or diff statistics

#### Scenario: Apply runs optional verification
- **WHEN** the user provides a verification command to the high-level apply workflow
- **THEN** the workflow SHALL execute the verification step after delegation and include its outcome in the summary
