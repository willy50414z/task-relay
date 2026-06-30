## ADDED Requirements

### Requirement: Install provides accurate non-interactive guidance
The install workflow SHALL direct users toward the currently supported non-interactive flags when interactive prompts are unavailable.

#### Scenario: Non-TTY install fails with current flag guidance
- **WHEN** the user triggers interactive install in a non-TTY context
- **THEN** the resulting guidance SHALL reference the current non-interactive flags rather than deprecated ones

### Requirement: Install reports next-step success guidance
The install workflow SHALL print clear next-step guidance after writing configuration so the user can validate and use the installed setup immediately.

#### Scenario: Install completes successfully
- **WHEN** install writes the managed block and skill bundle successfully
- **THEN** it SHALL print a concise summary of what was configured and the next commands to validate or use the setup

### Requirement: Install can surface post-write validation results
The install workflow SHALL be able to surface post-write validation or smoke-check results that help the user catch configuration problems early.

#### Scenario: Install surfaces a failing smoke check
- **WHEN** install completes but a post-write smoke check or preflight validation fails
- **THEN** install SHALL report the failure and recommend the next remediation step instead of silently ending as if setup were healthy

#### Scenario: Install surfaces a passing validation path
- **WHEN** install completes and the configured targets pass the enabled post-write checks
- **THEN** install SHALL report that validation succeeded and point the user to the next operational command
