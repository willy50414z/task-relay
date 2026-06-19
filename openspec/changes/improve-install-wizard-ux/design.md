## Context

`interactive-install-wizard` introduced `trly install` as a guided flow, but the current implementation uses numbered `input()` prompts. That is technically interactive but does not match the keyboard-driven selection model users expect from `openspec init`, which uses Inquirer-style cursor prompts.

The current implementation also has state and path drift:

- `trly install` without flags does not reliably prefill from existing project/user managed blocks.
- Parsed model metadata is keyed by agent name while wizard state is keyed by role (`primary`, `sub`).
- Main-mode clear and uninstall do not consistently reuse the same path resolution as install.
- Packaged assets still use the legacy `openspec-deepseek-delegation` directory, so generated `task-relay-delegation` bundles can fall back to stub templates.
- Existing project installs can keep the old `.codex/skills/openspec-deepseek-delegation` bundle next to the new bundle.

## Goals / Non-Goals

**Goals:**
- Provide arrow-key navigation and Enter selection for the interactive installer.
- Keep non-interactive flag-based installs suitable for scripts and CI.
- Make prefill deterministic for existing user/project managed blocks.
- Use one path-resolution contract for install, clear, uninstall, and skill cleanup.
- Install complete `task-relay-delegation` skill assets and clean up legacy project skill bundles.
- Add tests that validate behavior without relying on a real terminal where possible.

**Non-Goals:**
- Rebuild `trly` in Node or directly depend on OpenSpec's JavaScript prompt implementation.
- Add network model discovery at install time.
- Support arbitrary third-party primary agents or sub-agents.
- Remove non-interactive install flags.
- Make uninstall delete unmanaged user content outside task-relay managed blocks and managed skill directories.

## Decisions

### D1: Introduce a prompt adapter boundary

Create a small prompt interface used by `run_wizard()`:

```python
class PromptAdapter(Protocol):
    def select(self, message: str, choices: list[Choice], default: str | None) -> str: ...
    def confirm(self, message: str, default: bool = True) -> bool: ...
```

The production adapter uses a Python prompt dependency such as `questionary` or `InquirerPy`. Tests use a fake adapter that returns queued choices, so unit tests do not require a TTY.

Rationale: this gives the user the desired keyboard experience while keeping wizard logic deterministic and easy to test. It also avoids embedding terminal key handling directly in business logic.

Alternative considered: hand-roll raw keypress handling with `msvcrt`/termios. Rejected because Windows and POSIX terminal differences would create avoidable maintenance risk.

### D2: Keep argparse as the non-interactive contract

`trly install --primary ... --scope ... --mode ...` remains the scriptable path and must not invoke a prompt. If stdin is not a TTY and required flags are missing, the command returns a clear error explaining which flags are required.

Rationale: CI behavior should be predictable. A prompt dependency should not be required to exercise non-interactive installs.

### D3: Resolve existing state before prompting

Before the first prompt, the CLI scans candidate guidance files for managed blocks:

```text
project: ./AGENTS.md, ./CLAUDE.md
user:    ~/.codex/AGENTS.md, ~/.claude/CLAUDE.md
```

If exactly one matching block is found, its primary, scope, mode, sub-agent, and models seed the wizard defaults. If more than one block is found, the wizard still starts with safe defaults, and the selected primary/scope determines which block is updated.

Parsed model metadata is normalized into role keys:

```text
primary model -> state.models["primary"]
sub model     -> state.models["sub"]
```

Rationale: re-running `trly install` should feel like editing the existing configuration, not starting over.

### D4: Make path resolution the single source of truth

All file and skill paths come from `resolve_install_paths(primary_agent, scope, cwd)`:

| Primary | Scope   | Guidance path              | Skill root             |
|---------|---------|----------------------------|------------------------|
| claude  | user    | `~/.claude/CLAUDE.md`      | `~/.claude/skills`     |
| claude  | project | `<cwd>/CLAUDE.md`          | `<cwd>/.claude/skills` |
| codex   | user    | `~/.codex/AGENTS.md`       | `~/.codex/skills`      |
| codex   | project | `<cwd>/AGENTS.md`          | `<cwd>/.codex/skills`  |

Install, main-mode clear, uninstall, and legacy cleanup must call this helper instead of deriving paths from `path.parent`.

### D5: Rename packaged assets and clean legacy bundles

Package assets should live under `task_relay/assets/task-relay-delegation/`. The installer copies templates and agent config from that directory, falling back only if packaged assets are unavailable.

On install, after writing the new `task-relay-delegation` bundle, the installer removes old `openspec-deepseek-delegation` bundles from the selected skill root. Uninstall removes the new bundle and also removes the legacy bundle from the same resolved root if present.

Rationale: stale skills confuse agent selection and fallback templates lose important safety instructions.

## Risks / Trade-offs

- New prompt dependency increases packaging surface -> keep it small, pinned through `pyproject.toml`, and isolate it behind the adapter.
- Prompt libraries can behave differently in CI -> never invoke the prompt adapter when non-interactive flags are complete; return explicit errors for incomplete non-TTY installs.
- Auto-detecting multiple existing blocks can be ambiguous -> prefill only when unambiguous; otherwise use defaults and update the selected primary/scope target.
- Cleaning legacy bundles could remove a user-modified legacy skill -> limit cleanup to the managed legacy skill directory name under the selected task-relay skill root.

## Migration Plan

1. Add the prompt adapter and production select/confirm implementation.
2. Rewrite wizard step functions to call the adapter instead of `_prompt_numbered()` and `input()`.
3. Normalize existing managed block parsing into role-keyed model defaults.
4. Centralize clear/uninstall path handling around `resolve_install_paths()`.
5. Rename package assets and update package-data expectations.
6. Add cleanup of legacy `openspec-deepseek-delegation` bundles in selected roots.
7. Run unit tests plus manual smoke tests for project install, re-run prefill, main clear, and uninstall.

Rollback: keep non-interactive install code path independent from the prompt adapter, so a prompt regression can be isolated by temporarily disabling prompt-mode invocation while preserving scripted installs.
