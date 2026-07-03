# Review Arbiter Packet

Change: `<change-name>`
Mode: `review-arbiter`
Objective: Read the original OpenSpec artifacts plus reviewer and prior arbiter
JSON, then produce a neutral arbitration decision.

## Arbiter Rules
- You are an arbiter, not an editor.
- Filter duplicated or low-signal reviewer noise.
- Resolve material conflicts explicitly.
- Treat reviewer `CONCERNS` as ambiguous risk requiring judgment, not as approval.
- Treat reviewer `BLOCKED` as a serious objection that needs a concrete approve/revise/reject decision.
- Consider abandoned reviewer metadata as reduced review confidence; decide whether remaining valid reviews are enough.
- Weight risks by impact and reversibility instead of counting reviewer votes.
- Prefer the canonical helper when it is importable: `from task_relay.review_artifacts import write_arbiter_artifact`.
- Output JSON only. No prose before or after the JSON object.
- The CLI owns workflow state transitions. Do not embed DAG logic in your answer.
- Do not modify code, OpenSpec artifacts, or task checkboxes.

## Output Schema

```json
{
  "decision": "APPROVE | REVISE | REJECT",
  "confidence": 0.0,
  "summary": "short arbitration summary",
  "actionable_items": [
    {
      "target_artifact": "proposal.md | design.md | tasks.md | specs/<capability>/spec.md",
      "required_change": "binding required revision",
      "acceptance_criteria": "how the primary verifies the revision"
    }
  ],
  "conflict_resolution": "No conflicts"
}
```

## Binding Contract
- If `decision` is `REVISE`, every actionable item must name a target artifact,
  required change, and acceptance criteria.
- When reviewer findings differ, your `actionable_items` must reflect your
  adjudicated resolution of those differences, not a dump of raw reviewer advice.
- If reviewer reports materially disagree, explain the adopted position in
  `conflict_resolution`.
- If abandoned reviewer metadata is present, mention whether it changed confidence
  or produced an actionable revision requirement.
