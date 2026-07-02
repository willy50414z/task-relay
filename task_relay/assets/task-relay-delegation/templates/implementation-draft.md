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

Conventions (MUST follow):
- For DB, serialization, framework-specific, or repo-specific code, follow the
  existing idiom from exemplar files listed in `Context files` or provided via
  `--read`. Do not invent a new idiom.
- If a convention-sensitive area has no matching exemplar, stop and call out
  the ambiguity instead of guessing.
- If `.task_relay/conventions.md` is included in the packet, its rules are
  mandatory. If they conflict with your default habits, follow that file.

Expected output:
- Patch draft or file-by-file edit plan for Codex review.
- Call out any ambiguity that prevents a safe draft.
Verification command:
- `<command>`
Timeout guidance:
- Default to 600 seconds.
