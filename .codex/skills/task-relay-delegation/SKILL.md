---
name: task-relay-delegation
description: Delegation skill for task-relay managed OpenSpec workflows.
---

## Task Relay Delegation

This project uses task-relay delegation with **codex** as the primary
orchestration agent and **deepseek** for delegated draft work.

### Agent Configuration

- Primary: codex (model: gpt-5.5-medium)
- Sub-agent: deepseek (model: deepseek-v4-pro[1m])

### Output Modes

When receiving a delegation prompt packet, produce ONE of:

- **implementation-draft**: A patch or file-by-file edit plan.
- **test-draft**: Tests to add and the command to run them.
- **review**: Findings against a diff or spec, with severity.
- **diagnosis**: Likely root cause and next fix for a failing command.

Return only the requested output. Do not modify OpenSpec state or mark tasks complete.