---
name: trly-apply
description: Task Relay delegated apply workflow for OpenSpec implementation or test tasks. Use during OpenSpec apply when Task Relay apply is enabled, or when the user asks to run trly apply / invoke $trly-apply; do not use for proposal review.
---

# Trly Apply

## Workflow

Use this skill in two phases when Task Relay apply is enabled:

1. During OpenSpec propose, prepare delegate-ready tasks and context-packer boundaries.
2. During OpenSpec apply, run delegated implementation or test drafting.

## Propose Preparation

Do not run implementation delegates during propose. Instead, make sure the OpenSpec
artifacts create a usable apply queue:

- `tasks.md` has granular, ordered task ids that can be delegated independently.
- Implementation tasks are tagged for the apply chain, for example `[delegate:<agent>]`.
- Test-authoring tasks are tagged `[delegate:test]` when they should be delegated separately.
- Each task points to the relevant design section, spec capability, repo area, and expected verification command.
- Dependencies between tasks are explicit so apply can sequence isolated worktrees safely.
- Context-packer inputs are discoverable from task text, design headings, spec headings, and any extra repo references.

If those artifacts are missing, revise the proposal artifacts before apply; otherwise
`trly apply` has no bounded task to package and delegate.

## Apply Execution

When Task Relay apply is enabled, OpenSpec apply workflows should invoke this skill automatically.
If the change has a prior `REVISE` review result, do not proceed unless revision
verification reports `apply_ready: true`.

Run the high-level apply command:

```bash
trly apply --change <change> --task <task-id>
```

For test drafting:

```bash
trly apply --change <change> --task <task-id> --mode test-draft
```

Useful options:

- `--read <path>`: inline extra repo context; repeatable.
- `--diff-from <ref>` or `--diff-file <path>`: include dynamic changed-file context for test drafting.
- `--verify-cmd "<command>"`: run verification in a temporary worktree based on the delegated branch.
- `--base <ref>`: branch the isolated delegate worktree from a specific base.

## Responsibilities

The primary agent must review the delegated branch diff before integration. Mark
OpenSpec tasks complete only after accepted work is integrated and verified.

Apply delegates must not modify OpenSpec state, mark task checkboxes, or make
architecture, security, credential, migration, or destructive-operation decisions.

## Report

After apply completes, report:

- delegated branch name
- diff summary
- verification result, if any
- whether the branch is ready for primary integration
