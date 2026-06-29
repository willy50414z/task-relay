## ADDED Requirements

### Requirement: Install reviewers configuration
The install command SHALL support configuring proposal reviewers with `--reviewers`. The value MUST be a comma-separated list of reviewer entries.

#### Scenario: Install parallel reviewers
- **WHEN** a user runs `trly install --reviewers claude:/review,deepseek:/cso,codex:/qa-only`
- **THEN** the managed guidance SHALL include a `reviewers` entry preserving those reviewer entries

#### Scenario: Reviewer uses default persona
- **WHEN** a reviewer entry omits a persona
- **THEN** the system SHALL accept the entry and apply a documented default reviewer persona during review gate execution

### Requirement: Install arbiter configuration
The install command SHALL support configuring serial arbiters with `--arbiter`. The flag MAY be repeated or receive comma-separated entries, and generated guidance MUST preserve arbiter order. Review gate execution MUST require at least one configured arbiter.

#### Scenario: Install two arbiters with repeated flags
- **WHEN** a user runs `trly install --arbiter claude:/plan-ceo-review --arbiter claude:/plan-eng-review`
- **THEN** the managed guidance SHALL contain an arbiter chain in CEO then engineering order

#### Scenario: Install arbiters with comma-separated value
- **WHEN** a user runs `trly install --arbiter claude:/plan-ceo-review,deepseek:/plan-eng-review`
- **THEN** the managed guidance SHALL contain both arbiter entries in the specified order

#### Scenario: Arbiter shares reviewer agent
- **WHEN** the same agent appears in both `--reviewers` and `--arbiter`
- **THEN** the install command SHALL accept the configuration because persona and artifact isolation define the role boundary

#### Scenario: No arbiter configured
- **WHEN** review delegation is enabled and neither install defaults nor user-provided flags produce an arbiter entry
- **THEN** the install command or review gate configuration validation SHALL fail with a clear diagnostic

### Requirement: Install global timeout configuration
The install command SHALL support configuring the review gate timeout with `--global-timeout`. The value MUST be stored in managed guidance or runtime configuration used by the review gate.

#### Scenario: Install review gate timeout
- **WHEN** a user runs `trly install --reviewers claude:/review --arbiter claude:/plan-ceo-review --global-timeout 900`
- **THEN** the managed guidance or review gate configuration SHALL preserve `900` seconds as the global review gate timeout

### Requirement: Deprecated review-chain flag
The install command SHALL mark `--review-chain` as deprecated for proposal review. During the migration window, it MUST either map to `--reviewers` when no reviewers are provided or emit an argument conflict when both are provided ambiguously.

#### Scenario: Legacy review-chain maps to reviewers
- **WHEN** a user runs `trly install --review-chain claude,deepseek` without `--reviewers`
- **THEN** the command SHALL emit a deprecation warning and install only the original primary reviewer as `reviewers` guidance unless the user explicitly provides additional reviewers

#### Scenario: Reviewers and review-chain conflict
- **WHEN** a user runs `trly install --reviewers claude:/review --review-chain deepseek`
- **THEN** the command SHALL prefer `--reviewers` or fail with a clear argument diagnostic rather than silently merging two incompatible meanings
