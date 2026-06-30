# Agent Guidance

<!-- task-relay:start -->
## Task Relay Delegation

- primary: codex
- scope: project
- features: review, apply
- reviewers: codex:/review=gpt-5.5-high, deepseek:/review=deepseek-v4-pro[1m]
- arbiter: claude:/plan-ceo-review
- arbiter: claude:/plan-eng-review
- global-timeout: 900
- apply-chain: codex=gpt-5.5-medium, deepseek=deepseek-v4-pro[1m]

Delegation: codex orchestrates — parallel review via codex:/review=gpt-5.5-high, deepseek:/review=deepseek-v4-pro[1m] with arbitration via claude:/plan-ceo-review, claude:/plan-eng-review; apply via codex=gpt-5.5-medium, deepseek=deepseek-v4-pro[1m].

Primary model (codex) owns:
- Architecture, security, data migration, destructive operations, credentials.
- OpenSpec artifact interpretation, scope, and state changes.
- Integration of delegated output and final verification.

## Review Workflow (propose phase)

When a proposal is ready for review, codex SHALL:
1. Package reviewer and arbiter packets using `review-proposal` and `review-arbiter` templates.
2. Run all configured reviewers in parallel: codex:/review=gpt-5.5-high, deepseek:/review=deepseek-v4-pro[1m].
3. Run arbiters serially in order: claude:/plan-ceo-review, claude:/plan-eng-review.
4. Reviewers write unique JSON artifacts and arbiters write decision JSON.
5. The CLI validates JSON artifacts and computes final gate state programmatically.
6. Global review gate timeout is `900` seconds unless overridden.
7. codex may only apply `REVISE` items to OpenSpec artifacts; revision direction comes only from the arbiter's adjudicated contract, and codex MUST NOT re-arbitrate reviewer conflicts or directly adopt unadjudicated reviewer suggestions.
8. `REJECT` stops before apply. `APPROVE` proceeds directly, and `REVISE` may proceed after codex applies the arbiter revision contract.

Reviewer and arbiter non-goals: do not modify OpenSpec state, mark tasks,
perform destructive operations, or make final file edits.

## Apply Workflow (implementation phase)

When implementation is ready, codex SHALL:
1. Package the apply request using implementation-draft or test-draft templates.
2. For multi-task apply, open one change worktree `chg/<change-name>` from HEAD as   the integration sandbox; single trivial delegations may skip this and use one   isolated task branch directly.
3. Delegate each implementation or test task to apply chain (primary: codex)   with `trly run --target <agent> --prompt-file <packet> --isolate --base <ref>`.
4. `--isolate` runs the delegate in an ephemeral git worktree on a throwaway   branch `tr/<task-id>` with `git push` disabled; `--base` points at the change   branch tip so dependent tasks see previously accepted work.
5. Apply is phased: develop and commit onto task branches, merge accepted task   branches back into `chg/<change-name>`, run disjoint test delegations from the   accumulated change branch, then run primary integration tests in the change   worktree before a single final merge to the real branch.
6. codex reviews each branch diff before merge and marks tasks complete   only after the accepted work is integrated. An empty branch fails loudly (no   silent success).

Apply agent non-goals: do not modify OpenSpec state, mark tasks checkboxes,
or make architecture/security/migration decisions.

## Task Tags

- `[delegate:review]` — route proposal review to parallel reviewers plus serial arbiters.
- `[delegate:codex]` — route implementation to apply chain.
- `[delegate:test]` — route test authoring.
- `[codex-only]` — keep in primary agent.

Use `trly run --target <agent> --prompt-file <packet>` for delegated work.

<!-- task-relay:end -->
