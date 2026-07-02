## MODIFIED Requirements

### Requirement: Saved review setting confirmation
The `$trly-review` skill SHALL look for an existing Task Relay review configuration before asking the user to build a new reviewer or arbiter routing. When a saved configuration exists and the trigger prompt does not explicitly request reconfiguration or routing override, the skill SHALL display the saved configuration and use it without asking for confirmation.

#### Scenario: Existing setting is announced before review
- **WHEN** `$trly-review` is triggered
- **AND** a saved review configuration exists
- **AND** the trigger prompt does not request reconfiguration or routing override
- **THEN** the skill SHALL display the configured reviewers and arbiters before running review
- **AND** the skill SHALL state that it will review according to the displayed review config

#### Scenario: Saved setting runs without confirmation
- **WHEN** `$trly-review` is triggered
- **AND** a saved review configuration exists
- **AND** the trigger prompt does not request reconfiguration or routing override
- **THEN** the skill SHALL invoke `trly review --change <change>` or an equivalent API using the saved configuration
- **AND** the skill SHALL NOT ask whether the user wants to apply the saved setting

#### Scenario: Explicit reconfiguration request starts selection workflow
- **WHEN** `$trly-review` is triggered with a prompt that includes reconfiguration intent such as `重新設定`, `重設`, `改 review config`, `設定 review config`, `換 reviewer`, `換 arbiter`, `reconfigure`, `reset review config`, `change review config`, or `不要用目前 config`
- **THEN** the skill SHALL start the reviewer and arbiter selection workflow instead of auto-running the saved configuration

#### Scenario: Explicit routing override starts selection workflow
- **WHEN** `$trly-review` is triggered with explicit routing or persistence intent such as `--reviewers`, `--arbiter`, `--save`, or `--no-save`
- **THEN** the skill SHALL treat the request as a one-time or saved routing setup
- **AND** the skill SHALL start the reviewer and arbiter selection workflow instead of auto-running the saved configuration

#### Scenario: No saved setting starts selection workflow
- **WHEN** `$trly-review` is triggered
- **AND** no saved review configuration exists
- **THEN** the skill SHALL start the reviewer and arbiter selection workflow

## ADDED Requirements

### Requirement: Review config storage source of truth
The `$trly-review` skill SHALL use Task Relay managed guidance as the durable source of truth for saved review configuration and SHALL NOT introduce `.task_relay` as a durable review config storage location.

#### Scenario: Saved config lookup uses managed guidance
- **WHEN** `$trly-review` looks for an existing saved review configuration
- **THEN** the skill SHALL use the managed guidance configuration written by existing install or review-save flows

#### Scenario: Runtime state is not durable config
- **WHEN** the skill describes saved review configuration behavior
- **THEN** it SHALL NOT instruct agents to read or write `.task_relay` as the durable source of truth for review config
