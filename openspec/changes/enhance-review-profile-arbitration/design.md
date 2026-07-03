## Context

The current review gate loads concrete reviewer and arbiter entries from the managed block, runs each configured reviewer in parallel, then always runs the configured arbiter chain. This made sense when a review configuration represented the whole review workflow, but it does not scale well once review quality depends on a larger pool of personas such as `/review`, `/devils-advocate`, `/qa-only`, and `/cso`.

The desired model separates three concerns:

- review agents are fallback candidates for execution,
- reviewer profiles select the personas that inspect a proposal,
- arbiter profiles select the personas that adjudicate non-clean reviewer output.

The primary agent or CLI chooses the profiles. Delegated reviewers and arbiters remain read-only artifact producers and never choose workflow routing.

## Goals / Non-Goals

**Goals:**
- Add explicit reviewer profiles for persona selection.
- Add explicit arbiter profiles for arbitration persona selection.
- Keep the default reviewer profile predictable: `standard`.
- Keep the default arbiter profile predictable: `engineering`.
- Select one review agent/model from the configured fallback reviewer entries, then run all reviewer-profile personas through that selected agent in parallel.
- Skip arbitration when every required reviewer artifact is valid and has a `PASS` verdict.
- Run arbitration when any valid reviewer artifact has `CONCERNS` or `BLOCKED`.
- Retry malformed reviewer artifacts once with a corrective prompt that appears in delegate logs.
- Abandon a reviewer persona after a failed retry, while preserving failure metadata for arbitration or failure reporting.
- Add a canonical Python artifact writer/validator helper for reviewer and arbiter JSON artifacts.

**Non-Goals:**
- Do not add automatic keyword-based profile routing in the first release.
- Do not let delegates spawn additional review delegates.
- Do not change apply-phase delegation behavior.
- Do not require strict profile to run arbiters when every reviewer cleanly passes.
- Do not remove explicit `--reviewers` or `--arbiter` override compatibility.

## Decisions

### 1. Profiles select personas, not agents

Reviewer profiles expand to persona lists:

```text
lite      = /review
standard  = /review, /devils-advocate
qa        = /review, /devils-advocate, /qa-only
security  = /review, /devils-advocate, /cso
strict    = /review, /devils-advocate, /qa-only, /cso
```

Arbiter profiles expand separately:

```text
engineering = /plan-eng-review
product     = /plan-ceo-review
strict      = /plan-eng-review, /plan-ceo-review
```

Rationale: agent/model selection is an execution concern; persona selection is a review coverage concern. Keeping them separate lets the primary agent choose broader review viewpoints without reconfiguring installed agent credentials or model routing.

Alternative considered: store every profile as concrete `agent:/persona=model` entries. That would make profile behavior explicit but would duplicate agent configuration and make fallback behavior harder to reason about.

### 2. Review agents are fallback candidates

The review gate selects one effective review agent/model from the configured reviewer entries. All personas in the chosen reviewer profile run through that selected agent in parallel, each with its own packet and expected output path.

The first implementation can use the first configured reviewer entry as the selected agent. Later implementations can add health-based fallback if the selected agent fails before producing any reviewer artifacts.

Rationale: the user wants one agent to review the same plan from multiple perspectives. Running different personas on different agents would blur model-quality comparisons and make profile behavior depend on install ordering.

### 3. Reducer is mechanical

The deterministic reducer does not read reviewer prose or adjudicate findings. It only validates machine-readable artifacts and branches on verdict state:

```text
all required reviewer artifacts valid and verdict == PASS
  -> APPROVE, skip arbiter

any valid reviewer artifact verdict == CONCERNS or BLOCKED
  -> run selected arbiter profile

any reviewer artifact invalid
  -> retry that reviewer persona once before reducer decision
```

`CONCERNS` remains part of the reviewer verdict vocabulary. It means a reviewer found ambiguous risk that needs arbiter judgment. `BLOCKED` means the reviewer believes the proposal should not proceed without changes. Both states require arbitration.

Rationale: PASS-only approval is cheap and deterministic, while ambiguous or blocking findings are explicitly delegated to higher-quality arbiter personas.

### 4. Invalid reviewer artifacts get one corrective retry

When a reviewer artifact is missing, invalid JSON, schema-invalid, or semantically inconsistent, the gate retries the same selected agent/persona once. The retry packet includes:

- the previous validation errors,
- the required output path,
- the exact schema rules,
- a valid JSON example,
- an instruction that the previous artifact was rejected and must be rewritten.

The retry packet is executed through the normal job runner so the correction request appears in the delegate job log. If retry still fails, the reviewer persona is marked abandoned with validation error metadata.

Reducer behavior after abandonment:

- If all reviewer personas are abandoned, the review gate fails.
- If at least one valid reviewer exists and any valid reviewer has `CONCERNS` or `BLOCKED`, arbitration runs with abandoned reviewer metadata included.
- If all valid reviewers pass but at least one required reviewer was abandoned, arbitration runs so the arbiter can judge whether the missing persona weakens review confidence.

Rationale: format errors are recoverable once, but silently approving after a required persona was abandoned would weaken the review profile without visibility.

### 5. Canonical artifact helper

Add a Python module for artifact normalization and validation, for example `task_relay/review_artifacts.py`. It exposes functions similar to:

```python
write_reviewer_artifact(output_path: Path, payload: Mapping[str, object]) -> None
write_arbiter_artifact(output_path: Path, payload: Mapping[str, object]) -> None
validate_reviewer_artifact(payload: Mapping[str, object], persona: str | None = None) -> list[str]
validate_arbiter_artifact(payload: Mapping[str, object], persona: str | None = None) -> list[str]
```

The review and arbiter prompts instruct delegates to use the helper when possible. The gate must still validate artifacts after subprocess completion; the helper reduces format drift but is not the trust boundary.

Rationale: reviewer output is workflow input. A single canonical writer/validator keeps prompt instructions, retry diagnostics, tests, and gate enforcement aligned.

### 6. Persona-specific schema rules

Reviewer artifacts keep the existing verdicts:

```text
PASS | CONCERNS | BLOCKED
```

Common reviewer rules:

- `PASS` requires an empty `findings` array.
- `CONCERNS` or `BLOCKED` requires at least one finding or persona-specific concern field.
- every finding must include `severity`, `area`, `description`, and `recommendation`.

`/devils-advocate` must additionally provide:

- `fatal_flaw`,
- `simpler_alternative`,
- `reverse_case`.

Rationale: the existing schema remains backward compatible while the adversarial persona becomes enforceable.

### 7. Arbiter profiles are independent

The reviewer profile does not imply an arbiter profile. Defaults:

```text
reviewer profile = standard
arbiter profile = engineering
```

Product-heavy proposals can use `--arbiter-profile product`. Strict review can use `--arbiter-profile strict`. The chosen arbiter profile only executes when the reducer requires arbitration.

Rationale: review breadth and arbitration posture are separate decisions. A security-heavy proposal can still need engineering arbitration by default, while a scope-heavy proposal can explicitly choose product arbitration.

### 8. Overrides remain compatible

Existing `--reviewers` and `--arbiter` flags continue to work. When explicit reviewers are supplied, the gate treats them as manual persona/agent entries and records profile source as `manual_override`. When explicit arbiter entries are supplied, they override the selected arbiter profile but still run only when arbitration is required.

Rationale: existing scripts and managed block configurations remain valid while the new profile model becomes the preferred path.

## Risks / Trade-offs

- [Risk] Running multiple personas through the same selected agent can produce less independent reviewer diversity than multiple agents. Mitigation: make this behavior explicit and keep agent fallback separate from persona profile selection.
- [Risk] Skipping arbiters on clean PASS could miss subtle issues if reviewers are too optimistic. Mitigation: default `standard` includes `/devils-advocate`, and strict/QA/security profiles increase review persona coverage without forcing arbitration.
- [Risk] Abandoned reviewer personas can make review results less trustworthy. Mitigation: abandoned persona metadata forces arbitration unless every reviewer was abandoned, in which case the gate fails.
- [Risk] Delegates can ignore the artifact helper. Mitigation: the gate remains the final validator and retry mechanism; helper use improves reliability but is not required for trust.
- [Risk] Existing docs and skill guidance say arbiters always run. Mitigation: update docs, generated skill guidance, and summaries to describe PASS-only reducer approval and conditional arbitration.

## Migration Plan

1. Add profile and artifact helper code behind additive CLI flags.
2. Preserve existing `--reviewers` and `--arbiter` behavior.
3. Update generated skill guidance and docs after the gate supports conditional arbitration.
4. Validate with unit tests before using the new profile flags in normal review workflows.

Rollback is straightforward because the change is additive: callers can continue passing explicit `--reviewers` and `--arbiter` entries to use the legacy concrete-entry behavior.

