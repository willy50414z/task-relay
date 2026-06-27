"""Path resolution, managed block generation, and skill bundle management."""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import shutil

MANAGED_BLOCK_START = "<!-- task-relay:start -->"
MANAGED_BLOCK_END = "<!-- task-relay:end -->"
LEGACY_BLOCK_START = "<!-- task-relay:openspec-delegation:start -->"
LEGACY_BLOCK_END = "<!-- task-relay:openspec-delegation:end -->"

SKILL_NAME = "task-relay-delegation"
LEGACY_SKILL_NAME = "openspec-deepseek-delegation"

_GUIDANCE_FILE: dict[str, str] = {
    "claude": "CLAUDE.md",
    "codex": "AGENTS.md",
}

_SKILL_DIR: dict[str, str] = {
    "claude": ".claude/skills",
    "codex": ".codex/skills",
}


@dataclass(frozen=True)
class InstallResult:
    guidance_path: Path
    primary_agent: str
    scope: str
    mode: str | None
    sub_agent: str | None
    action: str


def resolve_install_paths(primary_agent: str, scope: str, cwd: str | Path | None = None) -> tuple[Path, Path]:
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
    """Scan user and project paths for files containing a task-relay managed block."""
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


def build_guidance_block(
    primary_agent: str,
    features: list[str],
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
    scope: str,
) -> str:
    """Generate a dynamic managed guidance block from wizard state."""
    lines = [
        MANAGED_BLOCK_START,
        "## Task Relay Delegation",
        "",
        f"- primary: {primary_agent}",
        f"- scope: {scope}",
    ]

    if features:
        lines.append(f"- features: {', '.join(features)}")
    else:
        lines.append("- features: none")

    if review_chain:
        lines.append(f"- review-chain: {_format_chain(review_chain)}")
    if apply_chain:
        lines.append(f"- apply-chain: {_format_chain(apply_chain)}")

    lines.append("")
    lines.append(_features_header(features, primary_agent, review_chain, apply_chain))
    lines.append("")
    lines.extend(_features_policy(features, primary_agent, review_chain, apply_chain))
    lines.append("")
    lines.append(MANAGED_BLOCK_END)

    return "\n".join(lines)


def _format_chain(chain: list[tuple[str, str | None]]) -> str:
    """Format chain as 'agent=model, agent' string."""
    return ", ".join(
        f"{agent}={model}" if model else agent
        for agent, model in chain
    )


def _features_header(
    features: list[str],
    primary_agent: str,
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
) -> str:
    if not features:
        return f"Delegation mode: main — all work stays with {primary_agent}."

    parts: list[str] = []
    if review_chain:
        parts.append(f"review via {_format_chain(review_chain)}")
    if apply_chain:
        parts.append(f"apply via {_format_chain(apply_chain)}")

    joined = "; ".join(parts)
    return f"Delegation: {primary_agent} orchestrates — {joined}."


def _features_policy(
    features: list[str],
    primary_agent: str,
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
) -> list[str]:
    if not features:
        return [
            "All work remains with the primary model. No automatic delegation.",
        ]

    policy: list[str] = []

    policy.append(f"Primary model ({primary_agent}) owns:")
    policy.append("- Architecture, security, data migration, destructive operations, credentials.")
    policy.append("- OpenSpec artifact interpretation, scope, and state changes.")
    policy.append("- Integration of delegated output and final verification.")
    policy.append("")

    if "review" in features and review_chain:
        policy.append("## Review Workflow (propose phase)")
        policy.append("")
        primary_review = review_chain[0][0]
        policy.append(f"When a proposal is ready for review, {primary_agent} SHALL:")
        policy.append(f"1. Package the proposal context using the `review-proposal` template.")
        policy.append(f"2. Delegate to review chain (primary: {primary_review}).")
        policy.append(f"3. The review agent evaluates requirement clarity, direction correctness,")
        policy.append(f"   and implementation plan completeness.")
        policy.append(f"4. The review agent writes findings to `spec/delegation_review.md`.")
        policy.append(f"5. The review agent MUST ask the user when encountering ambiguity")
        policy.append(f"   rather than defining solutions independently.")
        policy.append(f"6. Delegate with `trly run --target <agent> --prompt-file <packet>"
                      f" --expect-output spec/delegation_review.md` so a missing or empty review"
                      f" fails loudly instead of being trusted from stdout.")
        policy.append(f"7. If the run fails with a delegation-output error, re-run or escalate;"
                      f" do NOT treat the review as done.")
        policy.append(f"8. {primary_agent} MUST read the review artifact content before adopting it; a non-empty file only proves the gate passed.")
        policy.append(f"9. {primary_agent} reads the review and updates proposal artifacts as needed.")
        policy.append("")
        policy.append("Review agent non-goals: do not modify OpenSpec state, mark tasks,")
        policy.append("perform destructive operations, or make architecture decisions.")
        policy.append("")

    if "apply" in features and apply_chain:
        policy.append("## Apply Workflow (implementation phase)")
        policy.append("")
        primary_apply = apply_chain[0][0]
        policy.append(f"When implementation is ready, {primary_agent} SHALL:")
        policy.append(f"1. Package the apply request using implementation-draft or test-draft templates.")
        policy.append(f"2. For multi-task apply, open one change worktree `chg/<change-name>` from HEAD as"
                      f"   the integration sandbox; single trivial delegations may skip this and use one"
                      f"   isolated task branch directly.")
        policy.append(f"3. Delegate each implementation or test task to apply chain (primary: {primary_apply})"
                      f"   with `trly run --target <agent> --prompt-file <packet> --isolate --base <ref>`.")
        policy.append(f"4. `--isolate` runs the delegate in an ephemeral git worktree on a throwaway"
                      f"   branch `tr/<task-id>` with `git push` disabled; `--base` points at the change"
                      f"   branch tip so dependent tasks see previously accepted work.")
        policy.append(f"5. Apply is phased: develop and commit onto task branches, merge accepted task"
                      f"   branches back into `chg/<change-name>`, run disjoint test delegations from the"
                      f"   accumulated change branch, then run primary integration tests in the change"
                      f"   worktree before a single final merge to the real branch.")
        policy.append(f"6. {primary_agent} reviews each branch diff before merge and marks tasks complete"
                      f"   only after the accepted work is integrated. An empty branch fails loudly (no"
                      f"   silent success).")
        policy.append("")
        policy.append("Apply agent non-goals: do not modify OpenSpec state, mark tasks checkboxes,")
        policy.append("or make architecture/security/migration decisions.")
        policy.append("")

    policy.append("## Task Tags")
    policy.append("")
    if "review" in features:
        policy.append("- `[delegate:review]` — route proposal review to review chain.")
    if "apply" in features:
        policy.append(f"- `[delegate:{apply_chain[0][0] if apply_chain else 'apply'}]` — route implementation to apply chain.")
        policy.append("- `[delegate:test]` — route test authoring.")
    policy.append(f"- `[{primary_agent}-only]` — keep in primary agent.")
    policy.append("")
    policy.append(f"Use `trly run --target <agent> --prompt-file <packet>` for delegated work.")

    return policy


def _replace_managed_block(text: str, replacement: str) -> str:
    """Replace the managed block in *text* with *replacement*."""
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
    """Extract configuration from an existing managed block."""
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
            if stripped == "- models:" or stripped == "models:":
                in_models = True
                continue
            if in_models:
                if stripped.startswith("- ") and ":" in stripped[2:]:
                    key, _, value = stripped[2:].partition(":")
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        result.setdefault("models", {})[key] = value
                    continue
                in_models = False
            kv = stripped.removeprefix("- ").strip()
            if ":" not in kv:
                continue
            key, _, value = kv.partition(":")
            key = key.strip()
            value = value.strip()

            if key == "features":
                result["features"] = [f.strip() for f in value.split(",") if f.strip() and f.strip() != "none"]
            elif key in ("review-chain", "apply-chain"):
                result[key.replace("-", "_")] = _parse_chain_value(value)
            elif key == "primary":
                result["primary"] = value
            elif key == "mode":
                result["mode"] = value
            elif key == "sub-agent":
                result["sub_agent"] = value
            elif key == "scope":
                result["scope"] = value

        # Legacy format → new format mapping
        if not result.get("features") and result.get("mode") and result["mode"] != "main":
            result["features"] = ["apply"]
        if not result.get("apply_chain") and result.get("sub_agent"):
            sub = result["sub_agent"]
            models_dict = result.get("models") or {}
            model = models_dict.get("sub") or models_dict.get(sub)
            result["apply_chain"] = [(sub, model)]

        return result if result else None

    return None


def _parse_chain_value(value: str) -> list[tuple[str, str | None]]:
    """Parse 'agent=model, agent' into [(agent, model_or_none), ...]."""
    chain: list[tuple[str, str | None]] = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" in entry:
            agent, _, model = entry.partition("=")
            agent = agent.strip()
            model_val = model.strip() or None
        else:
            agent = entry.strip()
            model_val = None
        if agent:
            chain.append((agent, model_val))
    return chain


def install_skill_bundle(
    skill_root: Path,
    primary_agent: str,
    features: list[str],
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
) -> None:
    """Write the task-relay-delegation skill bundle to *skill_root*."""
    bundle_root = skill_root / SKILL_NAME
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True, exist_ok=True)

    bundle_root.joinpath("SKILL.md").write_text(
        _build_skill_md(primary_agent, features, review_chain, apply_chain),
        encoding="utf-8",
    )

    agents_dir = bundle_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    _write_agent_configs(agents_dir, review_chain, apply_chain)

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


def _build_skill_md(
    primary_agent: str,
    features: list[str],
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
) -> str:
    lines = [
        "---",
        f"name: {SKILL_NAME}",
        "description: Delegation skill for task-relay managed OpenSpec workflows.",
        "---",
        "",
        "## Task Relay Delegation",
        "",
        f"This project uses task-relay delegation with **{primary_agent}** as the primary",
        "orchestration agent.",
        "",
    ]

    if review_chain:
        lines.append("### Review Chain")
        lines.append("")
        for i, (agent, model) in enumerate(review_chain):
            role = "primary" if i == 0 else f"fallback {i}"
            model_str = model or "default"
            lines.append(f"- {role}: **{agent}** (model: {model_str})")
        lines.append("")

    if apply_chain:
        lines.append("### Apply Chain")
        lines.append("")
        for i, (agent, model) in enumerate(apply_chain):
            role = "primary" if i == 0 else f"fallback {i}"
            model_str = model or "default"
            lines.append(f"- {role}: **{agent}** (model: {model_str})")
        lines.append("")

    lines.append("### Primary Execution Workflow")
    lines.append("")
    lines.append("The primary agent should use task-relay explicitly rather than asking a")
    lines.append("delegate from free-form chat. Package context first, then run the selected")
    lines.append("chain target with the packet file.")
    lines.append("")
    if "review" in features and review_chain:
        primary_review = review_chain[0][0]
        lines.append("#### Review")
        lines.append("")
        lines.append("Use review during the OpenSpec propose phase:")
        lines.append("")
        lines.append("```bash")
        lines.append("trly pack --mode review-proposal --change <change> --out <packet>")
        lines.append(
            f"trly run --target {primary_review} --prompt-file <packet> --expect-output spec/delegation_review.md"
        )
        lines.append("```")
        lines.append("")
        lines.append("The review delegate must write `spec/delegation_review.md`. The primary")
        lines.append("agent must read that artifact before accepting findings; a non-empty file")
        lines.append("only proves the output gate passed.")
        lines.append("")
    if "apply" in features and apply_chain:
        primary_apply = apply_chain[0][0]
        lines.append("#### Apply")
        lines.append("")
        lines.append("Use apply during implementation or test drafting:")
        lines.append("")
        lines.append("```bash")
        lines.append("trly pack --mode implementation-draft --change <change> --task <task-id> --out <packet>")
        lines.append(f"trly run --target {primary_apply} --prompt-file <packet> --isolate --base <base-ref>")
        lines.append("```")
        lines.append("")
        lines.append("For test packets, use `--mode test-draft` and add `--diff-from` or")
        lines.append("`--diff-file` when dynamic changed-file context is needed. `--isolate`")
        lines.append("runs the delegate in an ephemeral git worktree on a throwaway `tr/<id>`")
        lines.append("branch with `git push` disabled. The primary agent reviews and integrates")
        lines.append("accepted branch diffs, runs final verification, and only then marks")
        lines.append("OpenSpec tasks complete.")
        lines.append("")

    lines.append("### Output Modes")
    lines.append("")
    lines.append("When receiving a delegation prompt packet, produce ONE of:")
    lines.append("")
    if "review" in features:
        lines.append("- **review-proposal**: Review a proposal for clarity, correctness, and completeness.")
    if "apply" in features:
        lines.append("- **implementation-draft**: A patch or file-by-file edit plan.")
        lines.append("- **test-draft**: Tests to add and the command to run them.")
        lines.append("- **review**: Findings against a diff or spec, with severity.")
        lines.append("- **diagnosis**: Likely root cause and next fix for a failing command.")
    lines.append("")
    lines.append("Return only the requested output. Do not modify OpenSpec state or mark tasks complete.")

    return "\n".join(lines)


def _write_agent_configs(
    agents_dir: Path,
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
) -> None:
    """Write agent config files for all agents in review and apply chains."""
    seen: set[str] = set()
    for agent, _model in review_chain + apply_chain:
        if agent in seen:
            continue
        seen.add(agent)
        _write_agent_config(agents_dir, agent)


def _write_agent_config(agents_dir: Path, agent: str) -> None:
    if agent == "codex":
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
                f"{SKILL_NAME}/agents/{agent}.yaml"
            )
            if source.is_file():
                agents_dir.joinpath(f"{agent}.yaml").write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
                return
        except Exception:
            pass

    config_name = {"codex": "openai.yaml", "claude": "claude.yaml", "deepseek": "deepseek.yaml"}.get(
        agent, f"{agent}.yaml"
    )
    agents_dir.joinpath(config_name).write_text(
        f"# Agent configuration for {agent}\n", encoding="utf-8"
    )


def _copy_templates(templates_dir: Path) -> None:
    templates = {
        "implementation-draft.md": "# Implementation Draft\n\n",
        "test-draft.md": "# Test Draft\n\n",
        "review.md": "# Review Findings\n\n",
        "diagnosis.md": "# Diagnosis\n\n",
        "review-proposal.md": "# Review Proposal\n\n",
    }

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


def install(
    primary_agent: str,
    scope: str,
    features: list[str],
    review_chain: list[tuple[str, str | None]],
    apply_chain: list[tuple[str, str | None]],
    cwd: str | Path | None = None,
) -> InstallResult:
    """Install delegation guidance for the given configuration."""
    guidance_path, skill_root = resolve_install_paths(primary_agent, scope, cwd)

    existing = guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else ""
    block = build_guidance_block(primary_agent, features, review_chain, apply_chain, scope)

    if _has_managed_block(guidance_path):
        updated = _replace_managed_block(existing, block)
        action = "updated"
    else:
        prefix = existing.rstrip()
        updated = f"{prefix}\n\n{block}\n" if prefix else f"# Agent Guidance\n\n{block}\n"
        action = "created"

    guidance_path.parent.mkdir(parents=True, exist_ok=True)
    guidance_path.write_text(updated, encoding="utf-8")

    install_skill_bundle(skill_root, primary_agent, features, review_chain, apply_chain)

    return InstallResult(
        guidance_path=guidance_path,
        primary_agent=primary_agent,
        scope=scope,
        mode=None if features else "main",
        sub_agent=None,
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

    for agent in _GUIDANCE_FILE:
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
