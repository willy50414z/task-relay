## ADDED Requirements

### Requirement: Review delegation output verification
The system SHALL verify that a review delegation's declared output artifact exists and is
non-empty before the review delegation is treated as successful, because the review path has
no `tasks.md` checkbox to backstop an unverified stdout success claim.

#### Scenario: Declared review artifact missing
- **WHEN** a review delegation declares an output artifact (e.g. a findings file) and the delegated agent does not create it
- **THEN** the system SHALL report a named failure rather than success

#### Scenario: Declared review artifact is empty
- **WHEN** a review delegation declares an output artifact and the delegated agent creates it but leaves it empty
- **THEN** the system SHALL report a named failure rather than success

#### Scenario: Apply path retains existing inspection
- **WHEN** an apply delegation produces code changes that the primary already inspects as a diff
- **THEN** the system SHALL NOT require the full outcome-resolution engine for the apply path; the existing diff inspection remains the apply contract

### Requirement: Verification is lightweight
The system SHALL implement review output verification as an existence-and-non-empty check
rather than adopting the full `evaluate()`/`resolver` workspace-and-status-file engine.

#### Scenario: No status-file protocol required for review
- **WHEN** review output verification runs
- **THEN** the system SHALL check the declared artifact path directly and SHALL NOT require the delegate to emit `status_*` files
