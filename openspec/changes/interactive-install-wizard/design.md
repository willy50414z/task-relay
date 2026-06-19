## Context

The current `trly install` takes CLI flags (`--mode`, `--level`, `--yes`, `--cwd`) and writes a hardcoded deepseek delegation block into `AGENTS.md`. It assumes codex is the primary agent, deepseek is the sub-agent, and only supports project scope.

The redesign replaces this with an interactive wizard that guides the user through primary agent, scope, mode, sub-agent, and model selection — producing guidance files and skill bundles appropriate to the chosen primary agent (Claude or Codex) at user or project scope.

## Goals / Non-Goals

**Goals:**
- Interactive terminal wizard with clear, sequential prompts
- Support both Claude and Codex as primary orchestration agents
- Support user-level (`~/.claude/`, `~/.codex/`) and project-level (`./`) scope
- Dynamic generation of managed guidance blocks and skill bundles
- Hardcoded model catalog with automated update workflow
- Mode `main` clears existing delegation block and exits
- `trly uninstall` auto-detects primary agent from existing managed block

**Non-Goals:**
- GUI or web-based installer
- Network-dependent model discovery at install time
- Plugin/third-party agent support beyond claude/codex/deepseek
- Async or background installation
- Config file (`config.yml`) — all configuration lives in managed blocks

## Decisions

### D1: Sequential prompt state machine with explicit WizardState

A `WizardState` dataclass accumulates user choices across steps. Each step is a pure function taking state and returning updated state. This keeps the flow testable and the steps composable.

```
WizardState
  primary_agent: "claude" | "codex" | None
  scope: "user" | "project" | None
  mode: "main" | "hybrid" | "delegated-apply" | None
  sub_agent: "claude" | "codex" | "deepseek" | None
  models: dict[str, str]    # agent_name → model_id
  cwd: Path
```

The runner orchestrates steps and handles Ctrl-C / EOF gracefully.

### D2: Path resolution table

A single function `resolve_install_paths(primary, scope, cwd) → (guidance_path, skill_root)`:

| Primary | Scope   | Guidance file              | Skill path               |
|---------|---------|----------------------------|--------------------------|
| claude  | user    | `~/.claude/CLAUDE.md`      | `~/.claude/skills/`      |
| claude  | project | `./CLAUDE.md`              | `./.claude/skills/`      |
| codex   | user    | `~/.codex/AGENTS.md`       | `~/.codex/skills/`       |
| codex   | project | `./AGENTS.md`              | `./.codex/skills/`       |

User home directories resolved via `Path.home()`.

### D3: Managed block format (consistent across primary agents)

```
<!-- task-relay:start -->
## Task Relay Delegation
- primary: <claude|codex>
- mode: <main|hybrid|delegated-apply>
- sub-agent: <claude|codex|deepseek>
- models:
  - <agent>: <model_id>
<!-- task-relay:end -->
```

Policy instructions follow the metadata, generated from a template keyed on `(primary, mode, sub_agent)`. The format is consistent regardless of whether the file is `CLAUDE.md` or `AGENTS.md`.

Block markers renamed from `task-relay:openspec-delegation:start/end` to `task-relay:start/end` for brevity.

### D4: Skill bundle structure (generalized)

```
skills/task-relay-delegation/
├── SKILL.md                       ← dynamic from template
├── agents/
│   └── <sub_agent>.yaml           ← dynamic, one file per sub-agent
└── templates/
    ├── implementation-draft.md
    ├── test-draft.md
    ├── review.md
    └── diagnosis.md
```

- `SKILL.md` is generated from a template with `{primary}`, `{sub_agent}`, `{model}` placeholders
- `agents/<sub_agent>.yaml` is selected from bundled agent configs (openai.yaml for codex, etc.)
- Templates are static and unchanged from current implementation

The skill is always named `task-relay-delegation` regardless of sub-agent choice.

### D5: Model catalog module

`task_relay/models.py` — a single source of truth for available models:

```python
@dataclass
class ModelInfo:
    id: str
    name: str
    tier: str         # "high", "medium", "fast"
    provider: str     # "anthropic", "openai", "deepseek"

CLAUDE_MODELS: list[ModelInfo] = [...]
CODEX_MODELS: list[ModelInfo] = [...]
DEEPSEEK_MODELS: list[ModelInfo] = [ModelInfo(id="deepseek-v4-pro[1m]", ...)]
```

Display helpers format models for terminal prompts:
```
Claude models:
  [1] claude-opus-4-8 — Opus 4.8 (highest reasoning)
  [2] claude-sonnet-4-6 — Sonnet 4.6 (balanced)
  [3] claude-haiku-4-5-20251001 — Haiku 4.5 (fast)
  [4] claude-fable-5 — Fable 5
```

### D6: GitHub Action for model catalog updates

A scheduled workflow (weekly) that:
1. Fetches model lists from Anthropic and OpenAI APIs
2. Compares against `task_relay/models.py`
3. If changes detected, creates a PR with the diff
4. Labels the PR as `model-update`

Runs on `schedule` and `workflow_dispatch`.

### D7: Uninstall detection

`trly uninstall` scans for the managed block marker (`<!-- task-relay:start -->`) in:
- `./CLAUDE.md` / `./AGENTS.md` (project scope, cwd)
- `~/.claude/CLAUDE.md` / `~/.codex/AGENTS.md` (user scope)

If no `--scope` flag, uninstall checks both. If `--scope user`, only checks user paths. If `--scope project`, only checks project paths.

Parsing the `primary:` line from the managed block determines which skill directory to clean up. If the managed block is malformed or primary can't be parsed, the uninstaller warns and skips skill cleanup.

## Risks / Trade-offs

- **Interactive-only means no scriptability** → Mitigation: Accept `--primary`, `--scope`, `--mode`, `--sub-agent`, `--model` as non-interactive flags that skip the wizard. Interactive mode only when no flags provided.
- **Model catalog staleness between GitHub Actions runs** → Mitigation: Weekly updates catch most new models. Manual `workflow_dispatch` trigger for urgent updates.
- **CLAUDE.md may conflict with existing CLAUDE.md conventions** → Mitigation: Managed block is additive; existing CLAUDE.md content is preserved outside the block.
- **Removing config.yml** → Mitigation: All existing config.yml data (model defaults) is now in the managed block. Config.yml was new in v0.2 with likely zero real-world adoption yet.
- **Breaking change to install flags** → Mitigation: `trly install` with no flags starts the wizard. Old flags (`--mode`, `--level`, `--cwd`) print a migration message pointing to the new wizard.

## Open Questions

- Should the wizard support re-running to change individual settings (e.g., just the model) without re-entering everything? Tentative: yes, pre-fill state from existing managed block.
- Should `trly uninstall` require a `--scope` flag or auto-detect? Tentative: auto-detect both scopes unless `--scope` is explicit.
