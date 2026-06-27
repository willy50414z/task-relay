## 0. Pre-work decisions (RESOLVED — see design.md "Resolved Decisions")

- [x] 0.1 Sequencing → option (a): land hardening against current code now; redesign carries it forward. Do not edit shared files in parallel.
- [x] 0.2 C2 defaults → transient: honor Retry-After else 5s backoff cap 60s, max 5; hard: 1800s total budget @ 120s intervals; fast-fallback off by default
- [x] 0.3 C1 ownership → hybrid, trly-led (deterministic existence/non-empty check via expected-output param + thin managed-block reaction instruction)
- [x] 0.4 C3 isolation → uniform ephemeral worktree + push-disabled for ALL three CLIs; RETAIN the headless `--dangerously-*` flags (worktree cwd + push-disable is the boundary; removing the flags breaks headless writes); no OS sandbox/per-CLI profiles; threat model unreliable-not-malicious; read/network confinement deferred

## 1. C2 — Quota resilience (lowest blast radius, ship first)

- [x] 1.1 Split `QUOTA_ERROR_PATTERNS` in `agents/common.py` into transient (429/retry-after) vs hard (out-of-credits/monthly-limit) classes
- [x] 1.2 Replace the fixed `max_retries=288 × 300s` loop with a bounded total wall-time budget (default 1800s @ 120s intervals for hard; transient: honor Retry-After else 5s→60s backoff, max 5)
- [x] 1.3 Emit a log entry (agent, attempt, wait interval) before each retry sleep; remove the dead timestamp line (`_ =`)
- [x] 1.4 Add opt-in fast-fallback policy (default off) so hard exhaustion can move to the next chain agent in `core._run_with_fallback`
- [x] 1.5 Tests: transient short-wait, hard-exhaustion bounded budget, log emission, fast-fallback on vs off

## 2. C1 — Review output verification

- [x] 2.1 Define the declared review output artifact path contract (where the review packet names its output)
- [x] 2.2 Add an existence-and-non-empty gate in trly via an expected-output param (e.g. `trly run --expect-output <path>`)
- [x] 2.3 Surface a named failure when the artifact is missing or empty; add a thin managed-block instruction for how the primary reacts; leave the apply path's diff inspection unchanged
- [x] 2.4 Rename `delegent_review.md` → `delegation_review.md` across templates/guidance
- [x] 2.5 Tests: missing artifact fails, empty artifact fails, present non-empty passes, apply path untouched

## 3. C3 — Uniform ephemeral worktree + push disabled

- [x] 3.1 Spike: verify `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_*`/`GIT_CONFIG_VALUE_*` pushurl override takes precedence over local `.git/config` and that `git push` is rejected
- [x] 3.2 New `task_relay/worktree.py` — create worktree on throwaway branch `tr/<job_id>` under `.task_relay/`, cleanup via `git worktree remove --force` (mirror `workspace.py`, honor `TASK_RELAY_KEEP_IO`)
- [x] 3.3 Build the push-neutralizing subprocess env (enumerate remotes, inject dead pushurl per remote); merge into each agent's run env
- [x] 3.4 Run delegates with `cwd` = the worktree; RETAIN the headless flags (`--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox`) — removing them breaks headless writes; isolation = worktree cwd + push-disable, not flag removal
- [x] 3.5 Surface a loud failure when an apply delegation leaves the worktree with no changes; primary integrates by diffing/merging `tr/<job_id>`
- [x] 3.6 Update managed-block workflow text + packet templates to describe the worktree flow
- [x] 3.7 Tests: edits land in worktree not real tree, `git push` rejected, real `.git/config` unchanged after run, cleanup removes worktree+branch, normal apply still succeeds

## 4. C4 — Packet generation (deterministic scoped defaults)

> Review revision: the shipped v0 inlines the WHOLE change (~31KB for one task), defeating C4's
> token-savings goal. Default changes to deterministic scoped extraction; full-inline becomes an
> opt-in escape hatch.

- [x] 4.1 `trly pack --mode <mode> --change <change> --task <task-id>` command, `--out`/stdout, consumable by `trly run --prompt-file` (done)
- [x] 4.2 Unresolvable `--read` extra file loud-fails (done)
- [x] 4.3 REVISE default: replace full-change inline with deterministic scoped extraction — target task block (parent heading; siblings only when numbering needs them), `design.md` `Decisions` / `Risks / Trade-offs` / `Open Questions`, and the relevant capability spec
- [x] 4.4 When capability relevance can't be resolved, fall back to all delta specs WITH a visible `Scope note: ...` line in the packet header
- [x] 4.5 Add `--full-change-context` (today's full-inline behavior) as an escape hatch
- [x] 4.6 Add `--dry-run --json` (selected files/sections, byte estimate, fallback reason; no full packet)
- [x] 4.7 Tests: task-block extraction, design-section extraction, relevant-spec selection, fallback-note present, `--full-change-context`, `--dry-run --json`
- [x] 4.8 Update C4 spec wording so it no longer claims "exactly declared scoped reads" while inlining all artifacts

## 6. Pre-delegation working-tree guard (to develop)

- [x] 6.1 `worktree.py`: add `is_dirty(repo_root)` via `git status --porcelain` (unstaged + staged-uncommitted + untracked)
- [x] 6.2 `errors.py`: add `DirtyWorkingTreeError(TaskRelayError)`; export it from `task_relay/__init__.py`
- [x] 6.3 `core.run_isolated`: add `allow_dirty=False`; before `create_worktree`, if dirty and not allow_dirty raise `DirtyWorkingTreeError` with commit/`--allow-dirty` guidance (no worktree/branch created)
- [x] 6.4 CLI: add `trly run --allow-dirty` flag, threaded through `cli/run.py` into `run_isolated`
- [x] 6.5 Tests (`tests/test_worktree.py`): dirty stops + no worktree/branch; dirty + allow_dirty proceeds; clean proceeds

## 7. Multi-task apply: change-level integration worktree (to develop)

- [x] 7.1 `worktree.create_worktree`: add a `base="HEAD"` parameter (branch from a given ref, not always HEAD); thread `base` through `core.run_isolated`; add `trly run --isolate --base <ref>`
- [x] 7.2 Change-level integration worktree lifecycle: at apply-session start open `chg/<change-name>` from HEAD as the integration sandbox; merge each accepted task branch (`tr/<task-id>`) back into it; final single integration of `chg/<change-name>` into the real branch; cleanup removes the change + task worktrees and the throwaway branches
- [x] 7.3 Task delegations branch from the change-branch tip (so dependent tasks see prior accepted work without per-task base planning); single/trivial delegations may skip the change worktree
- [x] 7.4 Phased apply: develop+commit (onto the change branch) → parallel test delegations from the accumulated change branch (disjoint scopes) → primary runs integration tests in the change worktree
- [x] 7.5 Managed-block Apply Workflow text (code, in `delegation.py`): describe the phased model, task↔worktree mapping, `--base` = change-branch tip, and skip-for-single-delegation
- [x] 7.6 Tests: a task worktree based on the change branch sees a prior task's merged work; independent tasks run in parallel and both merge back; final integration lands on the real branch; cleanup removes all worktrees/branches

## 8. Observability / execution trace (to develop)

- [x] 8.1 Trace writer: append one JSONL record per delegation to `.task_relay/trace.jsonl` (path via `TASK_RELAY_TRACE_FILE`); fields: ts, session, target, model, role, change, task, duration_s, outcome, fallback_from, branch, tokens_in, tokens_out, cost_usd, retries
- [x] 8.2 Measure per-delegation wall-clock duration in `core` / `_run_with_fallback` (reuse the `JobResult.duration_seconds` pattern)
- [x] 8.3 Token capture: invoke the claude CLI (claude + deepseek) with `--output-format json`, parse `usage` (input/output tokens, cost when present), still return assistant text as `stdout`; record `null` for CLIs that don't expose usage (codex)
- [x] 8.4 Wire outcome/fallback/retry classification (success / fallback_from / quota / error) from `_run_with_fallback` + `run_subprocess` into the trace record
- [x] 8.5 Human log stream: emit per-delegation start/end at a level controlled by `LLM_LOG_LEVEL` (extends the existing quota-retry warnings)
- [x] 8.6 `trly trace --summary [--change <name>]` (FIRST minimal slice — build this first): read `.task_relay/trace.jsonl` and print aggregated totals — delegations count, total duration, total tokens (where available, else marked unknown), cost when present, retries, outcome counts, and per-agent + per-role breakdown; `--change` filters to one change; absent/empty file prints "no records". Deterministic, 0 LLM tokens
- [ ] 8.6a Deferred (after the minimal slice): richer `trly trace` filters (`--session` / `--agent` / `--since`), `--json` output, `--watch`
- [x] 8.7 Tests for the minimal slice: aggregation correct (duration/token sums, per-agent + per-role); `--change` filter; token `null` counted as "unknown" (not silently zero); absent/empty-file case
- [ ] 8.8 Deferred / separate follow-up (NOT this change): an optional `/delegation-retro` analysis skill consuming `trly trace --json`; aggregation stays in the CLI, never the skill

## 5. Close-out

- [x] 5.1 Document the reinstall step for picking up the new managed-block workflow (no auto-migration)
- [x] 5.2 Run `openspec validate harden-delegation-runtime` and confirm green
- [x] 5.3 Update README/docs/install.md where the trust/worktree flow and packet command are user-visible
- [x] 5.4 Add `/.task_relay/` to `.gitignore` (worktrees + eval workspaces) — done
- [x] 5.5 Naming: standardize the automated review artifact on `spec/delegation_review.md` everywhere; sync the stale dogfooded `AGENTS.md` + `.codex/skills/task-relay-delegation/templates/review-proposal.md` (still `delegent_review.md`) via edit or reinstall; keep `delegate_review.md` as a human review supplement only (not the `--expect-output` path)
- [x] 5.6 C1 reinforcement: add one managed-block line that the primary MUST read the review artifact content (non-empty ≠ correct), not just trust the gate; skip a severity-marker schema (over-engineering)
