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
4. The review agent writes findings to `spec/delegent_review.md`.
5. The review agent MUST ask the user when encountering ambiguity
   rather than defining solutions independently.
6. codex reads the review and updates proposal artifacts as needed.

Review agent non-goals: do not modify OpenSpec state, mark tasks,
perform destructive operations, or make architecture decisions.

## Apply Workflow (implementation phase)

When implementation is ready, codex SHALL:
1. Package the apply request using implementation-draft or test-draft templates.
2. Delegate to apply chain (primary: deepseek).
3. The apply agent produces patches or implementation reports.
4. codex verifies output before marking tasks complete.

Apply agent non-goals: do not modify OpenSpec state, mark tasks checkboxes,
or make architecture/security/migration decisions.

## Task Tags

- `[delegate:review]` — route proposal review to review chain.
- `[delegate:deepseek]` — route implementation to apply chain.
- `[delegate:test]` — route test authoring.
- `[codex-only]` — keep in primary agent.

Use `trly run --target <agent> --prompt-file <packet>` for delegated work.

<!-- task-relay:end -->
