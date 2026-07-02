## ADDED Requirements

### Requirement: Saved review setting confirmation
The `$trly-review` skill SHALL look for an existing Task Relay review configuration before asking the user to build a new reviewer or arbiter routing.

#### Scenario: Existing setting is shown before review
- **WHEN** `$trly-review` is triggered and a saved review configuration exists
- **THEN** the skill SHALL display the configured reviewers and arbiters before running review

#### Scenario: User accepts saved setting
- **WHEN** the user confirms the displayed saved review setting
- **THEN** the skill SHALL run review with the saved setting without asking for reviewer or arbiter fields again

#### Scenario: User declines saved setting
- **WHEN** the user declines the displayed saved review setting
- **THEN** the skill SHALL start the reviewer and arbiter selection workflow for a one-time or saved replacement setting

### Requirement: Review setting table display
The `$trly-review` skill SHALL present review routing as a table with Role, Agent, Model, Effort, and Personas columns.

#### Scenario: Codex model effort is displayed
- **WHEN** a role entry uses a Codex model id with an effort suffix such as `gpt-5.5-high`
- **THEN** the table SHALL show `gpt-5.5` as Model and `high` as Effort

#### Scenario: Non-Codex effort is not applicable
- **WHEN** a role entry uses a non-Codex agent
- **THEN** the table SHALL show the configured model or `default` as Model and `n/a` as Effort

#### Scenario: Persona is shown without slash noise
- **WHEN** a role entry uses a slash persona such as `/plan-eng-review`
- **THEN** the table SHALL show the persona in a user-readable form such as `plan-eng-review` or its recognized alias

### Requirement: Reviewer selection workflow
The `$trly-review` skill SHALL collect reviewer routing in the order reviewer-agent, reviewer-model, reviewer-effort for Codex only, reviewer-personas, and add-next-reviewer confirmation.

#### Scenario: Codex reviewer asks for effort
- **WHEN** the selected reviewer agent is `codex`
- **THEN** the workflow SHALL ask for Codex effort before constructing the reviewer model id

#### Scenario: Non-Codex reviewer skips effort
- **WHEN** the selected reviewer agent is not `codex`
- **THEN** the workflow SHALL skip reviewer-effort and use the selected model id directly

#### Scenario: Multiple reviewers
- **WHEN** the user chooses to add another reviewer
- **THEN** the workflow SHALL repeat the reviewer selection sequence and preserve reviewer order for display and CLI flags

### Requirement: Arbiter selection workflow
The `$trly-review` skill SHALL collect arbiter routing in the order arbiter-agent, arbiter-model, arbiter-effort for Codex only, arbiter-personas, and add-next-arbiter confirmation.

#### Scenario: At least one arbiter is required
- **WHEN** the user attempts to run review without an arbiter
- **THEN** the skill SHALL stop before execution and explain that review gate requires an arbiter decision source

#### Scenario: Multiple arbiters preserve order
- **WHEN** the user chooses to add another arbiter
- **THEN** the workflow SHALL repeat the arbiter selection sequence and preserve arbiter order for serial execution

### Requirement: Persona alias normalization
The `$trly-review` skill SHALL normalize recognized persona aliases to the stored slash persona format used by review role entries.

#### Scenario: CEO alias
- **WHEN** the user selects persona `ceo`
- **THEN** the stored persona SHALL be `/plan-ceo-review`

#### Scenario: Engineer alias
- **WHEN** the user selects persona `engineer`
- **THEN** the stored persona SHALL be `/plan-eng-review`

#### Scenario: Review alias
- **WHEN** the user selects persona `review`
- **THEN** the stored persona SHALL be `/review`

#### Scenario: Security alias
- **WHEN** the user selects persona `cso`
- **THEN** the stored persona SHALL be `/cso`

### Requirement: Review execution handoff
The `$trly-review` skill SHALL run review through the stable `trly review` entry point after review routing is confirmed.

#### Scenario: Saved setting execution
- **WHEN** the user accepts an existing saved setting
- **THEN** the skill SHALL invoke `trly review --change <change>` or an equivalent API using the saved configuration

#### Scenario: One-time override execution
- **WHEN** the user builds a one-time reviewer and arbiter setting
- **THEN** the skill SHALL invoke `trly review --change <change>` with explicit `--reviewers` and `--arbiter` flags

#### Scenario: User chooses to save new setting
- **WHEN** the user builds a new setting and chooses to save it
- **THEN** the skill SHALL include the save option supported by `trly review` and preserve the selected reviewer and arbiter entries

### Requirement: Arbiter revision contract application
The `$trly-review` skill SHALL handle final review decisions according to the arbiter result and SHALL only modify OpenSpec artifacts when the final decision is `REVISE`.

#### Scenario: Approve does not edit artifacts
- **WHEN** review returns final decision `APPROVE`
- **THEN** the skill SHALL report the reviewer and arbiter summaries without editing OpenSpec artifacts

#### Scenario: Reject stops before apply
- **WHEN** review returns final decision `REJECT`
- **THEN** the skill SHALL report the arbiter reasons and stop before apply without editing OpenSpec artifacts

#### Scenario: Revise applies only arbiter actionable items
- **WHEN** review returns final decision `REVISE`
- **THEN** the primary agent SHALL update only the OpenSpec artifacts named by arbiter-adjudicated `actionable_items`

#### Scenario: Revise ignores unadjudicated reviewer suggestions
- **WHEN** a reviewer finding is not included in an arbiter `actionable_items` contract
- **THEN** the primary agent SHALL NOT apply that reviewer finding as part of `$trly-review`

#### Scenario: Revise requires readiness verification
- **WHEN** the primary agent finishes applying arbiter `actionable_items`
- **THEN** the skill SHALL run revision readiness verification and treat review as complete only when verification reports apply-ready
