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

- primary: **deepseek** (model: deepseek-v4-pro[1m])
- fallback 1: **codex** (model: gpt-5.5-medium)

### Primary Execution Workflow

The primary agent should use task-relay explicitly rather than asking a
delegate from free-form chat. Package context first, then run the selected
chain target with the packet file.

#### Apply

When apply is enabled, OpenSpec propose workflows prepare delegate-ready
tasks before implementation begins: each task should be granular, ordered,
tagged for delegation, and written so the context packer can map it to the
relevant design sections, specs, repo references, and verification command.
Do not run implementation delegates during propose.

When apply is enabled, OpenSpec apply workflows invoke `$trly-apply` for
delegated implementation or test drafting. The underlying command is:

```bash
trly apply --change <change> --task <task-id>
```

`$trly-apply` owns the full apply workflow, including branch diff review,
verification, and integration handoff.

Lower-level commands remain available for diagnostics and custom workflows:

```bash
trly pack --mode implementation-draft --change <change> --task <task-id> --out <packet>
trly run --target deepseek --prompt-file <packet> --isolate --base <base-ref>
```


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

- **implementation-draft**: A patch or file-by-file edit plan.
- **test-draft**: Tests to add and the command to run them.
- **review**: Findings against a diff or spec, with severity.
- **diagnosis**: Likely root cause and next fix for a failing command.

Return only the requested output. Do not modify OpenSpec state or mark tasks complete.