## Why

The current propose-phase review gate treats configured reviewers and arbiters as a fixed execution chain, which makes stronger persona coverage expensive and makes clean PASS cases pay for unnecessary arbitration. The review workflow needs profile-driven persona selection, mechanical PASS-only approval, and robust recovery from malformed reviewer artifacts while preserving primary-agent control over routing.

## What Changes

- Add reviewer profiles that select review personas, not agent/model entries.
- Treat configured review agents as fallback candidates; the selected agent runs every persona in the chosen reviewer profile in parallel.
- Add a dedicated `/devils-advocate` reviewer persona for adversarial proposal review.
- Add independent arbiter profiles, defaulting to engineering arbitration and allowing product-heavy review to choose product arbitration.
- Replace unconditional arbiter execution with a deterministic reducer:
  - all valid reviewer artifacts with `PASS` verdicts approve the review step and skip arbitration,
  - any valid `CONCERNS` or `BLOCKED` verdict runs the selected arbiter profile,
  - invalid reviewer artifacts are retried once with a corrective format prompt before being abandoned.
- Add canonical reviewer and arbiter artifact writing or validation helpers so delegated agents can produce stable JSON artifacts with consistent formatting.
- Record review profile, arbiter profile, reducer decision, retry attempts, skipped arbitration, and abandoned reviewer metadata in review outputs.
- Preserve explicit reviewer and arbiter override behavior for backward compatibility.
- Do not add automatic profile routing in the first release; the primary agent or CLI flag chooses profiles explicitly.

## Capabilities

### New Capabilities
- `review-profile-arbitration`: Defines profile-based reviewer persona selection, conditional arbiter execution, reviewer artifact retry behavior, and review result metadata.

### Modified Capabilities
- None.

## Impact

- Affected CLI commands: `trly review`, `trly review-gate`.
- Affected orchestration code: `task_relay/workflow/review_gate.py`, `task_relay/workflow/run_review.py`, and review config parsing/model code.
- Affected assets: review proposal and arbiter templates, reviewer/arbiter persona files, installed task-relay delegation skill guidance.
- Affected documentation: `docs/review-apply.md` and review usage examples.
- Affected tests: CLI review gate tests, review config tests, delegation/install guidance tests, and artifact validation/retry tests.
