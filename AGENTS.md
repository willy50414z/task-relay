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

Delegation: codex orchestrates — review via codex:/review=gpt-5.5-high, deepseek:/review=deepseek-v4-pro[1m] with arbitration via claude:/plan-ceo-review, claude:/plan-eng-review; apply via codex=gpt-5.5-medium, deepseek=deepseek-v4-pro[1m].

Primary model (codex) owns:
- Architecture, security, data migration, destructive operations, credentials.
- OpenSpec artifact interpretation, scope, and state changes.
- Integration of delegated output and final verification.

## Review Workflow (post-propose phase)

When review is enabled, OpenSpec propose workflows SHALL invoke `$trly-review`
after proposal artifacts are written. OpenSpec explore remains primary-only.

The `trly-review` skill packages reviewer and arbiter packets using
`review-proposal` and `review-arbiter` templates.
Configured reviewers: codex:/review=gpt-5.5-high, deepseek:/review=deepseek-v4-pro[1m].
Configured arbiters: claude:/plan-ceo-review, claude:/plan-eng-review.
Global review gate timeout is `900` seconds unless overridden.

For `REVISE`, codex may only apply arbiter-adjudicated `actionable_items` to
named OpenSpec artifacts, and MUST NOT re-arbitrate reviewer conflicts or
directly adopt unadjudicated reviewer suggestions.

Reviewer and arbiter non-goals: do not modify OpenSpec state, mark tasks,
perform destructive operations, or make final file edits.

## Apply Workflow (implementation phase)

When apply is enabled, OpenSpec propose workflows SHALL prepare delegate-ready
work before implementation begins: tasks must be granular, ordered, tagged for
delegation, and written so the context packer can map each task to the relevant
design sections, specs, repo references, and verification command.
Do not run implementation delegates during propose; only prepare the work queue
and context boundaries that apply will consume.

When implementation is ready, codex SHALL:
1. Use the `trly-apply` skill automatically from OpenSpec apply workflows.
2. Package the apply request using implementation-draft or test-draft templates.
3. For multi-task apply, open one change worktree `chg/<change-name>` from HEAD as   the integration sandbox; single trivial delegations may skip this and use one   isolated task branch directly.
4. Delegate each implementation or test task to apply chain (primary: codex)   with `trly run --target <agent> --prompt-file <packet> --isolate --base <ref>`.
5. `--isolate` runs the delegate in an ephemeral git worktree on a throwaway   branch `tr/<task-id>` with `git push` disabled; `--base` points at the change   branch tip so dependent tasks see previously accepted work.
6. Apply is phased: develop and commit onto task branches, merge accepted task   branches back into `chg/<change-name>`, run disjoint test delegations from the   accumulated change branch, then run primary integration tests in the change   worktree before a single final merge to the real branch.
7. codex reviews each branch diff before merge and marks tasks complete   only after the accepted work is integrated. An empty branch fails loudly (no   silent success).

Apply agent non-goals: do not modify OpenSpec state, mark tasks checkboxes,
or make architecture/security/migration decisions.

## Task Tags

- `[delegate:review]` — route proposal review to parallel reviewers plus serial arbiters.
- `[delegate:codex]` — route implementation to apply chain.
- `[delegate:test]` — route test authoring.
- `[codex-only]` — keep in primary agent.

Use `trly run --target <agent> --prompt-file <packet>` for delegated work.

<!-- task-relay:end -->
