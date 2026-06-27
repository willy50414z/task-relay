## 0. Prerequisite

- [x] 0.1 Confirm `harden-delegation-runtime` C4 scoped packer and `delegation-observability` trace are available; deferred tasks in that change are not required unless they modify those surfaces

## 1. P0 — Accuracy measurement (gates the rest)

- [x] 1.1 Define the primary accuracy metric: spec precision/recall, task-block precision/recall, fallback rate, packet byte size
- [x] 1.2 Define secondary reporting for design-section recall without making it the primary accuracy score
- [x] 1.3 Define the eval example schema: task, expected specs, expected task blocks, expected design sections, expected repo-file references, and evidence for each expected item
- [x] 1.4 Build a small labeled eval set of `(task -> expected scope)` examples with category coverage: narrow deterministic, ambiguous fallback, explicit-signal, and test-mode/diff cases
- [x] 1.5 Expand `trly pack --dry-run --json` diagnostics: `selection_mode` (deterministic / explicit_mapping / model_fallback), `spec_candidates` with scores, `missing_signals`, `repo_context_gap`, fallback reason, and dynamic diff source when present
- [x] 1.6 Metric runner: compute the metric over the eval set from the diagnostics; report precision/recall, fallback rate, packet size, sample count, and category coverage
- [x] 1.7 Tests: metric computation on a fixture eval set; diagnostics fields present and correct; category coverage appears in the report

## 2. P1 — Explicit, validated signals (deterministic)

- [x] 2.1 Define the change-local sidecar filename and YAML schema (tentative: `packer.yml`) for task-to-capability mapping, task dependencies, declared design sections, and declared repo-file references
- [x] 2.2 Packer consumes sidecar `task -> capability` mapping and `task dependencies` before token-overlap heuristics
- [x] 2.3 Derive-don't-declare: only require signals derivation can't produce
- [x] 2.4 `pack-lint` check (CLI + module): validate capability/spec exists, dependency task exists, declared design section exists, declared file exists, and tasks that will fall back
- [x] 2.5 Keep `pack-lint` advisory by default: diagnostic-only, no artifact mutation, no delegation blocking unless an explicit future gating mode is requested
- [x] 2.6 Tests: explicit mapping overrides heuristic; stale/invalid signal reported; lint flags fallback tasks; lint never edits artifacts; default lint does not block packing

## 3. P2 — Repo context: point-to default + dynamic test scope

- [x] 3.1 Default repo-file handling = reference/point-to (delegate reads in its worktree), not inline
- [x] 3.2 Opt-in inlining with a size/count guard
- [x] 3.3 Define the explicit dynamic diff input shape for test-mode packets (`--base`, `--diff-from`, `--diff-file`, or equivalent)
- [x] 3.4 Test-mode scope from the provided dynamic diff source (changed files + their tests); fall back to static scope when no diff is available
- [x] 3.5 Surface the dynamic diff source in `--dry-run --json` diagnostics for auditability
- [x] 3.6 Tests: default references not inlines; inline guard enforced; test packet scopes to changed files from explicit diff input; no-diff falls back cleanly; diagnostics show diff source

## 4. P3 — Model-assisted resolution (opt-in, last resort)

- [x] 4.1 Trigger only when deterministic can't uniquely resolve AND the resolver is enabled (default off)
- [x] 4.2 Constrained candidate-set construction; structured-result schema (specs, design_sections, task_dependencies, extra_reads, reason)
- [x] 4.3 Local deterministic validation of the model pick: selected paths/sections exist in the candidate set; invalid picks are rejected
- [x] 4.4 Soft cross-check against deterministic scores: flag outliers, but do not reject a valid candidate solely because it is outside token-overlap top candidates
- [x] 4.5 Cache resolver results by a full input hash covering task id/text, OpenSpec artifacts, sidecar signals, candidate set, resolver config, and dynamic diff fingerprint
- [x] 4.6 Reuse `delegation-observability` trace to record resolver token cost; enforce explicit per-run/per-pack model call limits
- [x] 4.7 Report fallback rate as an observed metric/warning signal, not as a directly enforceable control
- [x] 4.8 Tests: deterministic path skips the model; disabled-by-default falls back; invalid pick rejected; valid non-top candidate can be accepted when grounded; unsupported pick falls back; cache reuse; call limit enforced; diagnostics show model use

## 5. Close-out

- [x] 5.1 Re-run the P0 metric and confirm P1-P3 improved accuracy / fallback rate against the eval set, with sample count and category coverage shown
- [x] 5.2 `openspec validate enhance-context-packer` green; document the opt-in flags, sidecar schema, diff input option, and model call limit behavior
