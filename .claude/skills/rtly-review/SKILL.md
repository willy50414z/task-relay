---
name: rtly-review
description: Trigger the task-relay review gate — runs parallel reviewers and arbiter against an OpenSpec change.
triggers:
  - review
  - code review
  - review this change
  - review proposal
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - AskUserQuestion
---

# /rtly:review

Run the task-relay review gate against an OpenSpec change. Invokes parallel
reviewers followed by arbiter arbitration, producing a PASS / CONCERNS /
BLOCKED decision.

## Usage

```
/rtly:review --change <change-name>
/rtly:review --change <change-name> --target zerotoken
/rtly:review --change <change-name> --target deepseek --no-save
```

## Cold-start (first run)

If the project has no task-relay managed block in AGENTS.md, the skill MUST
guide the user through a minimal interactive setup before running the review:

1. Detect: run `grep -q "task-relay:start" AGENTS.md 2>/dev/null`. If exit code != 0, AGENTS.md has no managed block.
2. If no managed block exists:
   a. Tell the user: "No task-relay config found. Quick setup (2 questions):"
   b. Ask: "Which agent for review? [claude / deepseek / zerotoken]" (default: claude)
   c. Ask: "Which agent for arbiter? [claude / deepseek / zerotoken]" (default: claude)
   d. Write the minimal managed block to AGENTS.md via `trly install --targets <primary> --scope project --feature review --review-chain <review-agent>`
   e. Proceed with review.
3. If managed block exists, proceed directly.

## Per-invocation override

- `--target <agent>` — override the review agent for this run, persist to AGENTS.md
- `--model <model>` — override the model, persist to AGENTS.md
- `--no-save` — one-time override, do not persist

## Execution

Run the review gate via the existing CLI:

```bash
trly review-gate --change <change-name> --json
```

If `--target` is specified, pass it as `--reviewers <agent>`.

After the review completes, read the output JSON and present a summary:
- **PASS** → "All reviewers passed. Proceed to apply."
- **CONCERNS** → "Concerns found. Review the actionable items in spec/delegation_review.md."
- **BLOCKED** → "Review blocked. See spec/delegation_review_result.json for details."

## Configuration

The skill reads reviewer/arbiter configuration from the AGENTS.md managed block.
To view or modify the full workflow config, use:

```bash
trly dev steps      # list all workflow step configs
trly dev config --step review --target zerotoken  # change review agent
```
