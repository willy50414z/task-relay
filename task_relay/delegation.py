"""Path resolution, managed block generation, and skill bundle management."""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import shutil

# ── Marker constants ──────────────────────────────────────────────

MANAGED_BLOCK_START = "<!-- task-relay:start -->"
MANAGED_BLOCK_END = "<!-- task-relay:end -->"
LEGACY_BLOCK_START = "<!-- task-relay:openspec-delegation:start -->"
LEGACY_BLOCK_END = "<!-- task-relay:openspec-delegation:end -->"

SKILL_NAME = "task-relay-delegation"
LEGACY_SKILL_NAME = "openspec-deepseek-delegation"

# Primary agent → guidance file name
_GUIDANCE_FILE: dict[str, str] = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
}

# Primary agent → skill dir relative to scope root
_SKILL_DIR: dict[str, str] = {
    "claude": ".claude/skills",
    "codex": ".codex/skills",
}


# ── Public types ───────────────────────────────────────────────────

@dataclass(frozen=True)
class InstallResult:
    guidance_path: Path
    primary_agent: str
    scope: str
    mode: str | None
    sub_agent: str | None
    action: str  # "created", "updated", "cleared", "removed", "not-installed"


# ── Path resolution (Group 3) ─────────────────────────────────────

def resolve_install_paths(
    primary_agent: str, scope: str, cwd: str | Path | None = None
) -> tuple[Path, Path]:
    """Return (guidance_path, skill_root) for the given primary agent and scope."""
    project_root = Path(cwd).resolve() if cwd else Path.cwd()
    guidance_file = _GUIDANCE_FILE.get(primary_agent, "AGENTS.md")
    skill_subdir = _SKILL_DIR.get(primary_agent, ".codex/skills")

    if scope == "user":
        base = Path.home() / f".{primary_agent}"
        guidance_path = base / guidance_file
        skill_root = Path.home() / skill_subdir
    else:
        guidance_path = project_root / guidance_file
        skill_root = project_root / skill_subdir

    return guidance_path, skill_root


def detect_managed_blocks(cwd: str | Path | None = None) -> dict[str, list[Path]]:
    """Scan user and project paths for files containing a task-relay managed block.

    Returns dict mapping scope ("user" | "project") to list of matching paths.
    """
    found: dict[str, list[Path]] = {"user": [], "project": []}

    project_root = Path(cwd).resolve() if cwd else Path.cwd()
    for agent in _GUIDANCE_FILE:
        for scope in ("user", "project"):
            path, _ = resolve_install_paths(agent, scope, project_root)
            if _has_managed_block(path):
                found[scope].append(path)

    return found


def _has_managed_block(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
        return (MANAGED_BLOCK_START in text and MANAGED_BLOCK_END in text) or (
            LEGACY_BLOCK_START in text and LEGACY_BLOCK_END in text
        )
    except Exception:
        return False


# ── Managed block generation (Group 4) ─────────────────────────────

def build_guidance_block(
    primary_agent: str,
    mode: str,
    sub_agent: str,
    models: dict[str, str],
    scope: str,
) -> str:
    """Generate a dynamic managed guidance block from wizard state."""
    primary_model = models.get("primary", "")
    sub_model = models.get("sub", "")

    lines = [
        MANAGED_BLOCK_START,
        "## Task Relay Delegation",
        "",
        f"- primary: {primary_agent}",
        f"- mode: {mode}",
        f"- sub-agent: {sub_agent}",
        f"- scope: {scope}",
        f"- models:",
    ]
    if primary_model:
        lines.append(f"  - {primary_agent}: {primary_model}")
    if sub_agent != primary_agent and sub_model:
        lines.append(f"  - {sub_agent}: {sub_model}")
    elif sub_agent == primary_agent and sub_model:
        # Same agent for both roles, list both models
        lines.append(f"  - {primary_agent} (primary): {primary_model}")
        lines.append(f"  - {sub_agent} (sub): {sub_model}")

    lines.append("")
    lines.append(_mode_header(mode, primary_agent, sub_agent))
    lines.append("")
    lines.extend(_mode_policy(mode, primary_agent, sub_agent))
    lines.append("")
    lines.append(MANAGED_BLOCK_END)

    return "\n".join(lines)


def _mode_header(mode: str, primary_agent: str, sub_agent: str) -> str:
    if mode == "main":
        return f"Delegation mode: main — all work stays with {primary_agent}."
    if mode == "hybrid":
        return f"Delegation mode: hybrid — {primary_agent} orchestrates, {sub_agent} handles bounded delegated work."
    return f"Delegation mode: delegated-apply — {primary_agent} delegates full apply to {sub_agent} and verifies completion."


def _mode_policy(mode: str, primary_agent: str, sub_agent: str) -> list[str]:
    if mode == "main":
        return [
            "All work remains with the primary model. No automatic delegation.",
        ]

    if mode == "hybrid":
        return [
            f"Primary model ({primary_agent}) owns:",
            "- Architecture, security, data migration, destructive operations, credentials.",
            "- OpenSpec artifact interpretation, scope, and state changes.",
            "- Integration of delegated output and final verification.",
            "",
            f"Sub-agent ({sub_agent}) handles:",
            "- Bounded implementation drafts with clear file scope.",
            "- Small-scope tests and test suggestions.",
            "- Documentation extraction and summaries.",
            "- Repetitive edits.",
            "- Failure diagnosis and first-pass review.",
            "",
            "Propose-time task tags for delegation:",
            f"- `[delegate:{sub_agent}]` — route implementation to sub-agent.",
            "- `[delegate:test]` — route test authoring.",
            "- `[delegate:review]` — route review/diagnosis.",
            "- `[delegate:optional]` — delegate when prompt packet is small.",
            f"- `[{primary_agent}-only]` — keep in primary agent.",
            "",
            f"Use `trly run --target {sub_agent} --prompt-file <packet>` for delegated work.",
        ]

    return [
        f"Primary model ({primary_agent}) packages the apply request and delegates",
        f"implementation to {sub_agent}. The sub-agent produces patches or implementation",
        "reports for the full eligible apply scope.",
        "",
        "The primary model must:",
        "- Verify tasks, tests, and spec alignment before marking tasks complete.",
        "- Take over if delegated output is incomplete, unsafe, too broad, or unverifiable.",
        "- Not let the sub-agent mark tasks checkboxes complete.",
    ]


def _replace_managed_block(text: str, replacement: str) -> str:
    """Replace the managed block in *text* with *replacement*.

    Handles both current and legacy markers.
    """
    for start_marker, end_marker in [
        (MANAGED_BLOCK_START, MANAGED_BLOCK_END),
        (LEGACY_BLOCK_START, LEGACY_BLOCK_END),
    ]:
        start = text.find(start_marker)
        end = text.find(end_marker)
        if start == -1 or end == -1 or end < start:
            continue

        end += len(end_marker)
        prefix = text[:start].rstrip()
        suffix = text[end:].lstrip()
        parts = [p for p in (prefix, replacement.strip(), suffix) if p]
        return "\n\n".join(parts) + ("\n" if parts else "")

    raise ValueError("No managed block found in text")


def parse_existing_block(path: Path) -> dict | None:
    """Extract configuration from an existing managed block.

    Returns None if no block is found or parsing fails.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    for start_marker, end_marker in [
        (MANAGED_BLOCK_START, MANAGED_BLOCK_END),
        (LEGACY_BLOCK_START, LEGACY_BLOCK_END),
    ]:
        si = text.find(start_marker)
        ei = text.find(end_marker)
        if si == -1 or ei == -1 or ei < si:
            continue

        block = text[si + len(start_marker):ei]
        result: dict = {}
        in_models = False
        for line in block.strip().splitlines():
            stripped = line.strip()
            kv = stripped.removeprefix("- ").strip()
            if ":" not in kv:
                continue
            key, _, value = kv.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "primary":
                result["primary"] = value
            elif key == "mode":
                result["mode"] = value
            elif key == "sub-agent":
                result["sub_agent"] = value
            elif key == "scope":
                result["scope"] = value
            elif key == "models":
                in_models = True
                continue
            elif in_models and key and value:
                result.setdefault("models", {})[key] = value
        return result if result else None

    return None


# ── Skill bundle management (Group 5) ──────────────────────────────

def install_skill_bundle(
    skill_root: Path,
    primary_agent: str,
    sub_agent: str,
    models: dict[str, str],
) -> None:
    """Write the task-relay-delegation skill bundle to *skill_root*.

    Creates/replaces <skill_root>/task-relay-delegation/.
    """
    bundle_root = skill_root / SKILL_NAME
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)

    # SKILL.md (dynamic)
    bundle_root.joinpath("SKILL.md").write_text(
        _build_skill_md(primary_agent, sub_agent, models), encoding="utf-8"
    )

    # Agent config
    agents_dir = bundle_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    _write_agent_config(agents_dir, sub_agent)

    # Templates (from package assets)
    templates_dir = bundle_root / "templates"
    templates_dir.mkdir(exist_ok=True)
    _copy_templates(templates_dir)
    _remove_named_skill_bundle(skill_root, LEGACY_SKILL_NAME)


def remove_skill_bundle(skill_root: Path) -> bool:
    """Remove task-relay managed skill directories. Returns True if any were removed."""
    removed = _remove_named_skill_bundle(skill_root, SKILL_NAME)
    removed = _remove_named_skill_bundle(skill_root, LEGACY_SKILL_NAME) or removed
    return removed


def _remove_named_skill_bundle(skill_root: Path, skill_name: str) -> bool:
    bundle_root = skill_root / skill_name
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
        return True
    return False


def _build_skill_md(primary_agent: str, sub_agent: str, models: dict[str, str]) -> str:
    primary_model = models.get("primary", "default")
    sub_model = models.get("sub", "default")

    return "\n".join(
        [
            "---",
            f"name: {SKILL_NAME}",
            "description: Delegation skill for task-relay managed OpenSpec workflows.",
            "---",
            "",
            "## Task Relay Delegation",
            "",
            f"This project uses task-relay delegation with **{primary_agent}** as the primary",
            f"orchestration agent and **{sub_agent}** for delegated draft work.",
            "",
            "### Agent Configuration",
            "",
            f"- Primary: {primary_agent} (model: {primary_model})",
            f"- Sub-agent: {sub_agent} (model: {sub_model})",
            "",
            "### Output Modes",
            "",
            "When receiving a delegation prompt packet, produce ONE of:",
            "",
            "- **implementation-draft**: A patch or file-by-file edit plan.",
            "- **test-draft**: Tests to add and the command to run them.",
            "- **review**: Findings against a diff or spec, with severity.",
            "- **diagnosis**: Likely root cause and next fix for a failing command.",
            "",
            "Return only the requested output. Do not modify OpenSpec state or mark tasks complete.",
        ]
    )


def _write_agent_config(agents_dir: Path, sub_agent: str) -> None:
    if sub_agent == "codex":
        # Copy openai.yaml from assets
        try:
            source = resources.files("task_relay.assets").joinpath(
                f"{SKILL_NAME}/agents/openai.yaml"
            )
            if source.is_file():
                agents_dir.joinpath("openai.yaml").write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
                return
        except Exception:
            pass
    else:
        try:
            source = resources.files("task_relay.assets").joinpath(
                f"{SKILL_NAME}/agents/{sub_agent}.yaml"
            )
            if source.is_file():
                agents_dir.joinpath(f"{sub_agent}.yaml").write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
                return
        except Exception:
            pass

    # Fallback: write minimal config
    config_name = {"codex": "openai.yaml", "claude": "claude.yaml", "deepseek": "deepseek.yaml"}.get(
        sub_agent, f"{sub_agent}.yaml"
    )
    agents_dir.joinpath(config_name).write_text(
        f"# Agent configuration for {sub_agent}\n", encoding="utf-8"
    )


def _copy_templates(templates_dir: Path) -> None:
    templates = {
        "implementation-draft.md": "# Implementation Draft\n\n",
        "test-draft.md": "# Test Draft\n\n",
        "review.md": "# Review Findings\n\n",
        "diagnosis.md": "# Diagnosis\n\n",
    }

    # Try to copy from assets first
    try:
        asset_root = resources.files("task_relay.assets").joinpath(f"{SKILL_NAME}/templates")
        for name in templates:
            source = asset_root.joinpath(name)
            if source.is_file():
                templates_dir.joinpath(name).write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
                continue
            templates_dir.joinpath(name).write_text(templates[name], encoding="utf-8")
        return
    except Exception:
        pass

    for name, content in templates.items():
        templates_dir.joinpath(name).write_text(content, encoding="utf-8")


# ── High-level install / uninstall ─────────────────────────────────

def install(
    primary_agent: str,
    scope: str,
    mode: str,
    sub_agent: str,
    models: dict[str, str],
    cwd: str | Path | None = None,
) -> InstallResult:
    """Install delegation guidance for the given configuration."""
    guidance_path, skill_root = resolve_install_paths(primary_agent, scope, cwd)

    existing = guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else ""
    block = build_guidance_block(primary_agent, mode, sub_agent, models, scope)

    if _has_managed_block(guidance_path):
        updated = _replace_managed_block(existing, block)
        action = "updated"
    else:
        prefix = existing.rstrip()
        updated = f"{prefix}\n\n{block}\n" if prefix else f"# Agent Guidance\n\n{block}\n"
        action = "created"

    guidance_path.parent.mkdir(parents=True, exist_ok=True)
    guidance_path.write_text(updated, encoding="utf-8")

    install_skill_bundle(skill_root, primary_agent, sub_agent, models)

    return InstallResult(
        guidance_path=guidance_path,
        primary_agent=primary_agent,
        scope=scope,
        mode=mode,
        sub_agent=sub_agent,
        action=action,
    )


def clear(
    primary_agent: str | None = None,
    scope: str | None = None,
    cwd: str | Path | None = None,
) -> InstallResult | None:
    """Clear the managed block from guidance files (mode: main)."""
    project_root = Path(cwd).resolve() if cwd else Path.cwd()

    if primary_agent and scope:
        guidance_path, skill_root = resolve_install_paths(primary_agent, scope, project_root)
        if not guidance_path.exists():
            return None
        existing = guidance_path.read_text(encoding="utf-8")
        if not _has_managed_block(guidance_path):
            return None
        cleared = _replace_managed_block(existing, "").strip()
        if cleared:
            guidance_path.write_text(f"{cleared}\n", encoding="utf-8")
        else:
            guidance_path.unlink()
        remove_skill_bundle(skill_root)
        return InstallResult(
            guidance_path=guidance_path,
            primary_agent=primary_agent,
            scope=scope,
            mode="main",
            sub_agent=None,
            action="cleared",
        )

    # No explicit primary/scope: try all known locations
    result = None
    for agent in _GUIDANCE_FILE:
        for s in ("user", "project"):
            path, skill_root = resolve_install_paths(agent, s, project_root)
            if not path.exists():
                continue
            try:
                existing = path.read_text(encoding="utf-8")
                if not _has_managed_block(path):
                    continue
                cleared = _replace_managed_block(existing, "").strip()
                if cleared:
                    path.write_text(f"{cleared}\n", encoding="utf-8")
                else:
                    path.unlink()
                remove_skill_bundle(skill_root)
                result = InstallResult(
                    guidance_path=path,
                    primary_agent=agent,
                    scope=s,
                    mode="main",
                    sub_agent=None,
                    action="cleared",
                )
            except Exception:
                continue
    return result


def uninstall(
    scope: str | None = None, cwd: str | Path | None = None
) -> list[InstallResult]:
    """Remove delegation guidance. Returns list of results for each file processed."""
    project_root = Path(cwd).resolve() if cwd else Path.cwd()
    results: list[InstallResult] = []

    for agent, file_name in _GUIDANCE_FILE.items():
        candidates: list[tuple[str, Path, Path]] = []
        if scope is None or scope == "user":
            user_path, user_skill_root = resolve_install_paths(agent, "user", project_root)
            candidates.append(("user", user_path, user_skill_root))
        if scope is None or scope == "project":
            project_path, project_skill_root = resolve_install_paths(agent, "project", project_root)
            candidates.append(("project", project_path, project_skill_root))

        for s, path, skill_root in candidates:
            if not path.exists():
                continue
            try:
                existing = path.read_text(encoding="utf-8")
                if not _has_managed_block(path):
                    continue
                cleared = _replace_managed_block(existing, "").strip()
                if cleared:
                    path.write_text(f"{cleared}\n", encoding="utf-8")
                else:
                    path.unlink()
                remove_skill_bundle(skill_root)
                results.append(
                    InstallResult(
                        guidance_path=path,
                        primary_agent=agent,
                        scope=s,
                        mode=None,
                        sub_agent=None,
                        action="removed",
                    )
                )
            except Exception:
                continue

    return results
