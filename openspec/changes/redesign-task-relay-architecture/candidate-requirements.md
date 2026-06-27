# Candidate Requirements — explore session 2026-06-26

> Status: **CANDIDATE / not yet ratified.** These come from an explore-mode review of the
> delegation runtime (review/apply). They are captured here so they are not lost, and are
> intentionally kept OUT of the validated `specs/<capability>/spec.md` deltas until the
> team decides which to adopt. To adopt one: move its Requirement + Scenarios into the
> target capability's `spec.md`, add corresponding `tasks.md` entries, and update
> `proposal.md` scope.

Each candidate lists: target capability, the problem (with code evidence), a draft
`Requirement` (SHALL form), draft `Scenario`s, and an open question to resolve before adopting.

---

## C1 — Delegated work must have a verifiable output contract

**Target capability:** `openspec-delegation-install` (and touches `task-execution-core`)

**Problem.** The runtime has two execution engines: `evaluate()` enforces a structured
contract (workspace + `status_*` files + `resolver.py` + declared `output_files`), while
`run()` is a raw stdin→stdout pipe with no verification. The delegation managed block routes
review/apply through `run` (`delegation.py:203` — `trly run --target <agent> --prompt-file`),
so every packet's `Expected output`, `Verification command`, and "write findings to
`spec/delegent_review.md`" instruction is **honor-system only**: nothing checks the delegate
actually produced what the packet asked for. The structured `resolver` guarantees
(missing-output-file fails loudly) are bypassed by the path the feature actually uses.

### Requirement: Verifiable delegation output
The system SHALL give delegated review/apply work a verifiable output contract so that a
delegate's failure to produce the requested artifact is detected by the tooling rather than
relying on the orchestrator to notice.

#### Scenario: Declared delegation artifact missing
- **WHEN** a delegation packet declares an expected output artifact (e.g. a review findings file or a patch) and the delegated agent does not produce it
- **THEN** the system SHALL surface a loud, named failure to the orchestrator rather than returning success

#### Scenario: Delegation runs through the outcome-routed path
- **WHEN** review or apply delegation is executed
- **THEN** the system SHALL either route the work through the outcome-routed contract (status + declared output files) or provide an equivalent post-run verification step, not a raw stdout pass-through

**Open question.** Adopt the existing `evaluate()` engine for delegation (reuse `resolver`),
or add a lighter verification layer on top of `run()`? If the former, decide whether
`run` remains a public primitive or becomes internal.

---

## C2 — Quota handling must be observable, bounded, and fall back fast

**Target capability:** `agent-adapter-registry` (subprocess behavior) + `task-execution-core` (fallback)

**Problem.** `run_subprocess` retries quota errors `max_retries=288` × `interval=300s` = **up to
24 hours**, with **no logging** during the wait (`common.py:50-51`, `:80` computes a timestamp
then discards it via `_ =`). Because `AgentQuotaError` subclasses `AgentExecutionError`
(`errors.py:17`) and the retry happens *inside* `run_subprocess`, the fallback chain
(`_run_with_fallback`, `core.py:126`) does not engage until the exhausted agent has retried for
24 hours — defeating the purpose of a fallback chain in exactly the case (quota exhaustion)
where switching agents is most useful. This is the most likely failure mode for the
token-heavy apply phase, and it currently presents as a silent hang.

### Requirement: Observable quota waiting
The system SHALL emit a visible log/status entry each time it waits and retries on a quota
or rate-limit error, including the agent name, attempt number, and wait interval.

#### Scenario: Quota retry is logged
- **WHEN** an agent returns a quota or rate-limit error and the system decides to wait and retry
- **THEN** the system SHALL emit a log entry identifying the agent, the attempt number, and the wait duration before sleeping

### Requirement: Quota errors prefer fallback over long single-agent retry
The system SHALL prefer falling back to the next agent in a chain over exhausting a long
retry budget on a single quota-exhausted agent.

#### Scenario: Quota error falls back when a chain exists
- **WHEN** the primary agent in a fallback chain returns a quota error and another agent is available in the chain
- **THEN** the system SHALL move to the next agent rather than completing the full single-agent quota retry budget first

#### Scenario: Retry budget is bounded and configurable
- **WHEN** no fallback agent is available and the system retries on quota
- **THEN** the total retry wall-time SHALL be bounded by a configurable limit rather than a fixed ~24-hour default

**Open question.** Default total retry ceiling (e.g. 30 min?) and whether fallback-then-retry
or retry-then-fallback is the right ordering when the whole chain is quota-limited.

---

## C3 — Delegated agents must run under an enforced trust boundary

**Target capability:** `agent-adapter-registry` (adapter-owned command construction)

**Problem.** All three adapters launch with safety rails off — `--dangerously-skip-permissions`
(`claude.py:16`, `deepseek.py:36`) and `--dangerously-bypass-approvals-and-sandbox`
(`codex.py:19`) — inside the user's real `cwd`. The managed block and packet templates assert
"primary owns security / destructive ops / credentials" and list `Non-goals: do not perform
destructive operations`, but these are **prompt text with zero enforcement**: a delegated
agent physically can `rm`, `git push`, or read `.env`. The trust model that justifies
delegating to a cheaper/less-trusted model is stated but not enforced.

### Requirement: Enforced delegation trust boundary
The system SHALL enforce the delegation trust boundary through execution constraints, not
only through prompt instructions, so that a delegated agent cannot perform the destructive or
credential-sensitive operations the policy reserves for the primary.

#### Scenario: Delegated agent cannot perform reserved operations
- **WHEN** a delegated review or apply agent attempts a destructive or credential-accessing operation that policy reserves for the primary
- **THEN** the execution environment SHALL prevent it (e.g. sandbox, restricted working copy, or permission profile) rather than relying on the agent honoring a prompt non-goal

#### Scenario: Trust profile is explicit per role
- **WHEN** an agent is invoked as a delegate versus as the primary orchestrator
- **THEN** the system SHALL apply a permission/sandbox profile appropriate to that role rather than a single "skip all permissions" mode for every agent

**Open question.** What enforcement mechanism is acceptable without crippling apply's ability
to edit files — sandboxed/scoped working copy, allowlisted tools, ephemeral worktree, or a
read-only delegate that only emits diffs the primary applies? (C1's "delegate emits diff"
direction and C3 reinforce each other.)

---

## C4 — Packet generation command (scoped, inlined, standardized)

**Target capability:** `task-relay-cli` (new subcommand) + `openspec-delegation-install` (templates)

**Problem.** Delegation packets are hand-filled markdown templates with `<placeholder>` fields
(`assets/.../templates/*.md`). The orchestrator formats each packet by hand every time, which
(a) spends primary tokens on formatting, (b) is inconsistent, and (c) leaves `Allowed direct
reads` unenforced — the delegate, launched with skip-permissions, re-explores the whole repo
from a cold start, re-ingesting the same context per packet. A generator that assembles the
packet from a change/task and inlines exactly the scoped file slices would standardize the
format, enforce scoping, and cut duplicate token consumption.

### Requirement: Packet generation command
The system SHALL provide a command that generates a delegation packet for a given mode and
task, inlining the scoped context the packet declares rather than leaving it for the delegate
to rediscover.

#### Scenario: Generate a scoped packet
- **WHEN** a user requests a packet for a given mode (e.g. `implementation-draft`) and a target change/task
- **THEN** the system SHALL produce a packet pre-filled with the template structure and the inlined content of the declared scoped reads

#### Scenario: Generated packet is consumable by `trly run`
- **WHEN** a generated packet is passed to the delegation execution path
- **THEN** the delegate SHALL be able to act on the inlined context without needing to re-read the source repository to reconstruct it

**Open question.** Command shape (`trly pack --mode … --change … --task …`?), how it locates
"declared scoped reads", and how this interacts with C1's output contract and C3's trust
boundary (inlined context + diff-only output is the natural pairing).

---

## Adoption checklist (per candidate)

- [ ] C1 — Verifiable delegation output → `openspec-delegation-install` / `task-execution-core`
- [ ] C2 — Observable + bounded + fast-fallback quota handling → `agent-adapter-registry` / `task-execution-core`
- [ ] C3 — Enforced delegation trust boundary → `agent-adapter-registry`
- [ ] C4 — Packet generation command → `task-relay-cli` / `openspec-delegation-install`
