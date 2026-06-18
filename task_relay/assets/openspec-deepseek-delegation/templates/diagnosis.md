# Diagnosis Packet

Task id: `<task-id>`
Mode: `diagnosis`
Objective: `<describe the failing command or artifact to diagnose>`
Context files:
- `<path>`
- `<path>`
Allowed direct reads:
- `tasks.md` - read task `<task-id>` only
- `design.md` - read section `<section-heading>`
- `openspec/.../spec.md` - read section `<section-heading>`
- `<log-path>` - read only the failing command output
Non-goals:
- Do not update OpenSpec scope.
- Do not mark `tasks.md` checkboxes.
- Do not perform destructive operations.
- Do not change production files directly.
- Do not make architecture, security, credential, or migration decisions.
Expected output:
- Likely root cause, supporting evidence, and the next safe fix for Codex to apply.
- Mention any competing hypotheses briefly when the failure is ambiguous.
Verification command:
- `<command>`
Timeout guidance:
- Default to 180 seconds.
