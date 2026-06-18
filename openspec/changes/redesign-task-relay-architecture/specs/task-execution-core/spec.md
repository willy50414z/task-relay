## ADDED Requirements

### Requirement: Raw prompt execution
The system SHALL expose a Python API that sends a prompt to one selected agent or an ordered list of fallback agents and returns the raw stdout as text.

#### Scenario: Single agent succeeds
- **WHEN** a caller invokes `run(target="claude", prompt="hello")` and the resolved Claude agent exits successfully
- **THEN** the system SHALL return the agent stdout as a string

#### Scenario: Fallback agent succeeds
- **WHEN** a caller invokes `run(targets=["claude", "deepseek"], prompt="hello")`, the Claude agent raises `AgentExecutionError`, and the DeepSeek agent succeeds
- **THEN** the system SHALL return the DeepSeek stdout as a string

#### Scenario: Empty prompt rejected
- **WHEN** a caller invokes raw prompt execution with an empty or whitespace-only prompt
- **THEN** the system SHALL reject the request before invoking any agent

### Requirement: Outcome-routed evaluation
The system SHALL expose a Python API that runs an agent in an isolated workspace, resolves exactly one outcome from status files, collects declared output files, and calls the matching callback with a `JobResult`.

#### Scenario: Matching status file routes callback
- **WHEN** an agent creates `status_complete` in the evaluation workspace and `complete` is a declared outcome
- **THEN** the system SHALL call only the `complete` callback with a `JobResult` whose `status` is `complete`

#### Scenario: Declared output files are returned
- **WHEN** the matched outcome declares `questions.txt` and the agent writes that file in the workspace
- **THEN** the system SHALL include the file bytes in `JobResult.files["questions.txt"]`

#### Scenario: Missing declared output file fails loudly
- **WHEN** the matched outcome declares `questions.txt` and the agent does not create that file
- **THEN** the system SHALL raise `OutcomeResolutionError` or call `on_exception` with that error

### Requirement: Workspace lifecycle
The system SHALL create one isolated workspace per outcome-routed evaluation and clean it after agent execution, outcome resolution, and callback handling complete.

#### Scenario: Successful callback cleanup
- **WHEN** evaluation succeeds and the callback returns normally
- **THEN** the system SHALL delete the workspace unless debug retention is enabled

#### Scenario: Callback failure cleanup
- **WHEN** evaluation succeeds but the matching callback raises an exception
- **THEN** the system SHALL still delete the workspace unless debug retention is enabled and SHALL propagate the callback exception

#### Scenario: Agent failure cleanup
- **WHEN** all selected agents fail before outcome resolution
- **THEN** the system SHALL delete the workspace unless debug retention is enabled before propagating or reporting the failure

### Requirement: Typed execution errors
The system SHALL use named error classes for distinct core execution failures.

#### Scenario: Unknown agent
- **WHEN** a caller requests an agent name that cannot be resolved
- **THEN** the system SHALL raise `AgentNotFoundError`

#### Scenario: Agent timeout
- **WHEN** an agent subprocess exceeds the configured timeout
- **THEN** the system SHALL raise `AgentTimeoutError`

#### Scenario: Outcome cannot be resolved
- **WHEN** no status file exists and no `error` outcome is declared
- **THEN** the system SHALL raise `OutcomeResolutionError`
