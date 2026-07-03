# Proposal: Improve Propose Review Routing and Adversarial Review

## Summary

Enhance the propose-phase review workflow by adding deterministic review profiles, a dedicated adversarial reviewer persona, and clearer reviewer/arbiter routing rules.

The goal is to improve proposal review quality without requiring every change to run all reviewer and arbiter personas. The review system should treat personas as an available capability pool, not as a fixed always-on review chain.

## Problem

The current propose review workflow can run multiple reviewer personas and then use arbiter personas to produce a final decision. This provides strong review coverage, but it can become expensive when every proposal launches many delegated agents.

After adding a dedicated adversarial reviewer, the available persona pool becomes larger. Running all reviewers and arbiters for every proposal would cause excessive token usage, slower review cycles, and more noise for low-risk changes.

The current review proposal template already checks requirement clarity, direction correctness, implementation plan completeness, and user intent, but it does not force reviewers to explicitly challenge the proposal premise, identify fatal assumptions, or propose a smaller alternative.

## Goals

* Add deterministic review profiles for propose-phase review.
* Let the orchestration layer decide the review profile before launching reviewers.
* Add a dedicated Devil's Advocate reviewer persona for adversarial proposal review.
* Avoid random reviewer selection as the main review strategy.
* Avoid running all reviewer and arbiter personas for every proposal.
* Preserve existing explicit `--reviewers` and `--arbiter` override behavior.
* Keep arbiter execution conditional and compatible with the existing deterministic arbiter gating behavior.
* Improve review output by requiring explicit fatal assumption, simpler alternative, and reverse-case analysis.
* Record why a profile was selected and which personas were launched or skipped.

## Non-Goals

* Do not add implementation diff review in this change.
* Do not change apply-phase delegation behavior.
* Do not require every proposal to run CSO, QA, product arbiter, and engineering arbiter.
* Do not let delegated reviewers modify OpenSpec artifacts or task state.
* Do not make reviewer selection random by default.
* Do not replace existing deterministic arbiter gating if it already exists.

## Proposed Solution

Introduce a propose review router inside the review orchestration layer.

The router determines a review profile before reviewer execution. The selected profile determines:

* which reviewer personas to run,
* which arbiter persona is preferred if arbitration is needed,
* whether arbiter execution is required or conditional,
* and why this profile was selected.

Default behavior should be:

```text
profile = standard
reviewers = [/review, /devils-advocate]
arbiter = only if needed
```

This keeps normal proposal review to two reviewer agents in most cases, while still adding adversarial pressure.

## Review Profiles

### lite

For small, low-risk changes.

```text
reviewers:
  - /review

arbiter:
  - conditional only
```

### standard

Default for normal propose review.

```text
reviewers:
  - /review
  - /devils-advocate

arbiter:
  - conditional only
  - default preferred arbiter: /plan-eng-review
```

### qa

For changes involving user-facing behavior, acceptance criteria, regression risk, or verification plans.

```text
reviewers:
  - /review
  - /devils-advocate
  - /qa-only

arbiter:
  - conditional only
  - preferred arbiter: /plan-eng-review
```

### security

For changes involving secrets, credentials, permissions, sandboxing, CI/CD, supply chain, LLM tool authority, or trust boundaries.

```text
reviewers:
  - /review
  - /devils-advocate
  - /cso

arbiter:
  - conditional only
  - preferred arbiter: /plan-eng-review
```

### engineering

For changes involving architecture, migration, data flow, performance, concurrency, deployment behavior, or major implementation feasibility risk.

```text
reviewers:
  - /review
  - /devils-advocate
  - /qa-only

arbiter:
  - conditional only
  - preferred arbiter: /plan-eng-review
```

### product

For changes where product value, scope correctness, requirement completeness, or necessity is uncertain.

```text
reviewers:
  - /review
  - /devils-advocate

arbiter:
  - conditional only
  - preferred arbiter: /plan-ceo-review
```

### strict

For high-risk changes.

```text
reviewers:
  - /review
  - /devils-advocate
  - /qa-only
  - /cso

arbiter:
  - required or strongly preferred
  - default arbiter: /plan-eng-review
  - optional second arbiter: /plan-ceo-review if product/scope value is disputed
```

## Profile Selection Precedence

The router should select the profile using this precedence:

```text
1. Explicit CLI flag
   --profile lite|standard|qa|security|engineering|product|strict|auto

2. Existing explicit reviewer/arbiter override
   --reviewers and --arbiter continue to override automatic selection.

3. Change-level metadata if supported
   Example: review_profile: security

4. Auto router rules

5. Fallback default
   standard
```

## Auto Router Rules

The first version should use deterministic keyword and structural rules, not an extra LLM call.

Examples:

```text
If proposal/design/tasks/specs mention:
  auth, token, secret, credential, API key, sandbox, permission,
  supply chain, dependency, CI/CD, LLM tool authority, trust boundary
Then:
  profile = security

If they mention:
  acceptance criteria, regression, user-facing behavior, verification,
  test strategy, manual test, e2e, QA
Then:
  profile = qa

If they mention:
  migration, architecture, data flow, database schema, performance,
  concurrency, deployment, rollback, compatibility
Then:
  profile = engineering

If they mention:
  MVP, product value, user intent, scope expansion, alternative approach,
  over-design, requirement ambiguity
Then:
  profile = product

If any strict threshold is exceeded:
  profile = strict
```

Possible strict thresholds:

```text
- too many changed OpenSpec artifacts
- too many task items
- multiple capabilities/specs affected
- migration or security keywords plus unclear acceptance criteria
- proposal explicitly changes delegation authority or workflow state behavior
```

When multiple profiles match, choose the most conservative profile using this order:

```text
strict > security > engineering > qa > product > standard > lite
```

## New Reviewer Persona

Add a new persona:

```text
/devils-advocate
```

Purpose:

```text
Challenge whether the proposal should exist at all.
Attack hidden assumptions, over-design, unnecessary scope, fragile dependencies,
single points of failure, and missing simpler alternatives.
```

This reviewer should not check syntax, style, ordinary test coverage, or standard compliance. Those remain the responsibility of the existing reviewers.

## Review Proposal Output Enhancements

Extend review output with optional structured fields:

```json
{
  "reviewer": "agent:/persona",
  "verdict": "PASS | CONCERNS | BLOCKED",
  "summary": "short summary",
  "fatal_flaw": {
    "assumption": "the assumption that would invalidate the proposal",
    "why_fatal": "why this breaks the proposal",
    "evidence_needed": "what must be verified",
    "status": "unverified | refuted | accepted_risk"
  },
  "simpler_alternative": {
    "description": "smallest viable alternative",
    "tradeoff": "what it loses",
    "recommendation": "prefer | consider | reject"
  },
  "reverse_case": {
    "opposite_approach": "what if we do the opposite?",
    "when_better": "conditions where the opposite approach is better",
    "risk": "risk of ignoring it"
  },
  "findings": []
}
```

Backward compatibility:

* Existing reviewers may omit the new fields initially.
* `/devils-advocate` should always provide them.
* The arbiter and summary renderer should tolerate missing fields.

## Arbiter Policy

Do not make arbiter execution unconditional.

Keep or extend the existing deterministic arbiter gating behavior.

Arbiter should run when:

```text
- any reviewer returns BLOCKED
- any reviewer reports high or critical findings
- reviewer findings materially conflict
- /devils-advocate reports an unresolved fatal_flaw
- deterministic reducer cannot produce clear actionable items
- strict profile requires arbitration
```

Arbiter may be skipped when:

```text
- all reviewers PASS
- there are no high/critical findings
- there are no conflicts
- no fatal flaw is reported
- deterministic reducer can produce a clean APPROVE result
```

## Arbiter Risk Posture

When arbitration is needed, the arbiter should not blindly average reviewer opinions.

Add a risk-weighted rule:

```text
When reviewer findings conflict, prefer the most conservative finding if it is
evidence-supported or tied to irreversible risk, security risk, data loss,
migration risk, user-visible regression, or invalidated requirements.

If the pessimistic finding is plausible but not evidenced, convert it into a
required verification item instead of ignoring it.
```

## Review Result Metadata

The final review result should include routing metadata:

```json
{
  "selected_profile": "standard",
  "profile_reason": "default profile; no security/qa/strict triggers matched",
  "selected_reviewers": [
    "agent:/review",
    "agent:/devils-advocate"
  ],
  "skipped_reviewers": [
    {
      "reviewer": "agent:/cso",
      "reason": "no security-sensitive triggers matched"
    },
    {
      "reviewer": "agent:/qa-only",
      "reason": "no QA-specific triggers matched"
    }
  ],
  "arbiter_policy": "only_if_needed",
  "arbiter_invoked": false,
  "arbiter_skip_reason": "all reviewers passed without high/critical findings or conflicts"
}
```

## Expected Benefits

* Most normal proposals require only two reviewer agents.
* Low-risk proposals can run one reviewer.
* Security, QA, engineering, and product concerns still get specialized review when relevant.
* Review behavior becomes deterministic and reproducible.
* Token usage is controlled without weakening high-risk review coverage.
* Adversarial review becomes part of the default standard review without forcing all personas to run.

---

# Design: Propose Review Profile Router

## Current Context

The existing review workflow is a propose-phase gate that reviews OpenSpec artifacts before apply. Reviewers receive a `review-proposal` packet containing proposal/design/tasks/spec context, execute in parallel, and write reviewer JSON artifacts. Arbiters then read reviewer artifacts and produce an `APPROVE`, `REVISE`, or `REJECT` decision.

This change adds a routing layer before reviewer execution.

## Architecture

```text
trly review / trly review-gate
  -> load managed review config
  -> parse CLI overrides
  -> load OpenSpec change artifacts
  -> select review profile
  -> select reviewers
  -> generate review packets
  -> run reviewers in parallel
  -> deterministic reducer / existing arbiter gating
  -> optionally run arbiter
  -> write final review result
```

## Ownership

The review profile is decided by the orchestration layer.

```text
Responsible:
  - review-gate / router

Not responsible:
  - reviewer personas
  - arbiter personas
  - delegated agents
```

Reviewer personas only review. Arbiter personas only arbitrate. Workflow routing stays outside delegated agents.

## New Concepts

### ReviewProfile

Add a model similar to:

```python
class ReviewProfile(str, Enum):
    LITE = "lite"
    STANDARD = "standard"
    QA = "qa"
    SECURITY = "security"
    ENGINEERING = "engineering"
    PRODUCT = "product"
    STRICT = "strict"
    AUTO = "auto"
```

### ReviewProfilePlan

```python
@dataclass
class ReviewProfilePlan:
    selected_profile: str
    reason: str
    reviewers: list[str]
    preferred_arbiter: str | None
    arbiter_policy: str
    skipped_reviewers: list[SkippedReviewer]
    matched_triggers: list[str]
```

### ArbiterPolicy

```python
class ArbiterPolicy(str, Enum):
    NEVER = "never"
    ONLY_IF_NEEDED = "only_if_needed"
    REQUIRED = "required"
```

## CLI Changes

Add:

```bash
trly review --change <change> --profile auto
trly review-gate --change <change> --profile auto
```

Supported values:

```text
auto
lite
standard
qa
security
engineering
product
strict
```

Default:

```text
auto or standard
```

Recommended initial default:

```text
standard
```

Reason:

* safer and predictable for first release,
* no surprise router behavior,
* still only runs `/review + /devils-advocate`.

After auto router has tests and benchmarks, default can become `auto`.

## Override Rules

Existing explicit reviewer and arbiter flags should remain highest priority.

```text
If --reviewers is provided:
  use explicit reviewers
  profile metadata may still be recorded as "manual"

If --arbiter is provided:
  use explicit arbiter when arbitration is needed or required

If --profile is provided without --reviewers:
  select reviewers from profile

If neither --profile nor --reviewers is provided:
  use default profile
```

## Profile Mapping

```python
PROFILE_CONFIG = {
    "lite": {
        "reviewers": ["agent:/review"],
        "preferred_arbiter": "agent:/plan-eng-review",
        "arbiter_policy": "only_if_needed",
    },
    "standard": {
        "reviewers": ["agent:/review", "agent:/devils-advocate"],
        "preferred_arbiter": "agent:/plan-eng-review",
        "arbiter_policy": "only_if_needed",
    },
    "qa": {
        "reviewers": ["agent:/review", "agent:/devils-advocate", "agent:/qa-only"],
        "preferred_arbiter": "agent:/plan-eng-review",
        "arbiter_policy": "only_if_needed",
    },
    "security": {
        "reviewers": ["agent:/review", "agent:/devils-advocate", "agent:/cso"],
        "preferred_arbiter": "agent:/plan-eng-review",
        "arbiter_policy": "only_if_needed",
    },
    "engineering": {
        "reviewers": ["agent:/review", "agent:/devils-advocate", "agent:/qa-only"],
        "preferred_arbiter": "agent:/plan-eng-review",
        "arbiter_policy": "only_if_needed",
    },
    "product": {
        "reviewers": ["agent:/review", "agent:/devils-advocate"],
        "preferred_arbiter": "agent:/plan-ceo-review",
        "arbiter_policy": "only_if_needed",
    },
    "strict": {
        "reviewers": ["agent:/review", "agent:/devils-advocate", "agent:/qa-only", "agent:/cso"],
        "preferred_arbiter": "agent:/plan-eng-review",
        "arbiter_policy": "required",
    },
}
```

## Auto Router Design

The first version should be deterministic and rule-based.

Inputs:

```text
- proposal.md text
- design.md text
- tasks.md text
- specs/**/*.md text or selected sections
- optional change metadata
```

No extra LLM call is required.

### Trigger Categories

Security triggers:

```text
auth
token
secret
credential
api key
permission
sandbox
supply chain
dependency
ci/cd
github action
workflow
llm tool
mcp
agent authority
trust boundary
```

QA triggers:

```text
acceptance criteria
regression
user-facing
verification
test strategy
manual test
e2e
qa
rollback test
missing test
```

Engineering triggers:

```text
architecture
migration
data flow
database
schema
performance
concurrency
deployment
rollback
compatibility
state transition
distributed
cache
queue
```

Product triggers:

```text
scope
user intent
product value
mvp
alternative
over-design
requirement ambiguity
not necessary
simpler approach
```

Strict triggers:

```text
security trigger + migration trigger
security trigger + delegation authority change
multiple specs changed
large task count
proposal changes workflow state transition
proposal changes permission or sandbox behavior
unclear requirements plus high-risk implementation area
```

## Profile Resolution

If multiple categories match:

```text
strict > security > engineering > qa > product > standard > lite
```

The router should record:

```text
- matched triggers
- selected profile
- skipped profiles
- reason
```

## Devil's Advocate Persona Template

Add:

```md
# Reviewer Persona: /devils-advocate

Read-only adversarial proposal reviewer.

- Do not check syntax, formatting, style, or ordinary standard compliance.
- Challenge whether the proposal should exist at all.
- Attack hidden assumptions, unnecessary scope, premature abstraction, over-design,
  fragile dependencies, single points of failure, and missing simpler alternatives.
- Ask what assumption would invalidate the whole proposal if false.
- Ask what the smallest safer alternative is.
- Ask whether the opposite approach would be safer or cheaper.
- Report findings as structured JSON only.
- Do not modify project files, OpenSpec artifacts, or task state.
```

## Review Proposal Template Changes

Add adversarial fields to the output schema.

Required for `/devils-advocate`:

```text
fatal_flaw
simpler_alternative
reverse_case
```

Optional for other reviewers.

The summary renderer and arbiter should preserve these fields when present.

## Arbiter Template Changes

Add risk-weighted conflict handling:

```text
When resolving conflicts, prefer the conservative finding if it is evidence-supported
or tied to irreversible risk, security risk, data loss, migration risk, user-visible
regression, or invalidated requirements.

If the conservative finding is plausible but not evidenced, convert it into a
required verification item instead of ignoring it.
```

Add optional fields:

```json
{
  "risk_posture": "neutral | conservative | adversarial",
  "fatal_flaws": [
    {
      "source_reviewer": "agent:/devils-advocate",
      "assumption": "string",
      "arbiter_position": "accepted | rejected | needs_verification",
      "reason": "string"
    }
  ]
}
```

## Reducer / Arbiter Gating

Do not remove existing deterministic gating.

Extend it to understand new fields:

```text
If /devils-advocate fatal_flaw.status == "unverified":
  arbiter_needed = true

If any finding severity is high or critical:
  arbiter_needed = true

If any reviewer verdict is BLOCKED:
  arbiter_needed = true

If reviewer findings materially conflict:
  arbiter_needed = true

If profile arbiter_policy == required:
  arbiter_needed = true
```

Skip arbiter when safe:

```text
If all reviewers PASS
and no high/critical findings
and no unresolved fatal_flaw
and no conflicts
and profile arbiter_policy != required:
  skip arbiter
```

## Output Artifacts

Continue writing existing artifacts.

Add routing metadata to final review result JSON:

```json
{
  "review_profile": {
    "selected": "standard",
    "source": "explicit | auto | default | manual_override",
    "reason": "string",
    "matched_triggers": [],
    "selected_reviewers": [],
    "skipped_reviewers": [],
    "preferred_arbiter": "agent:/plan-eng-review",
    "arbiter_policy": "only_if_needed"
  }
}
```

Human-readable summary should include:

```text
Review profile: standard
Reviewers launched: /review, /devils-advocate
Reviewers skipped: /qa-only, /cso
Arbiter: skipped, all reviewers passed
```

## Backward Compatibility

* Existing `--reviewers` behavior remains valid.
* Existing `--arbiter` behavior remains valid.
* Existing reviewer JSON without adversarial fields remains valid.
* Existing managed block configuration remains valid.
* If `/devils-advocate` is not installed, standard profile should fail clearly or degrade to `/review` only depending on configuration.
* Default profile can initially be `standard` to avoid unexpected auto-router behavior.

## Failure Modes

### Missing persona

If a selected profile requires a reviewer that is unavailable:

```text
- fail clearly by default,
- include missing persona name,
- suggest installing or selecting a lower profile.
```

### Router cannot read change artifacts

Fallback:

```text
profile = standard
reason = "auto router failed to inspect artifacts; using standard fallback"
```

### Auto router over-selects strict

Acceptable in first version, but should be benchmarked.

### Too much reviewer noise

Arbiter should continue filtering duplicated or low-signal findings.

## Tests

Add tests for:

* profile selection by explicit CLI flag,
* profile fallback,
* manual reviewer override,
* auto security trigger,
* auto QA trigger,
* auto engineering trigger,
* auto product trigger,
* strict trigger precedence,
* missing persona behavior,
* arbiter skipped when all reviewers pass,
* arbiter invoked on unresolved fatal flaw,
* review result metadata.

---

# Tasks

## 1. Add Devil's Advocate persona

* [ ] Add `reviewer-devils-advocate.md`.
* [ ] Ensure persona is read-only.
* [ ] Ensure persona forbids syntax/style/ordinary compliance review.
* [ ] Ensure persona focuses on hidden assumptions, over-design, necessity, simpler alternatives, and reverse-case analysis.
* [ ] Include strict JSON-only output requirement.

## 2. Extend review proposal template

* [ ] Update `review-proposal.md` output schema.
* [ ] Add optional `fatal_flaw` field.
* [ ] Add optional `simpler_alternative` field.
* [ ] Add optional `reverse_case` field.
* [ ] Document that these fields are required for `/devils-advocate`.
* [ ] Preserve backward compatibility with existing reviewer outputs.

## 3. Add review profile model

* [ ] Add `ReviewProfile` enum.
* [ ] Add `ArbiterPolicy` enum.
* [ ] Add `ReviewProfilePlan` data structure.
* [ ] Add skipped reviewer metadata structure.
* [ ] Add profile-to-reviewer mapping.

## 4. Add CLI profile option

* [ ] Add `--profile` to `trly review`.
* [ ] Add `--profile` to `trly review-gate`.
* [ ] Support `lite`, `standard`, `qa`, `security`, `engineering`, `product`, `strict`, and `auto`.
* [ ] Preserve `--reviewers` override behavior.
* [ ] Preserve `--arbiter` override behavior.
* [ ] Record profile source as `explicit`, `auto`, `default`, or `manual_override`.

## 5. Implement deterministic review router

* [ ] Load proposal/design/tasks/spec text for routing.
* [ ] Implement security triggers.
* [ ] Implement QA triggers.
* [ ] Implement engineering triggers.
* [ ] Implement product triggers.
* [ ] Implement strict triggers.
* [ ] Implement profile precedence.
* [ ] Return selected profile, matched triggers, selected reviewers, skipped reviewers, preferred arbiter, and arbiter policy.
* [ ] Provide safe fallback to `standard` if routing fails.

## 6. Integrate router into review gate

* [ ] Run router before reviewer packet generation.
* [ ] Use selected reviewers when no explicit `--reviewers` override exists.
* [ ] Use preferred arbiter when no explicit `--arbiter` override exists.
* [ ] Include routing metadata in review result JSON.
* [ ] Include routing metadata in human-readable summary.

## 7. Extend deterministic arbiter gating

* [ ] Preserve current deterministic arbiter decision behavior.
* [ ] Add support for unresolved `fatal_flaw`.
* [ ] Add support for profile-level `arbiter_policy`.
* [ ] Invoke arbiter when strict profile requires it.
* [ ] Skip arbiter when all reviewers pass and no conflict/high-risk condition exists.
* [ ] Add clear skip reason to final result.

## 8. Update arbiter template

* [ ] Add risk-weighted conflict resolution rule.
* [ ] Add optional `risk_posture`.
* [ ] Add optional `fatal_flaws` adjudication field.
* [ ] Ensure arbiter still outputs JSON only.
* [ ] Ensure arbiter does not embed workflow/DAG logic.

## 9. Update install / managed configuration

* [ ] Ensure `/devils-advocate` can be installed with the skill bundle.
* [ ] Add review profile defaults to managed config if needed.
* [ ] Document how to override profile/reviewers/arbiter.
* [ ] Ensure legacy review-chain behavior remains compatible.

## 10. Add tests

* [ ] Test explicit `--profile standard`.
* [ ] Test explicit `--profile strict`.
* [ ] Test manual `--reviewers` override.
* [ ] Test manual `--arbiter` override.
* [ ] Test security auto-routing.
* [ ] Test QA auto-routing.
* [ ] Test engineering auto-routing.
* [ ] Test product auto-routing.
* [ ] Test strict precedence.
* [ ] Test missing `/devils-advocate` behavior.
* [ ] Test arbiter skipped on clean PASS.
* [ ] Test arbiter invoked on unresolved fatal flaw.
* [ ] Test review result includes routing metadata.
* [ ] Test human-readable summary includes profile and skip reasons.

## 11. Update documentation

* [ ] Document review profile concept.
* [ ] Document default profile.
* [ ] Document persona pool vs always-on review chain.
* [ ] Document why random reviewer selection is not the default.
* [ ] Document cost behavior:

  * lite: 1 reviewer
  * standard: 2 reviewers
  * issue case: 2 reviewers + optional arbiter
  * strict: 4 reviewers + arbiter
* [ ] Document recommended usage examples.

## 12. Validate on sample changes

* [ ] Run `lite` on a small documentation-only change.
* [ ] Run `standard` on a normal proposal.
* [ ] Run `security` on a permission/sandbox-related proposal.
* [ ] Run `qa` on a user-facing behavior proposal.
* [ ] Run `engineering` on a migration/data-flow proposal.
* [ ] Run `strict` on a high-risk delegation workflow proposal.
* [ ] Compare token usage and finding quality against the previous always-on reviewer chain.
