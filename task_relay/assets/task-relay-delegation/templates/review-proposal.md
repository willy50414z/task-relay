# Review Proposal Packet

Change: `<change-name>`
Mode: `review-proposal`
Objective: Review the proposal for requirement clarity, direction correctness,
and implementation plan completeness from an objective perspective.

## Context
- `openspec/changes/<change-name>/proposal.md`
- `openspec/changes/<change-name>/design.md`
- `openspec/changes/<change-name>/tasks.md`

## Review Checklist

### 1. Requirement Clarity
- Are the requirements clear, complete, and verifiable?
- Are there implicit assumptions not documented?
- Is the scope well-defined? What is in scope and what is out?

### 2. Direction Correctness
- From an objective perspective, is the solution direction reasonable?
- Is additional investigation of existing implementation or background needed?
- If needed, use gstack or other browser testing tools to validate existing behavior.

### 3. Implementation Plan Completeness
- Are the design decisions specific enough?
- Are the task steps granular enough? Are dependencies correct?
- Are there missing risks or edge cases?

### 4. User Intent
- If anything is unclear, ask the user rather than defining solutions independently.
- If there are alternative approaches worth considering, present them but let the user decide.

## Output
- Write review JSON to the unique path declared by the invoking CLI.
- Prefer the canonical helper when it is importable: `from task_relay.review_artifacts import write_reviewer_artifact`.
- If the helper is unavailable, still write exactly the same JSON shape yourself.
- Output JSON only. No prose before or after the JSON object.
- `PASS` requires an empty `findings` array.
- `CONCERNS` and `BLOCKED` require at least one finding or persona-specific concern field.
- Schema:

```json
{
  "reviewer": "agent:/persona",
  "verdict": "PASS | CONCERNS | BLOCKED",
  "summary": "short summary",
  "findings": [
    {
      "severity": "critical | high | medium | low",
      "area": "architecture | security | qa | scope | tests",
      "description": "problem statement",
      "recommendation": "concrete next step"
    }
  ]
}
```

For `/devils-advocate`, include these additional object fields:

```json
{
  "fatal_flaw": {
    "assumption": "the assumption that could invalidate the proposal",
    "why_fatal": "why this would break the proposal",
    "evidence_needed": "what must be checked",
    "status": "unverified | disproven | acceptable"
  },
  "simpler_alternative": {
    "description": "smallest viable alternative",
    "tradeoff": "what the simpler path loses",
    "recommendation": "adopt | consider | reject"
  },
  "reverse_case": {
    "opposite_approach": "what if the proposal did the opposite",
    "when_better": "conditions where the opposite wins",
    "risk": "risk of ignoring this case"
  }
}
```

## Non-goals
- Do not modify OpenSpec state or mark tasks.md checkboxes.
- Do not directly modify proposal.md / design.md / tasks.md.
- Do not perform destructive operations.
- Do not make architecture, security, credential, or migration decisions.
- Do not propose unrelated refactors.

## Timeout
- Default: 600 seconds
