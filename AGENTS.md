# Agent Guidance

<!-- task-relay:start -->
## Task Relay Delegation

- primary: codex
- mode: hybrid
- sub-agent: deepseek
- scope: project
- models:
  - codex: gpt-5.5-medium
  - deepseek: deepseek-v4-pro[1m]

Delegation mode: hybrid — codex orchestrates, deepseek handles bounded delegated work.

Primary model (codex) owns:
- Architecture, security, data migration, destructive operations, credentials.
- OpenSpec artifact interpretation, scope, and state changes.
- Integration of delegated output and final verification.

Sub-agent (deepseek) handles:
- Bounded implementation drafts with clear file scope.
- Small-scope tests and test suggestions.
- Documentation extraction and summaries.
- Repetitive edits.
- Failure diagnosis and first-pass review.

Propose-time task tags for delegation:
- `[delegate:deepseek]` — route implementation to sub-agent.
- `[delegate:test]` — route test authoring.
- `[delegate:review]` — route review/diagnosis.
- `[delegate:optional]` — delegate when prompt packet is small.
- `[codex-only]` — keep in primary agent.

Use `trly run --target deepseek --prompt-file <packet>` for delegated work.

<!-- task-relay:end -->
