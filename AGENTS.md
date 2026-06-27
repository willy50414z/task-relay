# Agent Guidance

<!-- task-relay:start -->
## Task Relay Delegation

- primary: codex
- scope: project
- features: review, apply
- review-chain: claude=claude-opus-4-8, deepseek=deepseek-v4-pro[1m]
- apply-chain: deepseek=deepseek-v4-pro[1m]

Delegation: codex orchestrates — review via claude=claude-opus-4-8, deepseek=deepseek-v4-pro[1m]; apply via deepseek=deepseek-v4-pro[1m].

Primary model (codex) owns:
- Architecture, security, data migration, destructive operations, credentials.
- OpenSpec artifact interpretation, scope, and state changes.
- Integration of delegated output and final verification.

## Review Workflow (propose phase)

When a proposal is ready for review, codex SHALL:
1. Package the proposal context using the `review-proposal` template.
2. Delegate to review chain (primary: claude).
3. The review agent evaluates requirement clarity, direction correctness,
   and implementation plan completeness.
4. The review agent writes findings to `spec/delegation_review.md`.
5. The review agent MUST ask the user when encountering ambiguity
   rather than defining solutions independently.
6. Delegate with `trly run --target <agent> --prompt-file <packet> --expect-output spec/delegation_review.md` so a missing or empty review fails loudly instead of being trusted from stdout.
7. If the run fails with a delegation-output error, re-run or escalate; do NOT treat the review as done.
8. codex MUST read the review artifact content before adopting it; a non-empty file only proves the gate passed.
9. codex reads the review and updates proposal artifacts as needed.

Review agent non-goals: do not modify OpenSpec state, mark tasks,
perform destructive operations, or make architecture decisions.

## Apply Workflow (implementation phase)

When implementation is ready, codex SHALL:
1. Package the apply request using implementation-draft or test-draft templates.
2. For multi-task apply, open one change worktree `chg/<change-name>` from HEAD as the integration sandbox; single trivial delegations may skip this and use one isolated task branch directly.
3. Delegate each implementation or test task to apply chain (primary: deepseek) with `trly run --target <agent> --prompt-file <packet> --isolate --base <ref>`.
4. `--isolate` runs the delegate in an ephemeral git worktree on a throwaway branch `tr/<id>` with `git push` disabled; `--base` points at the change branch tip so dependent tasks see previously accepted work.
5. Apply is phased: develop and commit onto task branches, merge accepted task branches back into `chg/<change-name>`, run disjoint test delegations from the accumulated change branch, then run primary integration tests in the change worktree before a single final merge to the real branch.
6. codex reviews each branch diff before merge and marks tasks complete only after the accepted work is integrated. An empty branch fails loudly (no silent success).

Apply agent non-goals: do not modify OpenSpec state, mark tasks checkboxes,
or make architecture/security/migration decisions.

## Task Tags

- `[delegate:review]` — route proposal review to review chain.
- `[delegate:deepseek]` — route implementation to apply chain.
- `[delegate:test]` — route test authoring.
- `[codex-only]` — keep in primary agent.

Use `trly run --target <agent> --prompt-file <packet>` for delegated work.

<!-- task-relay:end -->
