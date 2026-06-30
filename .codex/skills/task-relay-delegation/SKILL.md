---
name: task-relay-delegation
description: Delegation skill for task-relay managed OpenSpec workflows.
---

## Task Relay Delegation

This project uses task-relay delegation with **codex** as the primary
orchestration agent.

### Reviewers

- **codex** persona `/review` (model: gpt-5.5-high)
- **deepseek** persona `/review` (model: deepseek-v4-pro[1m])

### Arbiter Chain

- stage 1: **claude** persona `/plan-ceo-review` (model: default)
- stage 2: **claude** persona `/plan-eng-review` (model: default)

Global timeout: `900` seconds.

### Apply Chain

- primary: **codex** (model: gpt-5.5-medium)
- fallback 1: **deepseek** (model: deepseek-v4-pro[1m])

### Primary Execution Workflow

The primary agent should use task-relay explicitly rather than asking a
delegate from free-form chat. Package context first, then run the selected
chain target with the packet file.

#### Review

Use review during the OpenSpec propose phase:

```bash
trly review-gate --change <change>
```

The review gate runs reviewers in parallel, arbiters in order, validates
JSON artifacts, and writes a merged `openspec/changes/<change>/review/delegation_review.md` summary.

#### Apply

Use apply during implementation or test drafting:

```bash
trly apply --change <change> --task <task-id>
```

This high-level command packages the packet, uses the configured apply
chain, runs the delegate in an isolated worktree, fails loudly on empty
output, and prints a branch diff summary.

Lower-level fallback:

```bash
trly pack --mode implementation-draft --change <change> --task <task-id> --out <packet>
trly run --target codex --prompt-file <packet> --isolate --base <base-ref>
```

For test packets, use `--mode test-draft` and add `--diff-from` or
`--diff-file` when dynamic changed-file context is needed. `--isolate`
runs the delegate in an ephemeral git worktree on a throwaway `tr/<id>`
branch with `git push` disabled. The primary agent reviews and integrates
accepted branch diffs, runs final verification, and only then marks
OpenSpec tasks complete.

### Post-Install Validation

After `trly install`, run:

```bash
trly doctor
```

`trly doctor` checks configured targets, tokens, CLI availability, model
catalog matches, writable paths, managed blocks, and scope conflicts so
setup issues fail before the first real delegated run.

### Output Modes

When receiving a delegation prompt packet, produce ONE of:

- **review-proposal**: Review a proposal for clarity, correctness, and completeness.
- **implementation-draft**: A patch or file-by-file edit plan.
- **test-draft**: Tests to add and the command to run them.
- **review**: Findings against a diff or spec, with severity.
- **diagnosis**: Likely root cause and next fix for a failing command.

Return only the requested output. Do not modify OpenSpec state or mark tasks complete.