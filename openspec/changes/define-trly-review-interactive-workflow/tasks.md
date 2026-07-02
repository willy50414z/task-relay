## 1. Review Setting Formatting

- [x] 1.1 [delegate:deepseek] Add a helper that converts `ReviewGateConfig` reviewer and arbiter entries into display rows with Role, Agent, Model, Effort, and Personas fields.
- [x] 1.2 [delegate:deepseek] Implement Codex model display splitting so ids like `gpt-5.5-high` display as `Model=gpt-5.5` and `Effort=high`, while non-Codex entries display `Effort=n/a`.
- [x] 1.3 [delegate:deepseek] Add persona alias normalization for `review`, `cso`, `qa`, `qa-only`, `ceo`, and `engineer`, preserving slash persona storage format.
- [x] 1.4 [delegate:test] Add unit tests for display rows, Codex model/effort splitting, non-Codex defaults, and persona alias normalization.

## 2. `$trly-review` Skill Contract

- [x] 2.1 [delegate:deepseek] Update generated `trly-review/SKILL.md` content to require saved config lookup before collecting new reviewer or arbiter routing.
- [x] 2.2 [delegate:deepseek] Update generated `trly-review/SKILL.md` content to show the saved setting table and ask whether to apply it before running review.
- [x] 2.3 [delegate:deepseek] Add the reviewer wizard sequence: reviewer-agent, reviewer-model, reviewer-effort only for Codex, reviewer-personas, and add-next-reviewer.
- [x] 2.4 [delegate:deepseek] Add the arbiter wizard sequence: arbiter-agent, arbiter-model, arbiter-effort only for Codex, arbiter-personas, and add-next-arbiter.
- [x] 2.5 [delegate:test] Extend skill generation tests to assert the new saved-config confirmation, table columns, wizard sequences, and persona alias rules are present.

## 3. Review Execution And Persistence UX

- [x] 3.1 [delegate:deepseek] Ensure `$trly-review` instructions route accepted saved settings through `trly review --change <change>` or equivalent API without re-asking for role fields.
- [x] 3.2 [delegate:deepseek] Ensure one-time settings are documented as explicit `--reviewers` and repeated `--arbiter` flags.
- [x] 3.3 [delegate:deepseek] Ensure save behavior is documented with `--save`, and with explicit `--save-targets` and `--save-scope` when no managed block exists.
- [x] 3.4 [delegate:test] Add tests or golden assertions covering saved setting execution, one-time override execution, and save guidance.

## 4. Arbiter Revision Contract Handling

- [x] 4.1 [delegate:deepseek] Update `$trly-review` instructions so `APPROVE` and `REJECT` never edit OpenSpec artifacts.
- [x] 4.2 [delegate:deepseek] Update `$trly-review` instructions so `REVISE` reads `delegation_review_result.json` and updates only target artifacts named by arbiter `actionable_items`.
- [x] 4.3 [delegate:deepseek] Update `$trly-review` instructions to prohibit applying reviewer suggestions that are not included in arbiter `actionable_items`.
- [x] 4.4 [delegate:deepseek] Ensure `REVISE` instructions require `trly review-gate --change <change> --verify-revision` and completion only when apply-ready is true.
- [x] 4.5 [delegate:test] Add tests or golden assertions covering the `APPROVE`, `REJECT`, and `REVISE` decision handling text.

## 5. Integration Verification

- [x] 5.1 [codex-only] Review the final skill contract against `proposal.md`, `design.md`, and `specs/trly-review-interactive-workflow/spec.md` before implementation is marked complete.
- [x] 5.2 [delegate:test] Run targeted tests for review config helpers and skill generation.
- [x] 5.3 [codex-only] Run the full project test command appropriate for this repository and inspect any failures before final integration.
- [x] 5.4 [codex-only] Run `openspec status --change define-trly-review-interactive-workflow` and confirm the change remains apply-ready.
