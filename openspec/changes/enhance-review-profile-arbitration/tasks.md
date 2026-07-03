## 1. Profile Models and CLI Surface

- [x] 1.1 [delegate:deepseek] Add reviewer and arbiter profile enums/config mappings in `task_relay/review_config.py`; cover design decisions 1 and 7 plus spec requirements "Reviewer profiles select personas" and "Arbiter profiles select arbitration personas".
- [x] 1.2 [delegate:deepseek] Add `--review-profile` and `--arbiter-profile` to `trly review` and `trly review-gate`; preserve existing `--reviewers` and `--arbiter` overrides per design decision 8.
- [x] 1.3 [delegate:deepseek] Update review config construction so profile-based runs select one effective reviewer agent/model from configured reviewer fallback entries; cover design decision 2.

## 2. Artifact Helper and Validation

- [x] 2.1 [delegate:deepseek] Add `task_relay/review_artifacts.py` with reviewer and arbiter validation functions and stable JSON writer functions; cover design decisions 5 and 6.
- [x] 2.2 [delegate:deepseek] Move or wrap existing reviewer/arbiter artifact validation in `review_gate.py` to use the shared artifact helper without weakening current schema checks.
- [x] 2.3 [delegate:deepseek] Enforce reviewer consistency rules: `PASS` requires empty findings, `CONCERNS` and `BLOCKED` require findings or persona-specific concern fields, and `/devils-advocate` requires `fatal_flaw`, `simpler_alternative`, and `reverse_case`.

## 3. Persona and Template Assets

- [x] 3.1 [delegate:deepseek] Add `reviewer-devils-advocate.md` to the task-relay delegation persona assets; make it read-only and focused on fatal assumptions, simpler alternatives, and reverse-case analysis.
- [x] 3.2 [delegate:deepseek] Update `review-proposal.md` to document `fatal_flaw`, `simpler_alternative`, and `reverse_case`, and to instruct delegates to use the canonical artifact helper when available.
- [x] 3.3 [delegate:deepseek] Update `review-arbiter.md` and arbiter personas to handle `CONCERNS`, `BLOCKED`, abandoned reviewer metadata, and risk-weighted conflict resolution.
- [x] 3.4 [delegate:deepseek] Update persona alias mapping and installed skill bundle copy/guidance so `/devils-advocate`, reviewer profiles, and arbiter profiles are visible after install.

## 4. Review Gate Orchestration

- [x] 4.1 [delegate:deepseek] Expand reviewer profiles into persona-specific review jobs that run in parallel through the selected review agent/model; maintain unique reviewer artifact paths.
- [x] 4.2 [delegate:deepseek] Implement one-time corrective retry for invalid reviewer artifacts; include validation errors, output path, schema rules, and a valid JSON example in the retry prompt so the delegate job log shows the correction request.
- [x] 4.3 [delegate:deepseek] Implement the deterministic reducer: clean valid `PASS` from every selected reviewer approves and skips arbitration; `CONCERNS` or `BLOCKED` triggers the selected arbiter profile.
- [x] 4.4 [delegate:deepseek] Implement abandoned reviewer handling: all abandoned fails the gate; any abandoned with remaining valid reviews triggers arbitration and passes abandoned metadata to arbiter packets.
- [x] 4.5 [delegate:deepseek] Make arbiter execution conditional while preserving serial arbiter behavior whenever an arbiter profile or explicit arbiter override is invoked.

## 5. Result Artifacts, Docs, and Guidance

- [x] 5.1 [delegate:deepseek] Extend `delegation_review_result.json` and human-readable summary output with reviewer profile, arbiter profile, selected personas, selected execution agent, reducer decision, retry attempts, abandoned reviewers, arbiter invocation state, and skip reasons.
- [x] 5.2 [delegate:deepseek] Update `docs/review-apply.md` to describe profile-based reviewer personas, fallback review agents, PASS-only reducer approval, conditional arbitration, artifact retry, and helper-based artifact output.
- [x] 5.3 [delegate:deepseek] Update generated task-relay delegation skill guidance in `task_relay/delegation.py` so installed agents understand the new review and arbiter profile workflow.

## 6. Tests

- [x] 6.1 [delegate:test] Add tests for reviewer profile expansion, arbiter profile expansion, selected review agent fallback behavior, and CLI profile flags.
- [x] 6.2 [delegate:test] Add tests for clean PASS reducer approval, skipped arbitration metadata, `CONCERNS` triggering arbitration, and `BLOCKED` triggering arbitration.
- [x] 6.3 [delegate:test] Add tests for invalid reviewer artifact retry, retry prompt contents, abandoned reviewer metadata, and all-reviewers-abandoned gate failure.
- [x] 6.4 [delegate:test] Add tests for canonical artifact helper validation/writing, including `/devils-advocate` required adversarial fields.
- [x] 6.5 [delegate:test] Add compatibility tests for explicit `--reviewers` manual override and explicit `--arbiter` conditional invocation behavior.

## 7. Primary Integration and Verification

- [ ] 7.1 [codex-only] Review delegated diffs for architecture, backward compatibility, and conformance to the OpenSpec requirements before merging task branches.
- [ ] 7.2 [codex-only] Run focused review workflow tests with `pytest` after integration, including CLI, delegation, and artifact validation coverage.
- [ ] 7.3 [codex-only] Run the existing full test suite if focused tests pass, then update this task list only after accepted work is integrated and verified.

