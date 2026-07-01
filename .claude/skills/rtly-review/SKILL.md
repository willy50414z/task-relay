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

# /trly:review

Run the task-relay review gate against an OpenSpec change. Invokes parallel
reviewers followed by arbiter arbitration, producing a PASS / CONCERNS /
BLOCKED decision.

## Usage

```
/trly:review --change <change-name>
/trly:review --change <change-name> --reviewers claude:/review --arbiter claude:/plan-eng-review
/trly:review --change <change-name> --reviewers deepseek:/review --arbiter claude:/plan-eng-review --save
```

## Interactive Selection

Before running the review, ask the user to choose the routing for this run:

1. Reviewer agent and persona, in `agent:/persona` form.
   - Default reviewer persona: `/review`.
   - Examples: `claude:/review`, `deepseek:/review`, `codex:/review=gpt-5.5-high`.
2. Arbiter agent and persona, in `agent:/persona` form.
   - Default arbiter chain: `claude:/plan-ceo-review`, then `claude:/plan-eng-review`.
   - Examples: `claude:/plan-eng-review`, `deepseek:/review-arbiter`.
3. Whether to save this run's reviewer/arbiter settings for future reviews.

Do not use the install wizard to configure review routing. Use the answers to
build a `trly review` command for this run.

## Cold-start

If the project has no task-relay managed block, the review can still run with
explicit reviewer and arbiter selections. If the user chooses to save and no
managed block exists yet, ask where to save it:

- install target: `codex` or `claude`
- scope: `project` or `user`

Then pass `--save-targets <target> --save-scope <scope>` with `--save`.

## Execution

Run the review gate via `trly review`:

```bash
trly review --change <change-name> --reviewers <agent:/persona> --arbiter <agent:/persona> --json
```

If the user chose to save, add `--save`. If no managed block exists yet, also
add `--save-targets <target> --save-scope <scope>`.

After the review completes, read the output JSON and present a summary:
- **PASS** → "All reviewers passed. Proceed to apply."
- **CONCERNS** → "Concerns found. Review the actionable items in spec/delegation_review.md."
- **BLOCKED** → "Review blocked. See spec/delegation_review_result.json for details."

## Configuration

The skill reads reviewer/arbiter defaults from the managed block when present,
but every invocation should still confirm the reviewer and arbiter selection
with the user. To view the full workflow config, use:

```bash
trly dev steps      # list all workflow step configs
```
