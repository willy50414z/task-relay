## Why

The delegation runtime that powers the `review` and `apply` features has four structural
gaps found in an explore-mode review (2026-06-26/27). Two are defects that will bite users
(a silent ~24h quota hang; an unenforced trust boundary where a delegated agent can run
destructive operations), one is a correctness gap on the review path (delegate "success" is
trusted from stdout with no artifact check), and one is a token-cost optimization (packets
are hand-formatted and the delegate re-explores the repo each call). These were captured as
candidate requirements on the in-progress `redesign-task-relay-architecture` change; this
change turns the agreed subset into an executable plan against the current codebase.

## What Changes

- **C1 — Review output verification.** On the review delegation path (which has no `tasks.md`
  checkbox to backstop it), the primary SHALL verify the declared output artifact exists and
  is non-empty before treating the delegation as successful. This is a lightweight existence
  gate, NOT adoption of the full `evaluate()`/`resolver` engine. The apply path keeps its
  existing diff inspection.
- **C2 — Quota resilience.** **BREAKING (behavioral):** replace the fixed ~24h silent retry
  (`max_retries=288 × 300s`, no logging) with: (a) an observable retry that logs agent,
  attempt, and wait each time it sleeps; (b) a bounded, configurable total retry budget; and
  (c) classification of transient throttling (e.g. `429` / `Retry-After`) versus hard quota
  exhaustion (e.g. out-of-credits). Fast fallback to the next chain agent on hard exhaustion
  is an **opt-in policy**, default off, so the "wait for the cheap agent" cost advantage is
  preserved by default.
- **C3 — Enforced trust boundary.** Stop running every delegate with `--dangerously-skip-permissions`
  / `--dangerously-bypass-approvals-and-sandbox` in the user's real working tree. **Uniform
  mechanism for all three CLIs** (no per-CLI sandbox, no OS sandbox): run the delegate with its
  working directory set to an **ephemeral git worktree** on a throwaway branch (delegate still
  writes files, but not in the real tree), and **neutralize `git push`** process-locally via a
  subprocess `GIT_CONFIG_*` env override (a worktree shares the repo's `.git`/remotes). The
  CLIs' headless-execution flags are retained (removing them breaks headless writes); the
  worktree + push-disable is the enforced boundary. Threat model: unreliable-not-malicious;
  read/network confinement is deferred. The primary integrates by diffing/merging the throwaway
  branch. **Pre-delegation working-tree guard:** because the worktree is a clean `HEAD` checkout,
  the delegate does not see the main tree's uncommitted/untracked changes; an isolated run that
  finds a dirty main tree STOPS with guidance (commit and re-run) unless `--allow-dirty` is
  passed. **Multi-task apply (to develop):** an apply session opens one change-level integration
  worktree (`chg/<change-name>`); task delegations branch from the change-branch tip, merge back
  after review, and the change branch integrates into the real branch once — atomic, dependency-
  correct, parallel-capable, with the real branch untouched until the final integration.
- **C4 — Packet generation.** Add a command that generates a delegation packet for a given
  mode and task using **deterministic scoped defaults** (target task block + key design sections +
  the relevant capability spec) instead of inlining the whole change, so the delegate gets focused
  context and duplicate token consumption drops. A `--full-change-context` escape hatch keeps the
  whole-change behavior, and `--dry-run --json` shows what would be selected; when capability
  relevance can't be resolved, it falls back to all specs with a visible scope note.
- **C5 — Observability / execution trace (to develop).** Record one structured JSONL trace
  record per delegation (`.task_relay/trace.jsonl`): timestamp, agent, model, role, change/task,
  duration, outcome (success / fallback / quota / error), branch, and **token usage when the CLI
  exposes it**. Capture tokens by invoking the claude CLI (claude + deepseek) with
  `--output-format json` and parsing `usage`; record `null` when unavailable (e.g. codex) rather
  than guessing. Human-readable progress goes to the log stream (level via `LLM_LOG_LEVEL`); an
  optional `trly trace --summary` aggregates a session's total time, tokens, and per-agent
  breakdown. This is how the operator verifies the multi-agent flow ran, how long it took, and
  what it cost.

## Capabilities

### New Capabilities

- `delegation-output-verification`: Existence/non-empty verification of declared delegation
  output on the review path before success is recorded.
- `delegation-quota-resilience`: Observable, bounded, classified quota/rate-limit handling
  with opt-in fast fallback.
- `delegation-trust-boundary`: Uniform ephemeral-worktree isolation + process-local push-disable
  for delegated agents (headless flags retained; OS sandbox deferred), a pre-delegation
  dirty-working-tree guard, and a change-level integration worktree for atomic multi-task apply.
- `delegation-packet-generation`: Command that generates deterministic scoped-default delegation
  packets, with a full-change escape hatch and dry-run transparency.
- `delegation-observability`: Per-delegation JSONL execution trace (duration, outcome, token
  usage when the CLI exposes it) plus a session summary, so the operator can verify the flow,
  time, and token cost.

### Modified Capabilities

- None. There are no base specs under `openspec/specs/`; the overlapping in-progress
  `redesign-task-relay-architecture` change is a separate migration and is not modified here
  (see Impact for the coupling note).

## Impact

- **Code:** `task_relay/agents/common.py` (retry/classification/logging — C2),
  `task_relay/agents/{deepseek,claude,codex}.py` (extra-env merge for push-disable — C3),
  `task_relay/core.py` (`_run_with_fallback` policy — C2; `run_isolated` + dirty-tree guard — C3),
  new `task_relay/worktree.py` (worktree lifecycle, push-disable, dirty check — C3), a new
  packet-generation surface in `task_relay/cli/` + `task_relay/packer.py` (C4), and the
  delegation guidance/templates in `task_relay/delegation.py` +
  `task_relay/assets/task-relay-delegation/` (C1 verification instruction, C3 worktree workflow,
  C4 packet command reference).
- **Repo hygiene:** add `/.task_relay/` to `.gitignore` so ephemeral worktrees
  (`.task_relay/worktrees/<id>`) and evaluation workspaces (`.task_relay/<job_id>`) don't appear
  as untracked noise or get accidentally committed.
- **Tests:** the runtime delegation path is currently untested; this change adds coverage for
  quota classification, retry bounding, trust-profile command construction, output
  verification, and packet generation.
- **Backward compatibility:** the managed-block workflow text changes (worktree/patch flow,
  verification step). Already-installed users get the new text on reinstall; no automatic
  migration of existing guidance files is in scope.
- **Coupling:** `redesign-task-relay-architecture` (in-progress, 24/36) refactors the same
  adapters into ports-and-adapters. This change targets the current code; if the redesign
  lands first, C2/C3 move into the new adapter shape. The two should not be implemented in
  parallel against the same files. Sequencing is an open question (see design.md).
