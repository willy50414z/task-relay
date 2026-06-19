# Review Packet

Task id: `<task-id>`
Mode: `review`
Objective: `<describe the diff/spec review goal>`
Context files:
- `<path>`
- `<path>`
Allowed direct reads:
- `tasks.md` - read task `<task-id>` only
- `design.md` - read section `<section-heading>`
- `openspec/.../spec.md` - read section `<section-heading>`
Non-goals:
- Do not update OpenSpec scope.
- Do not mark `tasks.md` checkboxes.
- Do not perform destructive operations.
- Do not directly change files.
- Do not make architecture, security, credential, or migration decisions.
- Do not propose unrelated refactors.
Expected output:
- Findings ordered by severity with file or section references.
- Focus on policy drift, unsafe delegation authority, missing failure modes, or spec mismatch.
Verification command:
- `<command>`
Timeout guidance:
- Default to 300 seconds.
