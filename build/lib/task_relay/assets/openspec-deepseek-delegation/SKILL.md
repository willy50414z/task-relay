---
name: openspec-deepseek-delegation
description: Delegate bounded OpenSpec apply tasks to DeepSeek for implementation drafts, test drafts, review, and diagnosis. Use this whenever `tasks.md` contains `[delegate:deepseek]`, `[delegate:test]`, or `[delegate:review]` work for this repository.
---

# OpenSpec DeepSeek Delegation

Use this skill during OpenSpec apply after you have read the change artifacts and identified a bounded delegate task.

Keep the package compatible with `$skill-creator`: frontmatter stays limited to `name` and `description`, reusable resources stay bundled under this skill directory, and the root stays free of extra docs such as `README.md` or `CHANGELOG.md`.

## Boundaries

Codex remains the only actor allowed to change OpenSpec scope, integrate delegated output, update `tasks.md` checkboxes, and perform final verification.

Keep delegation in the development orchestration layer. Do not wire `trly`, LLM calls, or these packets into deterministic inner experiment graph runtime nodes.

Do not use a non-DeepSeek fallback when the user or task packet explicitly requires DeepSeek. If DeepSeek is unavailable, record the failure and take over in Codex.

## Dispatch

Use the repository-local command:

```powershell
trly run --target deepseek --prompt-file <packet> --timeout <seconds> --cwd <project>
```

Pick the template that matches the task:

- `[delegate:deepseek]` -> `templates/implementation-draft.md`
- `[delegate:test]` -> `templates/test-draft.md`
- `[delegate:review]` -> `templates/review.md`
- `[delegate:optional]` -> use the matching template only when the packet remains small and independently verifiable
- Diagnosis after a failing command -> `templates/diagnosis.md`

## Timeout Policy

- `implementation-draft`: 600 seconds
- `test-draft`: 300 seconds
- `review`: 300 seconds
- `diagnosis`: 180 seconds

Use a smaller timeout for trivial packets. Increase only when the packet stays bounded but needs more context.

## Workflow

1. Re-read `AGENTS.md` and the relevant task entry in `tasks.md`.
2. Fill the packet template with task id, objective, bounded context, non-goals, expected output, and verification command.
3. Write run artifacts under:

   ```text
   research/orchestration/runs/<run_id>/
     delegate_packets/
     delegate_outputs/
     delegate_metadata/
   ```

   Use a stable `run_id` such as `<change-slug>-apply-YYYYMMDDTHHMMSSZ`.

4. Save the packet in `delegate_packets/` and dispatch it with the command above.
5. Save raw stdout/stderr in `delegate_outputs/`.
6. Record one metadata JSON file per attempt in `delegate_metadata/`.
7. Review the delegate output yourself. DeepSeek output is never applied work by itself.
8. Integrate accepted parts, run the verification command, then mark the OpenSpec task complete.

Prefer direct file reads over broad inline dumps. It is acceptable to point the delegate at `tasks.md`, `design.md`, or spec files when the packet names the exact task id or section the delegate should read.
