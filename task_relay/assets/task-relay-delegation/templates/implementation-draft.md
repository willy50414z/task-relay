# Implementation Draft Packet

Task id: `<task-id>`
Mode: `implementation-draft`
Objective: `<describe the bounded implementation draft>`
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
- Do not make architecture, security, credential, or migration decisions.
Expected output:
- Patch draft or file-by-file edit plan for Codex review.
- Call out any ambiguity that prevents a safe draft.
Verification command:
- `<command>`
Timeout guidance:
- Default to 600 seconds.
