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

### Output Modes

When receiving a delegation prompt packet, produce ONE of:

- **review-proposal**: Review a proposal for clarity, correctness, and completeness.
- **implementation-draft**: A patch or file-by-file edit plan.
- **test-draft**: Tests to add and the command to run them.
- **review**: Findings against a diff or spec, with severity.
- **diagnosis**: Likely root cause and next fix for a failing command.

Return only the requested output. Do not modify OpenSpec state or mark tasks complete.