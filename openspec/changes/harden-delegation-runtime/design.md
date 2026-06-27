## Context

The delegation runtime executes review/apply work by shelling out to agent CLIs
(`task_relay/agents/*.py` via `common.run_subprocess`). Today every agent runs with safety
rails fully off in the user's real working directory, quota errors retry silently for up to
~24h, the managed-block workflow routes delegation through the raw `run` pipe (bypassing the
`resolver` output contract), and packets are hand-formatted markdown templates the delegate
re-explores the repo to satisfy. This change hardens that runtime along four axes (C1–C4)
agreed during an explore session. It targets the current code, alongside the in-progress
`redesign-task-relay-architecture` migration which refactors the same adapters.

## Goals / Non-Goals

**Goals:**
- Remove the two defects: silent ~24h quota hang (C2) and unenforced trust boundary (C3).
- Close the review-path verification gap with a lightweight existence check (C1).
- Cut duplicate token consumption with a scoped packet generator (C4).
- Add the first regression tests for the runtime delegation path.

**Non-Goals:**
- Adopting the full `evaluate()`/`resolver` engine for delegation (C1 stays lightweight).
- Migrating already-installed managed-block guidance files automatically.
- Implementing the `redesign-task-relay-architecture` ports-and-adapters refactor here.
- Async jobs, persistent storage, or web relay.

## Decisions

### D1: C1 verification lives on the review path only, as an existence-and-non-empty gate
The apply path is already backstopped by the primary inspecting the diff and ticking
`tasks.md`. Review has no checkbox, and its artifact is a side file the primary may not reopen,
so a delegate can claim success via stdout while the file is missing/empty. Chosen: a direct
path existence + non-empty check. Rejected: full status-file/outcome engine (too heavy for the
value; the apply path does not need it).

### D2: C3 uses a uniform ephemeral worktree for all three CLIs, with `git push` neutralized
Threat model: the delegate is **unreliable, not malicious** (it may make wrong/sloppy changes
or accidentally clobber files, but is not assumed to actively exfiltrate). Under that model the
goal is to protect the real working tree and block the one easy destructive escape (`git push`
to real remotes), not full OS-level containment.

Chosen mechanism, **identical across claude / deepseek / codex** (avoids per-CLI sandbox
complexity and the network/env friction OS sandboxes cause):
- Run the delegate with `cwd` = an **ephemeral git worktree on a throwaway branch**
  (`tr/<job_id>`). Writes land there, not in the real working tree.
- **Neutralize `git push` process-locally**, because a git worktree shares the repo's `.git`
  (objects, refs, and remotes) — so without this a delegate could push to real remotes. Do NOT
  mutate `.git/config` (worktrees share it); instead inject an override via the subprocess
  **env** (`GIT_CONFIG_COUNT` / `GIT_CONFIG_KEY_*` / `GIT_CONFIG_VALUE_*`) setting each remote's
  `pushurl` to a dead value, scoped to that one delegate process.
- The worktree (separate dir) + push-disable is the enforced boundary. **Implementation note:**
  the CLIs' own headless-execution flags (`--dangerously-skip-permissions`, codex's bypass)
  are **retained** — removing them breaks headless writes (in `--print`/`exec` mode no human can
  approve a tool call, so the agent could not edit files at all). Under the unreliable-not-
  malicious model, redirecting the agent's normal writes into the worktree cwd + hard-blocking
  push is the protection; full flag removal needs the deferred OS sandbox.

Accepted residual risk under the threat model: the delegate can still read arbitrary paths
(e.g. `.env`) and reach the network. Full read/network confinement needs an OS-level sandbox
(container/bubblewrap/namespace) and is **deferred as follow-up**, not v1 — explicitly traded
away for uniformity and zero sandbox friction. (Note: network can't be blanket-denied anyway
because the delegate's own model API traffic must pass.) If the threat model later includes a
malicious delegate, prefer codex (native `--sandbox`) as the apply agent or add an OS sandbox.

### D3: C2 default preserves the cost advantage; fast fallback is opt-in
Quota-rejected calls are not billed, so fast fallback does not duplicate token spend — but it
does spend the more expensive fallback agent's tokens during an outage instead of waiting for
the cheap agent to recover. Some users prefer to wait. Chosen: the must-fix core is
observability + a bounded budget + transient/hard classification; fast fallback is an opt-in
policy, default off. Also split `QUOTA_ERROR_PATTERNS` so transient `429`/retry-after is not
treated identically to hard out-of-credits.

### D4: C4 generator uses deterministic scoped defaults (not full-change inline)
Review correction: the shipped v0 inlined proposal + design + tasks + ALL delta specs (~31KB for
one task), which defeats C4's token-savings goal and contradicts "scoped". Chosen v1: the packer
extracts a small, stable context with **local deterministic code** (no LLM, so no main-agent
tokens) per mode/task:
- the target task block (parent heading; siblings only when numbering needs them);
- `design.md` sections implementers need: `Decisions`, `Risks / Trade-offs`, `Open Questions`;
- the relevant capability spec when the task heading/text names a capability, else a fallback to
  all delta specs WITH a visible `Scope note:` line so the precision downgrade is not silent.

Escape hatches: `--full-change-context` (v0 behavior) and `--dry-run --json` (show selected
files/sections + byte estimate + fallback reason). A `--read PATH` extra file is still inlined and
still loud-fails when unresolvable. Manifest-driven scoping is explicitly **v2**, only if the
deterministic defaults become insufficient (≥3 modes conflict, or `packer.py` accretes special
cases) — not now, to avoid a new artifact authors must maintain.

### D6 (note): C1 gate is necessary, not sufficient
The `--expect-output` existence+non-empty check is deterministic tooling; non-empty does not mean
correct. The managed block MUST require the primary to read the review artifact's content before
adopting it. A severity-marker schema is intentionally NOT added (over-engineering for v1).

### D7 (future): per-mode quota policy
Out of scope here: a future enhancement could let `review` fail/fall back faster while `apply`
prefers waiting for the cheap agent (apply's token/risk is higher). v1 keeps one global policy.

### D5: Pre-delegation working-tree guard (stop, not warn) + `.task_relay/` gitignore
An ephemeral worktree is a clean `HEAD` checkout: the delegate does not see the main tree's
uncommitted/untracked changes (those stay safely in the main tree — your files are never
endangered), so an apply that depends on WIP would run against a stale base. Chosen: at the
first step of an isolated run, if the main tree is dirty, STOP with guidance ("commit and
re-run, or pass `--allow-dirty`") rather than warn-and-proceed — proceeding would do the work
against stale `HEAD`, making the warning useless. An explicit `--allow-dirty` override supports
the intentional clean-`HEAD` case (WIP unrelated to the task). Rejected: warn-only (silent
correctness trap); auto-seeding the worktree with WIP (heavier, untracked/staged edge cases,
and sometimes a clean HEAD is what you want).

Also: `.task_relay/` (used for both ephemeral worktrees `worktrees/<id>` and evaluation
workspaces `<job_id>`) must be gitignored — otherwise it shows as untracked noise in the main
tree and can be `git add -A`'d. Add `/.task_relay/` to `.gitignore`.

### D8: Multi-task apply uses a change-level integration worktree (to develop)
A multi-task apply session needs to commit and merge repeatedly. Doing that on the real working
branch pollutes it with intermediate state; doing each task as a fresh-from-HEAD worktree means a
dependent task can't see a prior task's not-yet-merged output. Chosen: open ONE change-level
integration worktree (`chg/<change-name>`, branched from the current branch's HEAD) as the
integration sandbox at apply-session start. Each task delegation branches from the **change-branch
tip** (the internal base mechanism — no per-task base planning), implements in its own `tr/<task-id>`
worktree, and merges back into the change branch after primary review; dependent tasks therefore
see prior accepted work. Tests fan out in parallel from the accumulated change branch (disjoint
scopes); the primary runs integration tests in the change worktree; at the end the change branch
merges into the real branch ONCE.

Properties: atomic (drop `chg/*` to abandon; the real branch stays untouched until final
integration), dependency-correct without pre-planning bases, and parallel-capable. Single/trivial
delegations skip the change worktree (don't build a sandbox for one small change). The dirty-tree
guard (D5) runs at apply-session start so the change branch starts from a clean, known HEAD; push
stays disabled for all delegate worktrees, and only the primary pushes after final integration.
Token-neutral: the extra worktree/branch/merge work is git plumbing (~0 LLM tokens) — the
token savings still come from C4 scoped packets, not from this structure. `base-ref` is the
internal knob enabling this; it is not a separate user-facing default. Rejected: per-task base
planning at propose time (error-prone — the user's concern); a single long-lived shared worktree
(loses the per-task clean-branch review boundary and complicates parallelism).

### D9: Observability via per-delegation JSONL trace (to develop)
Today the runtime is unobservable: the operator can't confirm a multi-agent flow ran, how long it
took, or what it cost. Chosen: a structured **JSONL trace** with one record per delegation
(`.task_relay/trace.jsonl`, already gitignored) — ts, session, agent, model, role, change/task,
duration, outcome (success / fallback / quota / error), branch, tokens, cost, retries — plus the
existing human log stream and an optional `trly trace --summary` aggregator. The JSONL is the
machine-readable source of truth (grep/`jq`); the log stream is live progress.

Token capture is the one non-trivial part and must be honest: the runners currently use
`claude --print` (plain text), which returns **no usage**. To record tokens, invoke the claude CLI
(claude + deepseek, both Anthropic-compatible) with `--output-format json` and parse the `usage`
field (input/output tokens, and cost when reported); the runner still returns the assistant text
as `stdout` for compatibility. codex may not expose equivalent usage — record `null`, never a
guess. Duration reuses the timing pattern already in `JobResult.duration_seconds`. This is also the
prerequisite for measuring whether C4 scoped packets actually cut delegate tokens — without it,
any token-savings claim is unverifiable.

## Risks / Trade-offs

- [C2 over-eager fallback misreads a transient 429 as hard exhaustion] → classification split
  in D3; default-off fast fallback means a misread waits rather than wrongly switching.
- [C1 false-negative: delegate succeeded but wrote to a slightly different path] → the packet
  declares the exact artifact path; gate checks that path; mismatch fails loud and is fixable.
- [C3 worktree adds I/O overhead] → accept the overhead for the security win; one worktree per
  delegation, cleaned up like `workspace.py` does.
- [C3 push-disable env override doesn't take precedence over local `.git/config`] → spike
  `GIT_CONFIG_*` precedence against a local remote before wiring all three adapters; the
  integration test asserts `git push` from the delegate env is rejected.
- [C3 accepted residual: delegate can still read `.env` / reach network] → out of scope under
  the unreliable-not-malicious threat model; OS sandbox deferred as follow-up.
- [C4 over-inlines and bloats the packet / under-scopes and misses context] → deterministic
  scoped defaults (D4); spec-relevance fallback inlines all specs but emits a visible `Scope note:`
  so the downgrade isn't silent; `--full-change-context` and `--read` cover the under-scoped case.

## Migration Plan

- Behavioral change to quota handling (C2) and to the managed-block workflow text (C3 worktree
  flow, C1 verification step) ships in the package; existing installs pick it up on reinstall.
- No automatic rewrite of already-installed guidance files. Document the reinstall step.
- Rollout order within this change: C2 and C1 first (low blast radius, no workflow change for
  users), then C3 (workflow + adapter change), then C4 (new surface).

## Resolved Decisions (from review 2026-06-27)

1. **Sequencing vs `redesign-task-relay-architecture` → option (a).** Land this hardening
   against current code now; the redesign (stalled since 2026-06-19) carries the behavior
   forward when it resumes, per its own "preserve working behavior" principle. Rationale: C2/C3
   are live defects (silent 24h hang, security) and should not wait on a stalled refactor. Do
   not edit the same files in both changes in parallel.
2. **C3 isolation → uniform ephemeral worktree + push-disabled (resolved in D2 above).** Same
   mechanism for all three CLIs: delegate runs with `cwd` = a worktree on a throwaway branch,
   `git push` neutralized via subprocess `GIT_CONFIG_*` env override. The headless
   `--dangerously-*` flags are **RETAINED** — removing them breaks headless writes (no human to
   approve a tool call in `--print`/`exec`), so the worktree cwd + push-disable is the boundary,
   not flag removal. No OS sandbox, no per-CLI profiles. Threat model: unreliable-not-malicious;
   read/network confinement deferred as follow-up.
3. **C1 ownership → hybrid, trly-led.** trly does the deterministic existence + non-empty check
   via an expected-output parameter (e.g. `trly run --expect-output <path>` or a review
   subcommand); the managed block keeps a thin instruction for how the primary reacts to a
   failure. trly is necessary-but-not-sufficient (it cannot judge content correctness).
4. **C2 defaults.** Transient (`429`/retry-after): honor `Retry-After`, else 5s exponential
   backoff capped at 60s/wait, max 5 retries. Hard exhaustion (fast-fallback off by default):
   total wall-time budget default 1800s (30 min) at 120s intervals, then surface a quota
   failure. All overridable via the existing `LLM_QUOTA_*` env knobs with the new defaults.
5. **C4 shape.** `trly pack --mode <mode> --change <change> --task <task-id>` → packet to stdout
   (or `--out`), consumable by `trly run --prompt-file`. Scope source: OpenSpec change artifacts
   provide the inlined content; the packet template placeholders define which slices; extra
   named repo files resolve by path; an unresolvable declared read errors out.
6. **Naming → rename `delegent_review.md` to `delegation_review.md`** (matches the codebase's
   "delegation" terminology), done as part of C1. `delegate_review.md` is an acceptable
   alternative pending final confirmation.

## Open Questions

- None blocking. Remaining sub-choices (exact env var names for C2, whether C1 uses a flag on
  `trly run` vs a dedicated `trly review` subcommand, final spelling for #6) are
  implementation-time details, not plan-level forks.
