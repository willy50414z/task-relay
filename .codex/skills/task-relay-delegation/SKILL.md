---
name: task-relay-delegation
description: Delegation skill for task-relay managed OpenSpec workflows.
---

## Task Relay Delegation

This project uses task-relay delegation with **codex** as the primary
orchestration agent.

### Review Chain

- primary: **claude** (model: claude-opus-4-8)
- fallback 1: **deepseek** (model: deepseek-v4-pro[1m])

### Apply Chain

- primary: **deepseek** (model: deepseek-v4-pro[1m])

### Primary Execution Workflow

The primary agent should use task-relay explicitly rather than asking a
delegate from free-form chat. Package context first, then run the selected
chain target with the packet file.

#### Review

Use review during the OpenSpec propose phase:

```bash
trly pack --mode review-proposal --change <change> --out <packet>
trly run --target claude --prompt-file <packet> --expect-output spec/delegation_review.md
```

The review delegate must write `spec/delegation_review.md`. The primary
agent must read that artifact before accepting findings; a non-empty file
only proves the output gate passed.

#### Apply

Use apply during implementation or test drafting:

```bash
trly pack --mode implementation-draft --change <change> --task <task-id> --out <packet>
trly run --target deepseek --prompt-file <packet> --isolate --base <base-ref>
```

For test packets, use `--mode test-draft` and add `--diff-from` or
`--diff-file` when dynamic changed-file context is needed. `--isolate`
runs the delegate in an ephemeral git worktree on a throwaway `tr/<id>`
branch with `git push` disabled. The primary agent reviews and integrates
accepted branch diffs, runs final verification, and only then marks
OpenSpec tasks complete.

### Output Modes

When receiving a delegation prompt packet, produce ONE of:

- **review-proposal**: Review a proposal for clarity, correctness, and completeness.
- **implementation-draft**: A patch or file-by-file edit plan.
- **test-draft**: Tests to add and the command to run them.
- **review**: Findings against a diff or spec, with severity.
- **diagnosis**: Likely root cause and next fix for a failing command.

Return only the requested output. Do not modify OpenSpec state or mark tasks complete.