from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Iterable

from task_relay.agents import check_target
from task_relay.delegation import detect_managed_blocks, parse_existing_block, resolve_install_paths
from task_relay.models import get_catalog
from task_relay.review_config import ReviewRoleEntry
from task_relay import worktree


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    ok: bool
    severity: str
    scope: str
    summary: str
    detail: str | None = None
    remediation: str | None = None


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    checks: tuple[DoctorCheck, ...]
    configured_targets: tuple[str, ...]
    config_paths: tuple[str, ...]
    repo_root: str | None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "configured_targets": list(self.configured_targets),
            "config_paths": list(self.config_paths),
            "repo_root": self.repo_root,
            "checks": [asdict(check) for check in self.checks],
        }


def build_doctor_report(
    *,
    cwd: str | None = None,
    target_agents: list[str] | None = None,
    scope: str | None = None,
) -> DoctorReport:
    base = Path(cwd).resolve() if cwd else Path.cwd()
    repo_root = worktree.git_repo_root(str(base))
    checks: list[DoctorCheck] = []

    blocks = _collect_blocks(base, target_agents=target_agents, scope=scope)
    config_paths = tuple(str(item["path"]) for item in blocks)
    configured_targets = tuple(
        target for target in _configured_targets(blocks, target_agents) if target
    )

    checks.extend(_repo_checks(base, repo_root))
    checks.extend(_config_checks(blocks))
    checks.extend(_target_checks(configured_targets))
    checks.extend(_model_checks(blocks))
    checks.extend(_path_checks(base, blocks, target_agents=target_agents, scope=scope))

    ok = not any(check.severity == "error" and not check.ok for check in checks)
    return DoctorReport(
        ok=ok,
        checks=tuple(checks),
        configured_targets=configured_targets,
        config_paths=config_paths,
        repo_root=str(repo_root) if repo_root else None,
    )


def format_doctor_report(report: DoctorReport) -> str:
    lines = [
        "delegation ready" if report.ok else "delegation issues detected",
        f"configured targets: {', '.join(report.configured_targets) if report.configured_targets else '(none)'}",
    ]
    if report.repo_root:
        lines.append(f"repo root: {report.repo_root}")
    if report.config_paths:
        lines.append("config paths:")
        for path in report.config_paths:
            lines.append(f"- {path}")
    else:
        lines.append("config paths: (none)")
    lines.append("checks:")
    for check in report.checks:
        status = "PASS" if check.ok else check.severity.upper()
        lines.append(f"- [{status}] {check.id}: {check.summary}")
        if check.detail:
            lines.append(f"  detail: {check.detail}")
        if check.remediation:
            lines.append(f"  remediation: {check.remediation}")
    return "\n".join(lines)


def summarize_validation(report: DoctorReport) -> tuple[bool, list[str]]:
    blockers = [
        check.summary
        for check in report.checks
        if not check.ok and check.severity == "error"
    ]
    return report.ok, blockers


def _collect_blocks(
    base: Path,
    *,
    target_agents: list[str] | None,
    scope: str | None,
) -> list[dict]:
    blocks: list[dict] = []
    selected_targets = list(target_agents or [])
    if not selected_targets:
        discovered = detect_managed_blocks(base)
        paths = discovered.get(scope, []) if scope else (discovered.get("project", []) + discovered.get("user", []))
        for path in paths:
            parsed = parse_existing_block(path)
            if parsed:
                blocks.append({"path": path, "scope": _infer_scope(base, path), "config": parsed})
        if blocks:
            return blocks
        selected_targets = ["claude", "codex"]

    scopes = [scope] if scope else ["project", "user"]
    for agent in selected_targets:
        for candidate_scope in scopes:
            path, _ = resolve_install_paths(agent, candidate_scope, base)
            parsed = parse_existing_block(path)
            if parsed:
                blocks.append({"path": path, "scope": candidate_scope, "config": parsed})
    return blocks


def _configured_targets(blocks: list[dict], explicit_targets: list[str] | None) -> list[str]:
    configured: list[str] = []
    for item in blocks:
        config = item["config"]
        primary = config.get("primary")
        if primary:
            configured.append(primary)
        for reviewer in config.get("reviewers") or []:
            configured.append(reviewer.agent)
        for arbiter in config.get("arbiters") or []:
            configured.append(arbiter.agent)
        for agent, _model in config.get("apply_chain") or []:
            configured.append(agent)
    if configured:
        ordered = []
        for target in configured:
            if target not in ordered:
                ordered.append(target)
        return ordered
    return list(explicit_targets or [])


def _repo_checks(base: Path, repo_root: Path | None) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    if repo_root is None:
        checks.append(DoctorCheck(
            id="repo.git",
            ok=False,
            severity="error",
            scope="repo",
            summary="current directory is not inside a git repository",
            remediation="Run task-relay from a git repo before using isolated delegation.",
        ))
        return checks

    checks.append(DoctorCheck(
        id="repo.git",
        ok=True,
        severity="info",
        scope="repo",
        summary="git repository detected",
        detail=str(repo_root),
    ))
    worktree_dir = repo_root / ".task_relay"
    try:
        worktree_dir.mkdir(parents=True, exist_ok=True)
        checks.append(DoctorCheck(
            id="repo.worktree-path",
            ok=True,
            severity="info",
            scope="repo",
            summary="task-relay worktree path is writable",
            detail=str(worktree_dir),
        ))
    except OSError as exc:
        checks.append(DoctorCheck(
            id="repo.worktree-path",
            ok=False,
            severity="error",
            scope="repo",
            summary="task-relay worktree path is not writable",
            detail=str(exc),
            remediation="Fix filesystem permissions for .task_relay/ under the repo root.",
        ))
    return checks


def _config_checks(blocks: list[dict]) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    if not blocks:
        checks.append(DoctorCheck(
            id="config.managed-block",
            ok=False,
            severity="warning",
            scope="config",
            summary="no managed delegation block found",
            remediation="Run `trly install` or pass explicit targets to doctor for environment-only checks.",
        ))
        return checks

    checks.append(DoctorCheck(
        id="config.managed-block",
        ok=True,
        severity="info",
        scope="config",
        summary=f"found {len(blocks)} managed delegation block(s)",
    ))

    for item in blocks:
        config = item["config"]
        path = item["path"]
        features = config.get("features") or []
        if "review" in features and not config.get("reviewers"):
            checks.append(DoctorCheck(
                id=f"config.reviewers:{path.name}",
                ok=False,
                severity="error",
                scope=item["scope"],
                summary="review is enabled but no reviewers are configured",
                detail=str(path),
                remediation="Re-run `trly install` with --reviewers or disable the review feature.",
            ))
        if "apply" in features and not config.get("apply_chain"):
            checks.append(DoctorCheck(
                id=f"config.apply-chain:{path.name}",
                ok=False,
                severity="error",
                scope=item["scope"],
                summary="apply is enabled but no apply chain is configured",
                detail=str(path),
                remediation="Re-run `trly install` with --apply-chain or disable the apply feature.",
            ))

    if len(blocks) > 1:
        grouped: dict[str, list[dict]] = {}
        for item in blocks:
            primary = item["config"].get("primary")
            if primary:
                grouped.setdefault(primary, []).append(item)
        for primary, entries in grouped.items():
            if len(entries) < 2:
                continue
            baseline = _comparable_config(entries[0]["config"])
            for other in entries[1:]:
                if _comparable_config(other["config"]) != baseline:
                    checks.append(DoctorCheck(
                        id=f"config.scope-conflict:{primary}",
                        ok=False,
                        severity="warning",
                        scope="config",
                        summary="user and project delegation configs conflict",
                        detail=f"{entries[0]['path']} vs {other['path']}",
                        remediation="Choose one source of truth or align the managed blocks.",
                    ))
                    break
    return checks


def _target_checks(targets: Iterable[str]) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    for target in targets:
        status = check_target(target)
        checks.append(DoctorCheck(
            id=f"target.{target}",
            ok=status.ok,
            severity="error" if not status.ok else "info",
            scope="agent",
            summary=f"{target} target is {'ready' if status.ok else 'not ready'}",
            detail=status.reason,
            remediation=None if status.ok else f"Fix {target} authentication or installation before delegation.",
        ))
    return checks


def _model_checks(blocks: list[dict]) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    for item in blocks:
        config = item["config"]
        entries: list[tuple[str, str | None]] = []
        for reviewer in config.get("reviewers") or []:
            entries.append((reviewer.agent, reviewer.model))
        for arbiter in config.get("arbiters") or []:
            entries.append((arbiter.agent, arbiter.model))
        for agent, model in config.get("apply_chain") or []:
            entries.append((agent, model))

        for agent, model in entries:
            if not model:
                continue
            try:
                catalog = get_catalog(agent)
            except ValueError:
                checks.append(DoctorCheck(
                    id=f"model.{agent}",
                    ok=False,
                    severity="error",
                    scope="model",
                    summary=f"unknown agent '{agent}' referenced in managed config",
                    remediation="Update the managed block to use a supported agent.",
                ))
                continue
            known = {entry.id for entry in catalog}
            checks.append(DoctorCheck(
                id=f"model.{agent}:{model}",
                ok=model in known,
                severity="error" if model not in known else "info",
                scope="model",
                summary=f"model reference {model} for {agent} is {'valid' if model in known else 'invalid'}",
                remediation=None if model in known else "Update the managed block to a model present in task_relay/models.py.",
            ))
    return checks


def _path_checks(
    base: Path,
    blocks: list[dict],
    *,
    target_agents: list[str] | None,
    scope: str | None,
) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    targets = _configured_targets(blocks, target_agents)
    scopes = [scope] if scope else ["project", "user"]
    for agent in targets:
        for candidate_scope in scopes:
            guidance_path, skill_root = resolve_install_paths(agent, candidate_scope, base)
            checks.append(_writable_check(
                id=f"path.guidance:{agent}:{candidate_scope}",
                path=guidance_path,
                scope="path",
                summary=f"guidance path for {agent}/{candidate_scope}",
            ))
            checks.append(_writable_check(
                id=f"path.skills:{agent}:{candidate_scope}",
                path=skill_root / "task-relay-delegation",
                scope="path",
                summary=f"skill bundle path for {agent}/{candidate_scope}",
            ))
            features = _features_for_path(blocks, agent, candidate_scope)
            split_skills = []
            if "review" in features:
                split_skills.append("trly-review")
            if "apply" in features:
                split_skills.append("trly-apply")
            for skill_name in split_skills:
                checks.append(_writable_check(
                    id=f"path.skills:{agent}:{candidate_scope}:{skill_name}",
                    path=skill_root / skill_name,
                    scope="path",
                    summary=f"{skill_name} skill bundle path for {agent}/{candidate_scope}",
                ))
    return checks


def _features_for_path(blocks: list[dict], agent: str, scope: str) -> set[str]:
    features: set[str] = set()
    for block in blocks:
        config = block.get("config") or {}
        if config.get("primary") != agent:
            continue
        block_scope = block.get("scope") or config.get("scope") or "project"
        if block_scope != scope:
            continue
        features.update(config.get("features") or [])
    return features


def _writable_check(*, id: str, path: Path, scope: str, summary: str) -> DoctorCheck:
    probe = path if path.exists() else path.parent
    ok = os.access(probe, os.W_OK)
    return DoctorCheck(
        id=id,
        ok=ok,
        severity="error" if not ok else "info",
        scope=scope,
        summary=f"{summary} is {'writable' if ok else 'not writable'}",
        detail=str(path),
        remediation=None if ok else f"Grant write access to {probe}.",
    )


def _infer_scope(base: Path, path: Path) -> str:
    try:
        path.relative_to(base)
        return "project"
    except ValueError:
        return "user"


def _comparable_config(config: dict) -> dict:
    return {
        "primary": config.get("primary"),
        "features": tuple(config.get("features") or []),
        "reviewers": tuple(
            (entry.agent, entry.persona, entry.model)
            for entry in (config.get("reviewers") or [])
            if isinstance(entry, ReviewRoleEntry)
        ),
        "arbiters": tuple(
            (entry.agent, entry.persona, entry.model)
            for entry in (config.get("arbiters") or [])
            if isinstance(entry, ReviewRoleEntry)
        ),
        "apply_chain": tuple((agent, model) for agent, model in (config.get("apply_chain") or [])),
    }
