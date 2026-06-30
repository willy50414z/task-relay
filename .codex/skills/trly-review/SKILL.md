---
name: trly-review
description: Task Relay review workflow for OpenSpec changes. Use after OpenSpec propose when Task Relay review is enabled, or when the user asks to run trly review / review-gate / $trly-review before apply; do not use for openspec explore.
---

# Trly Review

## Workflow

Run this skill after OpenSpec propose when Task Relay review is enabled. The normal OpenSpec path is:

```text
openspec.explore -> openspec.propose -> trly-review -> openspec.apply
```

Run the configured review gate:

```bash
trly review-gate --change <change>
```

The gate runs reviewers in parallel, runs arbiters in order, validates JSON
artifacts, and writes:

- `openspec/changes/<change>/review/delegation_review.md`
- `openspec/changes/<change>/review/delegation_review_result.json`
- reviewer JSON artifacts
- arbiter JSON artifacts

## Decisions

- `APPROVE`: do not edit OpenSpec artifacts. Report reviewer opinions and arbiter decision; review is complete and apply may proceed.
- `REJECT`: do not edit OpenSpec artifacts. Report reviewer opinions and arbiter reasons; stop before apply.
- `REVISE`: the primary agent must apply only the arbiter-adjudicated `actionable_items` before apply.

For `REVISE`:

1. Read `openspec/changes/<change>/review/delegation_review_result.json`.
2. Read the listed reviewer and arbiter artifacts.
3. Update only the named target artifacts, such as `proposal.md`, `design.md`, `tasks.md`, or `specs/**/spec.md`.
4. Follow the arbiter contract exactly. Do not re-arbitrate reviewer conflicts and do not adopt unadjudicated reviewer suggestions.
5. Run revision verification:

```bash
trly review-gate --change <change> --verify-revision
```

Only treat review as complete when verification reports `apply_ready: true`.

## Report

After review completes, report:

- final decision
- reviewer verdicts and concise findings
- arbiter decision summaries
- for `REVISE`, which OpenSpec artifacts the primary agent modified
- verification result
- whether apply may proceed

Do not run `trly apply` from this skill unless the user explicitly asks to continue.
