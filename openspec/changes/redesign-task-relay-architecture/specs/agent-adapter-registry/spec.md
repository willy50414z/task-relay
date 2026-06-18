## ADDED Requirements

### Requirement: Built-in agent resolution
The system SHALL resolve built-in agent names through a registry without requiring core execution code to branch on a target enum.

#### Scenario: Resolve Claude
- **WHEN** a caller requests agent name `claude`
- **THEN** the registry SHALL return a Claude runner adapter

#### Scenario: Resolve Codex
- **WHEN** a caller requests agent name `codex`
- **THEN** the registry SHALL return a Codex runner adapter

#### Scenario: Resolve DeepSeek
- **WHEN** a caller requests agent name `deepseek`
- **THEN** the registry SHALL return a DeepSeek runner adapter

### Requirement: Adapter-owned subprocess behavior
Each agent adapter SHALL own command construction, environment construction, health checking, and subprocess failure classification for that agent.

#### Scenario: Codex effort flag
- **WHEN** Codex is executed with effort `xhigh`
- **THEN** the Codex adapter SHALL pass the correct Codex CLI reasoning effort configuration to the subprocess command

#### Scenario: DeepSeek environment
- **WHEN** DeepSeek is executed with an available `DEEPSEEK_AUTH_TOKEN`
- **THEN** the DeepSeek adapter SHALL configure the Anthropic-compatible base URL, auth token, model, subagent model, and effort environment variables before invoking the Claude CLI

#### Scenario: Claude model flag
- **WHEN** Claude is executed with a model override
- **THEN** the Claude adapter SHALL pass the model override to the Claude CLI command

### Requirement: Configured defaults
The system SHALL merge built-in defaults, config-file defaults, and explicit runtime arguments in deterministic precedence order.

#### Scenario: CLI override wins
- **WHEN** config sets Claude default model to `claude-sonnet` and the caller passes model `claude-opus`
- **THEN** the adapter SHALL execute with model `claude-opus`

#### Scenario: Config default applies
- **WHEN** config sets Codex effort to `high` and the caller does not pass effort
- **THEN** the Codex adapter SHALL execute with effort `high`

#### Scenario: Missing config is valid
- **WHEN** `~/.task-relay/config.yml` does not exist
- **THEN** the registry SHALL use built-in defaults without error

### Requirement: Unsupported future adapter types are explicit
The system SHALL reject configured adapter types that are reserved but not implemented in v0.2.

#### Scenario: OpenCLI type rejected
- **WHEN** config declares an agent with `type: opencli`
- **THEN** resolving that agent SHALL fail with a clear configuration error that web relay is not supported in this version
