## Context

`harden-delegation-runtime` C4 shipped a deterministic scoped packer (`task_relay/packer.py`):
per-mode template, target task block, key `design.md` sections, best-overlap delta spec, visible
fallback to all specs, `--full-change-context` and `--dry-run --json`. It is stable, cheap, and
reproducible but loses accuracy when artifacts are unclear. This change raises accuracy while
keeping those properties. It builds on C4 and reuses `delegation-observability` for measuring cost.

## Goals / Non-Goals

**Goals:**
- Make scope-selection accuracy measurable before changing it.
- Raise accuracy with deterministic, validated, explicit signals.
- Keep repo context lean (point-to, not inline) and cover dynamic test scope.
- Allow a constrained, opt-in, reproducible model resolver only as a last resort.

**Non-Goals:**
- The model generating final packet markdown.
- Hiding model involvement.
- Replacing the deterministic baseline.
- A full manifest system.

## Decisions

### D1: Measurement gates the work (P0 first)
Every "more accurate" claim needs the metric + labeled eval set, or it is unverifiable (the same
lesson as observability's "no measurement, no claim"). The `--dry-run --json` diagnostics are the
raw data. Primary accuracy metrics are spec precision/recall, task-block precision/recall, fallback
rate, and packet byte size. `design.md` section selection is tracked as a secondary recall signal
because section relevance is more subjective than spec/task relevance. P0 lands before P1-P3 so
each later phase is judged, not assumed.

### D2: Eval ground truth is labeled by rule, not by packer intuition
The labeled eval set records `(task -> expected scope)` with explicit fields for expected specs,
expected task blocks, expected design sections, and expected repo-file references. A label is valid
only when it cites the artifact text or implementation dependency that makes the scope necessary.
The initial set may start from existing changes, but it must include successful narrow cases,
ambiguous fallback cases, explicit-signal cases, and test-mode/diff cases before being used for
claims. The metric runner reports sample count and category coverage with the score so small or
biased eval sets are visible.

### D3: Explicit signals live in a change-local sidecar
Authors declare only what deterministic derivation cannot get; the packer derives the rest.
Explicit signals live in a change-local sidecar (tentative filename: `packer.yml`) under the change
directory, not inline in `tasks.md`. This keeps human-readable OpenSpec files clean and avoids
redefining `openspec validate` semantics. `pack-lint` validates declared signals (capability/spec
exists, dependency exists, file exists) and is advisory by default: it reports actionable diagnostics
but does not auto-edit artifacts and does not block delegation unless a caller explicitly opts into
a future gating mode.

### D4: Repo files are referenced by default, inlined only opt-in and guarded
The delegate runs in a worktree with the full repo, so it can read declared files itself. Inlining
repo source would re-bloat the packet - the regression C4 just fixed. Default = point-to; inline =
opt-in with a size/count guard. Test-mode scope may draw on an explicit dynamic source, such as a
caller-provided base ref or diff path, to identify files changed during the apply session and their
tests. If no dynamic source is provided, test-mode falls back to static artifact scope.

### D5: Model resolver is constrained, validated, cached, opt-in, and call-bounded
When deterministic rules cannot uniquely resolve scope, an opt-in resolver may call DeepSeek to pick
from a constrained candidate set and return structured JSON (specs, sections, deps, repo-file
candidates). It never authors the packet. Self-reported confidence is not the gate: the local
resolver validates paths/sections, verifies every choice came from the candidate set, and uses
deterministic scores as a soft outlier check rather than a hard top-N filter. A model pick can
choose outside the token-overlap winners when the candidate exists and the reason is grounded; picks
with no deterministic support (for example zero-overlap and no explicit signal) fall back
conservatively with a visible note.

Resolver results are cached by an input hash that covers the task id/text, OpenSpec artifact
contents, sidecar signal contents, candidate set, resolver configuration, and any dynamic diff
fingerprint. Fallback rate is observed and reported as an accuracy metric; it is not directly
"enforced". Model cost is controlled by explicit per-run/per-pack call limits and by cache reuse.

## Risks / Trade-offs

- [Explicit signals go stale and mislead the packer] -> `pack-lint` validates them; derive rather
  than declare where possible (D3).
- [Sidecar convention adds one more file] -> keeps `tasks.md` readable and avoids coupling to
  OpenSpec validator internals (D3).
- [Inlining repo files re-bloats packets] -> point-to by default; inline is opt-in and size-guarded (D4).
- [Dynamic diff discovery becomes implicit magic] -> require an explicit base ref or diff source;
  fall back cleanly when absent (D4).
- [Model resolver hurts reproducibility / adds token cost] -> cache by full input hash, keep
  deterministic default, and enforce explicit model call limits rather than pretending fallback rate
  itself is enforceable (D5).
- [Trusting model self-confidence] -> rejected; accept/reject by deterministic validation and soft
  outlier checks (D5).
- [Eval set overfits local author intuition] -> require label evidence, category coverage reporting,
  and visible sample counts before accepting improvement claims (D2).

## Migration Plan

- P0 (metric + eval set + diagnostics) ships first and is non-breaking.
- P1 adds optional sidecar signals and advisory `pack-lint`; existing packs keep working without a
  sidecar.
- P2 adds point-to repo references by default and opt-in guarded inlining.
- P3 is behind an opt-in flag, default off, with explicit per-run call limits.
- Sequenced after `harden-delegation-runtime` C4 scoped packer and `delegation-observability` trace
  are available; deferred work in that change is not required unless it changes those surfaces.

## Open Questions

1. Exact metric thresholds (target precision/recall and acceptable fallback-rate warning level).
2. Final sidecar filename and YAML schema field names.
3. Exact per-run/per-pack model resolver call limits.
4. Exact CLI shape for dynamic test scope (`--base`, `--diff-from`, `--diff-file`, or equivalent).
