## ADDED Requirements

### Requirement: Agent chain format
The system SHALL represent agent fallback chains as an ordered comma-separated list where each entry is an agent name with an optional model specification using `agent=model` syntax. The first entry SHALL be the primary agent for that chain; subsequent entries SHALL be fallback agents in priority order.

#### Scenario: Chain with explicit models
- **WHEN** a managed block contains `- review-chain: claude=claude-sonnet-4-6, deepseek=deepseek-v4-pro[1m], codex=gpt-5.5-medium`
- **THEN** the system SHALL parse this as a 3-agent chain with claude as primary, deepseek as first fallback, and codex as second fallback, each with the specified model

#### Scenario: Chain with default models
- **WHEN** a managed block contains `- apply-chain: deepseek, codex`
- **THEN** the system SHALL parse this as a 2-agent chain with deepseek using its default model and codex using its default model

#### Scenario: Mixed explicit and default models
- **WHEN** a managed block contains `- review-chain: claude=claude-opus-4-8, deepseek`
- **THEN** the system SHALL use claude-opus-4-8 for claude and the default model for deepseek

### Requirement: Fallback execution contract
When the primary agent in a chain fails with a quota or execution error, the system SHALL try the next agent in the chain. If all agents in the chain fail, the system SHALL raise the last encountered error.

#### Scenario: Primary fails, fallback succeeds
- **WHEN** the review chain primary agent fails with an AgentExecutionError
- **THEN** the system SHALL attempt the second agent in the chain and return its result if successful

#### Scenario: All agents in chain fail
- **WHEN** all agents in a chain fail
- **THEN** the system SHALL raise the last encountered AgentExecutionError

#### Scenario: Fallback preserves agent-specific model
- **WHEN** the system falls back to the second agent in a chain that specifies a model
- **THEN** the system SHALL invoke that agent with its specified model, not the primary agent's model

### Requirement: Independent chains for review and apply
Each feature (review and apply) SHALL have its own independent agent chain. The review chain SHALL be used when the primary agent delegates review work. The apply chain SHALL be used when the primary agent delegates implementation work.

#### Scenario: Review and apply use different primary agents
- **WHEN** review-chain is `claude, deepseek` and apply-chain is `deepseek, codex`
- **THEN** review tasks SHALL first attempt claude and apply tasks SHALL first attempt deepseek

#### Scenario: Review and apply chains may share agents
- **WHEN** review-chain includes `codex` and apply-chain also includes `codex`
- **THEN** both chains SHALL operate independently without conflict

### Requirement: Chain selection respects enabled features
When a feature is not enabled, its chain SHALL NOT be available, and the primary agent SHALL NOT delegate work of that type. If neither feature is enabled, no delegation SHALL occur.

#### Scenario: Only review feature enabled
- **WHEN** the managed block has `features: review` and only a `review-chain`
- **THEN** the primary agent SHALL delegate review work but SHALL NOT delegate apply work

#### Scenario: Only apply feature enabled
- **WHEN** the managed block has `features: apply` and only an `apply-chain`
- **THEN** the primary agent SHALL delegate apply work but SHALL NOT delegate review work
