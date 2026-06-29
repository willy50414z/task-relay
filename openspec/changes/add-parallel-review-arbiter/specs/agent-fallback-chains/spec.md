## ADDED Requirements

### Requirement: Reviewers are not fallback chains
The system SHALL treat `reviewers` as a parallel fan-out list, not as an ordered fallback chain. Ordered fallback semantics SHALL remain available only where explicitly configured as fallback targets or apply chains.

#### Scenario: Reviewer list has multiple entries
- **WHEN** the managed guidance contains `reviewers: claude:/review, deepseek:/cso`
- **THEN** both reviewers SHALL be invoked for the same gate rather than invoking DeepSeek only if Claude fails

#### Scenario: Apply chain remains fallback
- **WHEN** the apply configuration contains `apply-chain: deepseek, codex`
- **THEN** apply delegation SHALL continue to try DeepSeek first and Codex only as fallback on execution failure

### Requirement: Legacy review-chain migration
The system SHALL support reading legacy `review-chain` configuration during the migration window, but generated guidance MUST prefer `reviewers` and MUST NOT describe proposal review as a sequential chain.

#### Scenario: Legacy review-chain exists
- **WHEN** existing managed guidance contains `review-chain: claude, deepseek` and no `reviewers` entry
- **THEN** the system SHALL interpret only `claude` as the migrated reviewer, preserve `deepseek` only as legacy metadata if needed, and emit or display deprecation guidance

#### Scenario: New reviewers override legacy chain
- **WHEN** both `reviewers` and `review-chain` are present
- **THEN** the system SHALL use `reviewers` for proposal review gate orchestration
