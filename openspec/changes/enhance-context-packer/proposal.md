## Why

`trly pack` (shipped in `harden-delegation-runtime` C4) selects packet scope with deterministic
rules: target task block, key `design.md` sections, and the most-relevant delta spec by token
overlap, falling back to all specs with a visible scope note. This is stable, cheap, and
reproducible, but accuracy drops when task wording, spec naming, or design structure are unclear —
the packer then falls back broadly or under-scopes repo context. This change raises scope-selection
accuracy WITHOUT sacrificing predictability, auditability, or the scope boundary. Source:
`openspec/changes/harden-delegation-runtime/context-packer-enhance.md` plus six review additions
(notably: define how accuracy is measured BEFORE changing selection, and keep model assistance a
constrained, opt-in, last resort).

## What Changes

- **P0 — Accuracy measurement first (gating).** Define a scope-selection accuracy metric
  (primary: spec/task-block precision/recall, fallback rate, packet byte size; secondary:
  design-section recall) and a small labeled eval set (`(task → expected scope)`) with explicit
  ground-truth labeling rules. Without this, no later phase is verifiable. Emit per-pack selection
  diagnostics as the raw data for the metric.
- **P1 — Explicit, validated signals (deterministic).** Allow OpenSpec artifacts to carry signals
  the packer consumes first via a change-local sidecar file (e.g. task-to-capability mapping,
  task dependencies, extra extractable `design.md` sections). **DRY:** declare only what
  deterministic derivation can't get. A `pack-lint` post-propose check validates these signals
  (capability/spec exists, dependency task exists, declared file exists) and reports advisory
  diagnostics only, never auto-mutating artifacts or blocking delegation by default.
- **P2 — Repo context: point-to by default, not inline.** Because the delegate runs in a worktree
  with the full repo, the packer SHALL by default declare repo files for the delegate to read
  rather than inline them (avoids re-bloating the packet — the regression C4 fixed). Inlining is
  opt-in and size/count-guarded. Test-mode packets SHALL be able to scope from an explicit dynamic
  source, such as a caller-provided base ref or diff, not only static artifacts.
- **P3 — Model-assisted scope resolution (opt-in, last resort).** When deterministic rules can't
  uniquely resolve scope, an opt-in resolver may use DeepSeek to pick from a CONSTRAINED candidate
  set and return a structured result (specs, design sections, dependencies, repo-file candidates).
  It never authors the packet (local renderer keeps control). The model's self-reported confidence
  is NOT trusted as the gate; the local resolver validates the structured pick deterministically
  (paths/sections exist) and uses deterministic scores as a soft outlier check rather than a hard
  top-candidate filter. Results are cached by a hash that covers the task, OpenSpec artifacts, the
  candidate set, and any dynamic diff fingerprint. Deterministic stays the default; fallback rate
  is reported as an accuracy signal, while model call volume is bounded separately by explicit
  per-run limits.

Non-goals (from the source doc, retained): the model never generates the final packet markdown;
model involvement is always visible in diagnostics; model assistance never replaces the
deterministic baseline; no full manifest system.

## Capabilities

### New Capabilities

- `packer-scope-accuracy`: An accuracy metric, a labeled eval set, and per-pack selection
  diagnostics that double as the metric's raw data.
- `packer-explicit-signals`: Packer-consumable signals in OpenSpec artifacts plus a `pack-lint`
  validation/diagnostic check.
- `packer-repo-context`: Default point-to (not inline) for repo files with a size/count guard, and
  dynamic test-mode scope from the change-branch diff.
- `packer-model-resolution`: Opt-in, constrained, deterministically-validated, cached model scope
  resolver used only when deterministic rules can't resolve.

### Modified Capabilities

- None as delta specs. This builds on `delegation-packet-generation` from
  `harden-delegation-runtime`; that change must land first (its C4 is the baseline). No base specs
  exist under `openspec/specs/` to modify.

## Impact

- **Code:** `task_relay/packer.py` (signal consumption, point-to vs inline, diagnostics, resolver
  hook), a new `pack-lint` surface (CLI + check), the `trly pack --dry-run --json` diagnostics
  expansion, and an optional model-resolution module gated behind a flag. Token capture/trace from
  `delegation-observability` is reused to measure resolver cost.
- **OpenSpec authoring convention:** P1/P2 introduce optional artifact signals — an
  ecosystem-level convention change. Signals live in a change-local sidecar so human-readable
  OpenSpec files stay clean and existing `openspec validate` behavior is not redefined. Adopt
  incrementally and validate ROI against the P0 metric.
- **Token cost:** P0–P2 are deterministic (0 LLM tokens). P3 adds a bounded, opt-in DeepSeek call
  only on genuine ambiguity; the cache and explicit per-run call limit keep it off the happy path.
- **Dependency / sequencing:** depends on `harden-delegation-runtime` C4 (scoped packer) and reuses
  its `delegation-observability` trace. Should not be implemented until that change lands.
