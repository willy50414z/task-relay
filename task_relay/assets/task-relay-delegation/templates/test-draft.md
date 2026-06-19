# Test Draft Packet

Task id: `<task-id>`
Mode: `test-draft`
Objective: `<describe the focused test or validation coverage>`
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
- Do not change production behavior beyond what tests need to reference.
- Do not make architecture, security, credential, or migration decisions.
Expected output:
- Focused tests to add or a validation-check plan with assertions and run command.
- Keep the draft limited to the named files.
Verification command:
- `<command>`
Timeout guidance:
- Default to 300 seconds.
