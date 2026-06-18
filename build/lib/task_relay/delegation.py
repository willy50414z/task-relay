from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import shutil

MANAGED_BLOCK_START = "<!-- task-relay:openspec-delegation:start -->"
MANAGED_BLOCK_END = "<!-- task-relay:openspec-delegation:end -->"
DEFAULT_GUIDANCE_FILE = "AGENTS.md"
SKILL_NAME = "openspec-deepseek-delegation"
VALID_MODES = ("main", "hybrid", "delegated-apply")


@dataclass(frozen=True)
class DelegationInstallResult:
    path: Path
    mode: str | None
    action: str


def install_project_guidance(project_dir: str | Path, mode: str) -> DelegationInstallResult:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {', '.join(VALID_MODES)}")

    project_path = Path(project_dir).resolve()
    guidance_path = project_path / DEFAULT_GUIDANCE_FILE
    existing = guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else ""
    block = build_guidance_block(mode)

    if MANAGED_BLOCK_START in existing or MANAGED_BLOCK_END in existing:
        updated = _replace_managed_block(existing, block)
        action = "updated"
    else:
        prefix = existing.rstrip()
        if prefix:
            updated = f"{prefix}\n\n{block}\n"
            action = "appended"
        else:
            updated = f"# Agent Guidance\n\n{block}\n"
            action = "created"

    guidance_path.write_text(updated, encoding="utf-8")
    _install_skill_bundle(project_path, mode)
    return DelegationInstallResult(path=guidance_path, mode=mode, action=action)


def uninstall_project_guidance(project_dir: str | Path) -> DelegationInstallResult:
    project_path = Path(project_dir).resolve()
    guidance_path = project_path / DEFAULT_GUIDANCE_FILE
    if not guidance_path.exists():
        _remove_skill_bundle(project_path)
        return DelegationInstallResult(path=guidance_path, mode=None, action="not-installed")

    existing = guidance_path.read_text(encoding="utf-8")
    if MANAGED_BLOCK_START not in existing and MANAGED_BLOCK_END not in existing:
        _remove_skill_bundle(project_path)
        return DelegationInstallResult(path=guidance_path, mode=None, action="not-installed")

    updated = _replace_managed_block(existing, "").strip()
    if updated:
        guidance_path.write_text(f"{updated}\n", encoding="utf-8")
    else:
        guidance_path.unlink()

    _remove_skill_bundle(project_path)
    return DelegationInstallResult(path=guidance_path, mode=None, action="removed")


def build_guidance_block(mode: str) -> str:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {', '.join(VALID_MODES)}")

    return "\n".join(
        [
            MANAGED_BLOCK_START,
            "## OpenSpec Delegation Policy",
            "",
            _mode_header(mode),
            "",
            _mode_policy(mode),
            "",
            "When working on OpenSpec propose/apply tasks under a delegation-enabled mode:",
            "- During propose, use lightweight task tags in `tasks.md`:",
            "  `[delegate:deepseek]`, `[delegate:test]`, `[delegate:review]`,",
            "  `[delegate:optional]`, and `[codex-only]`.",
            "- During apply, inspect the current task tag before implementation.",
            "  `[codex-only]` stays in Codex. `[delegate:deepseek]` routes to",
            "  implementation drafts. `[delegate:test]` routes to test drafts.",
            "  `[delegate:review]` routes to review or failure diagnosis.",
            "  `[delegate:optional]` is delegated when the prompt packet is small.",
            "- Use lower-cost submodels only for bounded, low-risk, verifiable draft work.",
            "- Keep architecture, security, migrations, credentials, destructive operations,",
            "  and OpenSpec state changes in Codex unless the user explicitly says otherwise.",
            "- Build minimal delegation prompt packets: task text, relevant artifact excerpts,",
            "  relevant file excerpts, expected output format, and verification commands.",
            "- Use these output modes for prompt packets: `implementation-draft` returns a",
            "  patch or file-by-file edit plan; `test-draft` returns tests to add and run;",
            "  `review` returns findings against the diff/spec; `diagnosis` returns likely",
            "  root cause and next fix for a failing command.",
            "- Use `trly run --target deepseek --prompt-file <packet>` for delegated",
            "  draft/review/diagnosis work unless a task packet names another target or",
            "  DeepSeek is unavailable.",
            "- Submodels must not change OpenSpec scope or mark `tasks.md` checkboxes complete.",
            "- Codex reviews delegated output, integrates changes, runs final verification,",
            "  and is the only actor that marks OpenSpec tasks complete.",
            "- If delegated output is unavailable, malformed, too broad, stale, or inconsistent,",
            "  Codex takes over after one unusable attempt unless the failure is mechanical.",
            "- Record delegation decisions or overrides near the relevant task in `tasks.md`",
            "  when the workflow uses delegated draft work.",
            "",
            "Propose-time task packets for submodel delegation:",
            "- Split delegate-friendly work into standalone tasks with enough local context",
            "  that a submodel can avoid reading all OpenSpec artifacts.",
            "- Use multi-line task entries for submodel-eligible work:",
            "  ```md",
            "  - [ ] 2.2 [delegate:test] Add CLI tests for `--mode hybrid`",
            "    - context: `tests/test_cli.py`, `task_relay/delegation.py`",
            "    - output: focused tests for install/update behavior",
            "    - verify: `pytest tests/test_cli.py`",
            "  ```",
            "- The `context` field lists the minimal files or artifacts the submodel must read.",
            "- The `output` field describes what the submodel should produce.",
            "- The `verify` field gives the command or check that confirms the output is usable.",
            "- Keep the checkbox line in the standard `- [ ]` format so OpenSpec task parsing",
            "  remains intact. Put packet fields as indented notes under the checkbox.",
            "- Use multi-line packets only when they reduce submodel context load. Simple",
            "  `[codex-only]` or trivial tasks can remain one-line checkboxes.",
            "",
            "The compatibility command `agent-dispatch` is deprecated and planned for removal in v0.3.0.",
            MANAGED_BLOCK_END,
        ]
    )


def _mode_header(mode: str) -> str:
    if mode == "main":
        return "Delegation mode: main - no automatic submodel delegation."
    if mode == "hybrid":
        return "Delegation mode: hybrid - propose-time task routing plus delegation-first apply for tagged work."
    return "Delegation mode: delegated-apply - main model delegates apply implementation to a submodel and verifies completion."


def _mode_policy(mode: str) -> str:
    if mode == "main":
        return "\n".join(
            [
                "Mode A / main: all OpenSpec apply work remains with the main model.",
                "Do not delegate any apply tasks to submodels unless the user explicitly",
                "asks for it on a specific task. This mode keeps all context in the main",
                "session and disables automatic delegation.",
            ]
        )

    if mode == "hybrid":
        return "\n".join(
            [
                "Mode B / hybrid: the recommended delegation-first cost-control default.",
                "",
                "Main model owns:",
                "- OpenSpec artifact interpretation, scope, and architecture decisions.",
                "- Architecture, security, data migration, destructive operations,",
                "  credentials, and other high-risk decisions.",
                "- Integration of delegated output into the working tree.",
                "- Large feature acceptance and final tests.",
                "- `tasks.md` checkbox updates and OpenSpec state changes.",
                "",
                "Hybrid mandatory delegation rules:",
                "- During OpenSpec propose, Codex MUST assign delegate-friendly implementation,",
                "  test, review, documentation extraction, repetitive edit, and diagnosis work",
                "  to standalone delegate task packets.",
                "- Delegate-friendly means bounded file scope, clear expected output, and an",
                "  independently verifiable command or review check.",
                "- During apply, Codex MUST attempt delegation for every `[delegate:deepseek]`,",
                "  `[delegate:test]`, and `[delegate:review]` task before implementing it directly.",
                "- Do not skip a tagged delegate task merely because it is small, trivial, or",
                "  faster for Codex to do directly.",
                "- Codex may skip or take over only when the task is high-risk, needs broad repo",
                "  context, the delegation backend is unavailable, or one delegated attempt",
                "  returns unusable output.",
                "- Record the concrete skip/takeover reason near the relevant task in `tasks.md`.",
                "- During apply, split each OpenSpec change into the smallest practical work",
                "  packets before acting: implementation, test authoring, test execution,",
                "  verification, and diagnosis. Keep the integration step in Codex, but delegate",
                "  bounded draft work whenever a task can be verified from a file, test, or log.",
                "- If a task can be proven by a focused test or command output, prefer having",
                "  Codex write the test or command description and letting a submodel execute or",
                "  inspect the result when that reduces context load.",
                "- When a delegated task needs verification, have the submodel return either a",
                "  concise patch plan, a test plan, or a log/output summary. Codex then reviews",
                "  the result, integrates the changes, and performs the final acceptance check.",
                "",
                "Submodels are assigned:",
                "- Implementation drafts with clear file scope.",
                "- Small-scope tests and test suggestions.",
                "- Documentation reading, extraction, and summaries.",
                "- Repetitive edits.",
                "- Failure diagnosis.",
                "- First-pass diff/spec review.",
            ]
        )

    return "\n".join(
        [
            "Mode C / delegated-apply: full delegated apply with main-model verification.",
            "",
            "The main model packages the apply request and delegates implementation to",
            "a submodel. The submodel may produce a patch or implementation report for",
            "the full eligible apply scope.",
            "",
            "The main model must:",
            "- Verify that tasks, tests, and spec alignment are complete before marking",
            "  tasks complete.",
            "- Take over if delegated output is incomplete, unsafe, too broad, or",
            "  unverifiable.",
            "- Not let submodels mark `tasks.md` checkboxes complete.",
        ]
    )


def _replace_managed_block(text: str, replacement: str) -> str:
    start = text.find(MANAGED_BLOCK_START)
    end = text.find(MANAGED_BLOCK_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("managed OpenSpec delegation block is malformed")

    end += len(MANAGED_BLOCK_END)
    prefix = text[:start].rstrip()
    suffix = text[end:].lstrip()
    parts = [part for part in (prefix, replacement.strip(), suffix) if part]
    return "\n\n".join(parts) + ("\n" if parts else "")


def _install_skill_bundle(project_path: Path, mode: str) -> None:
    if mode not in {"hybrid", "delegated-apply"}:
        return

    skill_root = project_path / ".codex" / "skills" / SKILL_NAME
    if skill_root.exists():
        shutil.rmtree(skill_root)
    skill_root.mkdir(parents=True, exist_ok=True)

    asset_root = resources.files("task_relay.assets").joinpath(SKILL_NAME)
    for relative_path in (
        "SKILL.md",
        "agents/openai.yaml",
        "templates/implementation-draft.md",
        "templates/test-draft.md",
        "templates/review.md",
        "templates/diagnosis.md",
    ):
        target_path = skill_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_file = asset_root.joinpath(relative_path)
        target_path.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")


def _remove_skill_bundle(project_path: Path) -> None:
    skill_root = project_path / ".codex" / "skills" / SKILL_NAME
    if skill_root.exists():
        shutil.rmtree(skill_root)
