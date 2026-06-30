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
- Output JSON only. No prose before or after the JSON object.
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

## Non-goals
- Do not modify OpenSpec state or mark tasks.md checkboxes.
- Do not directly modify proposal.md / design.md / tasks.md.
- Do not perform destructive operations.
- Do not make architecture, security, credential, or migration decisions.
- Do not propose unrelated refactors.

## Timeout
- Default: 600 seconds
