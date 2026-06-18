## ADDED Requirements

### Requirement: Canonical CLI command
The system SHALL expose `trly` as the canonical command-line entry point for task-relay workflows.

#### Scenario: Run help
- **WHEN** a user runs `trly run --help`
- **THEN** the CLI SHALL display prompt input, target selection, model, effort, timeout, and cwd options

#### Scenario: Evaluate help
- **WHEN** a user runs `trly evaluate --help`
- **THEN** the CLI SHALL display purpose input, outcome declaration, output-file declaration, target selection, and JSON output options

### Requirement: Raw prompt CLI execution
The CLI SHALL support raw prompt execution from inline text, a file, or stdin.

#### Scenario: Inline prompt
- **WHEN** a user runs `trly run --target claude --prompt "hello"`
- **THEN** the CLI SHALL call the Python run API and write only model stdout to stdout on success

#### Scenario: Prompt file
- **WHEN** a user runs `trly run --target codex --prompt-file prompt.md`
- **THEN** the CLI SHALL read `prompt.md` as UTF-8 and pass its contents to the Python run API

#### Scenario: Stdin prompt
- **WHEN** a user runs `trly run --target deepseek --stdin` and sends text on stdin
- **THEN** the CLI SHALL pass stdin content to the Python run API

### Requirement: Outcome-routed CLI evaluation
The CLI SHALL support outcome-routed evaluation and JSON serialization.

#### Scenario: Successful JSON result
- **WHEN** a user runs `trly evaluate` with valid purpose, outcomes, and `--json`
- **THEN** the CLI SHALL write one JSON object containing status, target, duration, stdout, and decoded declared files

#### Scenario: Unknown output-file status
- **WHEN** a user declares `--output-file failed=errors.txt` without declaring outcome `failed`
- **THEN** the CLI SHALL exit with an argument/runtime error and SHALL NOT invoke an agent

### Requirement: Health CLI
The CLI SHALL expose agent health checks as JSON.

#### Scenario: Check all agents
- **WHEN** a user runs `trly health --json`
- **THEN** the CLI SHALL return a JSON object keyed by agent name with `ok` and `reason`

#### Scenario: Check one agent
- **WHEN** a user runs `trly health --target codex --json`
- **THEN** the CLI SHALL return only Codex health status

### Requirement: CLI exit codes
The CLI SHALL preserve the established exit code contract.

#### Scenario: Success
- **WHEN** a CLI command succeeds
- **THEN** the process SHALL exit with code `0`

#### Scenario: Runtime failure
- **WHEN** agent execution or runtime logic fails
- **THEN** the process SHALL exit with code `1` and write diagnostics to stderr

#### Scenario: Argument failure
- **WHEN** argument parsing or validation fails
- **THEN** the process SHALL exit with code `2` and write diagnostics to stderr
