"""Generate delegation packets with scoped OpenSpec context.

The delegate runs cold each invocation, so the packet carries selected OpenSpec
context and points to repo files the delegate can read from its worktree.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
import hashlib
import json
import re
import subprocess
import time
from typing import Any

from task_relay.errors import PacketGenerationError

SKILL_NAME = "task-relay-delegation"
VALID_MODES = (
    "review-proposal",
    "review-arbiter",
    "implementation-draft",
    "test-draft",
    "review",
    "diagnosis",
)
_CORE_ARTIFACTS = ("proposal.md", "design.md", "tasks.md")
_DESIGN_SECTION_TITLES = ("Decisions", "Risks / Trade-offs", "Open Questions")
_SIDECAR_NAMES = ("packer.yml", "packer.yaml", "packer.json")
_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "if", "in", "into",
    "is", "it", "of", "on", "or", "so", "that", "the", "this", "to", "when", "with",
    "done", "develop", "option", "land", "against", "current", "code", "now",
}


@dataclass(frozen=True)
class PacketSection:
    label: str
    text: str
    source: str

    @property
    def byte_count(self) -> int:
        return len(self.text.encode("utf-8"))


@dataclass(frozen=True)
class RepoReference:
    path: str
    source: str
    reason: str


@dataclass(frozen=True)
class SpecCandidate:
    path: str
    score: int
    selected: bool = False
    source: str = "deterministic"

    def to_report(self) -> dict[str, object]:
        return {
            "path": self.path,
            "score": self.score,
            "selected": self.selected,
            "source": self.source,
        }


@dataclass(frozen=True)
class SpecSelection:
    sections: tuple[PacketSection, ...]
    candidates: tuple[SpecCandidate, ...]
    scope_note: str | None = None
    fallback_reason: str | None = None
    selection_mode: str = "deterministic"
    model_resolution: dict[str, Any] | None = None


@dataclass(frozen=True)
class PackerSignals:
    path: Path | None
    raw: dict[str, Any]

    @property
    def task_signals(self) -> dict[str, dict[str, Any]]:
        tasks = self.raw.get("tasks", {})
        return tasks if isinstance(tasks, dict) else {}

    def for_task(self, task_id: str | None) -> dict[str, Any]:
        if not task_id:
            return {}
        value = self.task_signals.get(task_id, {})
        return value if isinstance(value, dict) else {}

    def hash_text(self) -> str:
        if not self.raw:
            return ""
        return json.dumps(self.raw, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class PacketPlan:
    template: str
    sections: tuple[PacketSection, ...]
    repo_references: tuple[RepoReference, ...] = ()
    scope_note: str | None = None
    fallback_reason: str | None = None
    selection_mode: str = "deterministic"
    spec_candidates: tuple[SpecCandidate, ...] = ()
    missing_signals: tuple[str, ...] = ()
    repo_context_gap: tuple[str, ...] = ()
    dynamic_diff_source: str | None = None
    model_resolution: dict[str, Any] | None = None
    resolver_cache_key: str | None = None

    @property
    def byte_estimate(self) -> int:
        header = len(self.template.encode("utf-8"))
        note = len((self.scope_note or "").encode("utf-8"))
        body = sum(section.byte_count for section in self.sections)
        labels = sum(len(section.label.encode("utf-8")) for section in self.sections)
        refs = sum(len(ref.path.encode("utf-8")) + len(ref.reason.encode("utf-8")) for ref in self.repo_references)
        return header + note + body + labels + refs

    def to_report(self, *, mode: str, change: str, task: str | None, full_change_context: bool) -> dict[str, object]:
        return {
            "mode": mode,
            "change": change,
            "task": task,
            "full_change_context": full_change_context,
            "selection_mode": self.selection_mode,
            "scope_note": self.scope_note,
            "fallback_reason": self.fallback_reason,
            "byte_estimate": self.byte_estimate,
            "spec_candidates": [candidate.to_report() for candidate in self.spec_candidates],
            "missing_signals": list(self.missing_signals),
            "repo_context_gap": list(self.repo_context_gap),
            "dynamic_diff_source": self.dynamic_diff_source,
            "model_resolution": self.model_resolution,
            "resolver_cache_key": self.resolver_cache_key,
            "sections": [
                {
                    "label": section.label,
                    "source": section.source,
                    "bytes": section.byte_count,
                }
                for section in self.sections
            ],
            "repo_references": [
                {"path": ref.path, "source": ref.source, "reason": ref.reason}
                for ref in self.repo_references
            ],
        }


def _load_template(mode: str) -> str:
    if mode not in VALID_MODES:
        raise PacketGenerationError(
            f"unknown mode '{mode}'. Valid modes: {', '.join(VALID_MODES)}"
        )
    asset = resources.files("task_relay.assets").joinpath(f"{SKILL_NAME}/templates/{mode}.md")
    if not asset.is_file():
        raise PacketGenerationError(f"template for mode '{mode}' is missing from the package")
    return asset.read_text(encoding="utf-8")


def _inline(label: str, text: str) -> str:
    return f"### {label}\n\n```\n{text.rstrip()}\n```"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _heading_match(line: str) -> re.Match[str] | None:
    return re.match(r"^(#{1,6})\s+(.*)$", line)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _normalize_task_signal(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _load_signals(change_dir: Path) -> PackerSignals:
    for name in _SIDECAR_NAMES:
        path = change_dir / name
        if not path.is_file():
            continue
        text = _read_text(path).strip()
        if not text:
            return PackerSignals(path=path, raw={})
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PacketGenerationError(
                f"packer signals sidecar {path} must use JSON-compatible YAML in this version: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise PacketGenerationError(f"packer signals sidecar {path} must contain an object")
        return PackerSignals(path=path, raw=payload)
    return PackerSignals(path=None, raw={})


def _extract_design_sections(path: Path, titles: tuple[str, ...] | list[str] | None = None) -> list[PacketSection]:
    lines = _read_text(path).splitlines()
    target_titles = tuple(titles) if titles is not None else _DESIGN_SECTION_TITLES
    targets = {_normalize_title(title): title for title in target_titles}
    sections: list[PacketSection] = []
    index = 0
    while index < len(lines):
        match = _heading_match(lines[index])
        if not match:
            index += 1
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        normalized = _normalize_title(title)
        if normalized not in targets:
            index += 1
            continue
        end = index + 1
        while end < len(lines):
            next_match = _heading_match(lines[end])
            if next_match and len(next_match.group(1)) <= level:
                break
            end += 1
        block = "\n".join(lines[index:end]).strip()
        sections.append(PacketSection(
            label=f"design.md :: {targets[normalized]}",
            text=block,
            source=path.name,
        ))
        index = end
    return sections


def _extract_task_block(path: Path, task_id: str | None) -> tuple[PacketSection | None, str | None]:
    text = _read_text(path)
    if not task_id:
        return PacketSection(label=path.name, text=text, source=path.name), None

    lines = text.splitlines()
    task_re = re.compile(rf"^- \[.\]\s+{re.escape(task_id)}\b")
    task_index = next((i for i, line in enumerate(lines) if task_re.search(line.strip())), None)
    if task_index is None:
        raise PacketGenerationError(f"task '{task_id}' not found in {path}")

    heading_index = None
    for i in range(task_index, -1, -1):
        if _heading_match(lines[i]):
            heading_index = i
            break

    block_lines: list[str] = []
    heading_title: str | None = None
    if heading_index is not None:
        heading_match = _heading_match(lines[heading_index])
        if heading_match is not None:
            heading_title = heading_match.group(2).strip()
        block_lines.append(lines[heading_index])
        block_lines.append("")

    block_lines.append(lines[task_index])
    follow = task_index + 1
    while follow < len(lines):
        line = lines[follow]
        stripped = line.strip()
        if _heading_match(line):
            break
        if re.match(r"^- \[.\]\s+\d", stripped):
            break
        if not stripped or line.startswith(("  ", "\t")):
            block_lines.append(line)
            follow += 1
            continue
        break

    label = path.name if heading_title is None else f"{path.name} :: {heading_title}"
    return PacketSection(label=label, text="\n".join(block_lines).strip(), source=path.name), heading_title


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in _STOPWORDS and not token.isdigit()
    }


def _spec_section(spec: Path, change_dir: Path) -> PacketSection:
    rel = str(spec.relative_to(change_dir))
    return PacketSection(label=rel, text=_read_text(spec), source=rel)


def _all_spec_sections(change_dir: Path) -> list[PacketSection]:
    return [_spec_section(spec, change_dir) for spec in sorted(change_dir.glob("specs/**/*.md"))]


def _score_specs(change_dir: Path, task_context: str) -> list[tuple[int, Path]]:
    spec_paths = sorted(change_dir.glob("specs/**/*.md"))
    tokens = _tokenize(task_context)
    scores: list[tuple[int, Path]] = []
    for spec in spec_paths:
        haystack = f"{spec.parent.name} {spec.stem} {_read_text(spec)}".lower()
        score = sum(1 for token in tokens if token in haystack)
        scores.append((score, spec))
    scores.sort(key=lambda item: (item[0], str(item[1])), reverse=True)
    return scores


def _candidate_reports(
    scores: list[tuple[int, Path]],
    change_dir: Path,
    selected: set[str] | None = None,
    *,
    source: str = "deterministic",
) -> tuple[SpecCandidate, ...]:
    selected = selected or set()
    return tuple(
        SpecCandidate(
            path=str(spec.relative_to(change_dir)),
            score=score,
            selected=str(spec.relative_to(change_dir)) in selected,
            source=source if str(spec.relative_to(change_dir)) in selected else "deterministic",
        )
        for score, spec in scores
    )


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _select_explicit_specs(change_dir: Path, task_signal: dict[str, Any], scores: list[tuple[int, Path]]) -> SpecSelection | None:
    capability = task_signal.get("capability")
    if not isinstance(capability, str) or not capability.strip():
        return None
    spec = change_dir / "specs" / capability.strip() / "spec.md"
    if not spec.is_file():
        return SpecSelection(
            sections=tuple(_all_spec_sections(change_dir)),
            candidates=_candidate_reports(scores, change_dir),
            scope_note=f"declared capability '{capability}' did not resolve; included all delta specs.",
            fallback_reason="invalid_explicit_capability",
            selection_mode="explicit_mapping",
        )
    rel = str(spec.relative_to(change_dir))
    return SpecSelection(
        sections=(_spec_section(spec, change_dir),),
        candidates=_candidate_reports(scores, change_dir, {rel}, source="explicit_mapping"),
        selection_mode="explicit_mapping",
    )


def _select_relevant_specs(
    change_dir: Path,
    task_context: str,
    task_signal: dict[str, Any] | None = None,
    *,
    task_id: str | None = None,
    cwd: str | None = None,
    model_resolver_enabled: bool = False,
    model_result: dict[str, Any] | None = None,
    model_call_limit: int = 1,
) -> SpecSelection:
    spec_paths = sorted(change_dir.glob("specs/**/*.md"))
    if not spec_paths:
        return SpecSelection(sections=(), candidates=())

    scores = _score_specs(change_dir, task_context)
    task_signal = task_signal or {}
    explicit = _select_explicit_specs(change_dir, task_signal, scores)
    if explicit is not None:
        return explicit

    if not task_context.strip():
        return SpecSelection(
            sections=tuple(_all_spec_sections(change_dir)),
            candidates=_candidate_reports(scores, change_dir),
            scope_note="no task context was available; included all delta specs.",
            fallback_reason="no_task_context",
        )

    best_score = scores[0][0]
    best = [spec for score, spec in scores if score == best_score and score > 0]
    if len(best) == 1:
        rel = str(best[0].relative_to(change_dir))
        return SpecSelection(
            sections=(_spec_section(best[0], change_dir),),
            candidates=_candidate_reports(scores, change_dir, {rel}),
        )

    fallback = SpecSelection(
        sections=tuple(_all_spec_sections(change_dir)),
        candidates=_candidate_reports(scores, change_dir),
        scope_note="capability relevance could not be resolved; included all delta specs.",
        fallback_reason="unresolved_capability_relevance",
    )
    if not model_resolver_enabled:
        return fallback
    if model_call_limit <= 0:
        return SpecSelection(
            **{**fallback.__dict__, "model_resolution": {"status": "skipped", "reason": "call_limit_exhausted"}}
        )
    if model_result is None:
        model_result, call_meta = _call_model_resolver(
            change_dir,
            task_context,
            scores,
            task_id=task_id,
            cwd=cwd,
        )
        if model_result is None:
            return SpecSelection(**{**fallback.__dict__, "model_resolution": call_meta})
        selected = _apply_model_selection(change_dir, scores, fallback, model_result)
        if selected.model_resolution:
            merged = {**selected.model_resolution, **{"call": call_meta}}
            return SpecSelection(**{**selected.__dict__, "model_resolution": merged})
        return selected
    return _apply_model_selection(change_dir, scores, fallback, model_result)


def _call_model_resolver(
    change_dir: Path,
    task_context: str,
    scores: list[tuple[int, Path]],
    *,
    task_id: str | None,
    cwd: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    from task_relay.agents.deepseek import DeepSeekRunner
    from task_relay.errors import AgentExecutionError
    from task_relay.trace import append_trace_record, new_session_id
    from task_relay.types import AgentRunRequest

    candidates = [
        {"path": str(spec.relative_to(change_dir)), "score": score}
        for score, spec in scores
    ]
    prompt = (
        "Mode: `model-resolution`\n"
        f"Change: `{change_dir.name}`\n"
        f"Task id: `{task_id or ''}`\n\n"
        "Select relevant context-packer scope from the constrained candidate set. "
        "Return JSON only with keys: specs (array of candidate paths), "
        "design_sections (array), task_dependencies (array), extra_reads (array), reason (string).\n\n"
        f"Task context:\n{task_context}\n\n"
        f"Candidates JSON:\n{json.dumps(candidates, ensure_ascii=False)}\n"
    )
    start = time.monotonic()
    session = new_session_id()
    result = None
    outcome = "error"
    error: str | None = None
    try:
        result = DeepSeekRunner().run(AgentRunRequest(prompt=prompt, cwd=cwd, session=session))
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError("model resolver returned non-object JSON")
        outcome = "success"
        return payload, {"status": "called", "target": "deepseek", "outcome": outcome}
    except (AgentExecutionError, json.JSONDecodeError, ValueError) as exc:
        error = str(exc)[:300]
        return None, {"status": "skipped", "reason": "model_call_failed", "target": "deepseek", "error": error}
    finally:
        duration = time.monotonic() - start
        usage = result.usage if result is not None else None
        append_trace_record({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "session": session,
            "target": "deepseek",
            "model": result.model if result is not None else None,
            "role": "model-resolution",
            "change": change_dir.name,
            "task": task_id,
            "duration_s": round(duration, 6),
            "outcome": outcome,
            "fallback_from": None,
            "branch": None,
            "tokens_in": usage.input_tokens if usage else None,
            "tokens_out": usage.output_tokens if usage else None,
            "cost_usd": usage.cost_usd if usage else None,
            "retries": result.retries if result is not None else 0,
            "error": error,
        }, cwd=cwd)


def _apply_model_selection(
    change_dir: Path,
    scores: list[tuple[int, Path]],
    fallback: SpecSelection,
    model_result: dict[str, Any],
) -> SpecSelection:
    specs = _coerce_list(model_result.get("specs"))
    score_by_rel = {str(spec.relative_to(change_dir)): score for score, spec in scores}
    invalid = [spec for spec in specs if spec not in score_by_rel]
    if invalid:
        return SpecSelection(
            **{**fallback.__dict__, "model_resolution": {"status": "rejected", "reason": "invalid_pick", "invalid": invalid}}
        )
    grounded = [spec for spec in specs if score_by_rel.get(spec, 0) > 0]
    if not grounded:
        return SpecSelection(
            **{**fallback.__dict__, "model_resolution": {"status": "rejected", "reason": "unsupported_pick"}}
        )
    sections = tuple(_spec_section(change_dir / spec, change_dir) for spec in specs)
    return SpecSelection(
        sections=sections,
        candidates=_candidate_reports(scores, change_dir, set(specs), source="model_fallback"),
        selection_mode="model_fallback",
        model_resolution={
            "status": "accepted",
            "reason": str(model_result.get("reason") or "model selected grounded candidates"),
            "outlier_check": "soft",
        },
    )


def _full_change_sections(change_dir: Path) -> list[PacketSection]:
    sections: list[PacketSection] = []
    for artifact in _CORE_ARTIFACTS:
        path = change_dir / artifact
        if path.is_file():
            sections.append(PacketSection(label=artifact, text=_read_text(path), source=artifact))
    sections.extend(_all_spec_sections(change_dir))
    return sections


def _resolve_repo_reference(base: Path, rel_path: str, source: str, reason: str) -> tuple[RepoReference | None, str | None]:
    path = base / rel_path if not Path(rel_path).is_absolute() else Path(rel_path)
    try:
        display = str(path.relative_to(base))
    except ValueError:
        display = str(path)
    if not path.is_file():
        return None, display
    return RepoReference(path=display, source=source, reason=reason), None


def _task_dependencies(tasks_path: Path, task_signal: dict[str, Any]) -> tuple[PacketSection, ...]:
    sections: list[PacketSection] = []
    for dep in _coerce_list(task_signal.get("dependencies")):
        section, _heading = _extract_task_block(tasks_path, dep)
        if section is not None:
            sections.append(PacketSection(
                label=f"dependency {section.label}",
                text=section.text,
                source=section.source,
            ))
    return tuple(sections)


def _dynamic_diff_paths(base: Path, *, diff_file: str | None = None, diff_from: str | None = None) -> tuple[list[str], str | None]:
    if diff_file:
        path = Path(diff_file)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            raise PacketGenerationError(f"diff file '{diff_file}' could not be resolved at {path}")
        text = _read_text(path)
        paths = _paths_from_diff_text(text)
        return paths, f"diff_file:{diff_file}"
    if diff_from:
        completed = subprocess.run(
            ["git", "diff", "--name-only", diff_from, "--"],
            cwd=base,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise PacketGenerationError(f"git diff from '{diff_from}' failed: {completed.stderr.strip()[:300]}")
        paths = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return paths, f"diff_from:{diff_from}"
    return [], None


def _paths_from_diff_text(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                candidate = parts[3]
                paths.append(candidate[2:] if candidate.startswith("b/") else candidate)
            continue
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if not line.startswith(("+", "-")) and " " not in line:
            paths.append(line)
    deduped: list[str] = []
    for item in paths:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _scoped_sections(
    change_dir: Path,
    task: str | None,
    *,
    base: Path,
    signals: PackerSignals,
    dynamic_repo_files: list[str] | None = None,
    dynamic_diff_source: str | None = None,
    model_resolver_enabled: bool = False,
    model_result: dict[str, Any] | None = None,
    model_call_limit: int = 1,
) -> tuple[list[PacketSection], list[RepoReference], str | None, str | None, str, tuple[SpecCandidate, ...], list[str], list[str], dict[str, Any] | None]:
    sections: list[PacketSection] = []
    repo_refs: list[RepoReference] = []
    missing_signals: list[str] = []
    repo_context_gap: list[str] = []

    task_signal = signals.for_task(task)
    proposal = change_dir / "proposal.md"
    if task is None and proposal.is_file():
        sections.append(PacketSection(label="proposal.md", text=_read_text(proposal), source="proposal.md"))

    tasks_path = change_dir / "tasks.md"
    heading_title = None
    task_text = ""
    if tasks_path.is_file():
        task_section, heading_title = _extract_task_block(tasks_path, task)
        if task_section is not None:
            sections.append(task_section)
            task_text = task_section.text
        if task_signal:
            sections.extend(_task_dependencies(tasks_path, task_signal))

    design_path = change_dir / "design.md"
    if design_path.is_file():
        design_titles = list(_DESIGN_SECTION_TITLES)
        for title in _coerce_list(task_signal.get("design_sections")):
            if title not in design_titles:
                design_titles.append(title)
        sections.extend(_extract_design_sections(design_path, design_titles))

    spec_selection = _select_relevant_specs(
        change_dir,
        " ".join(part for part in (heading_title, task_text, task or "") if part),
        task_signal,
        task_id=task,
        cwd=str(base),
        model_resolver_enabled=model_resolver_enabled,
        model_result=model_result,
        model_call_limit=model_call_limit,
    )
    sections.extend(spec_selection.sections)

    if task and signals.path is None:
        missing_signals.append("sidecar_absent")
    if task and not task_signal:
        missing_signals.append(f"task:{task}")

    for rel in _coerce_list(task_signal.get("repo_files")):
        ref, missing = _resolve_repo_reference(base, rel, "sidecar", "declared task repo context")
        if ref is None:
            repo_context_gap.append(missing or rel)
        else:
            repo_refs.append(ref)

    for rel in dynamic_repo_files or []:
        ref, missing = _resolve_repo_reference(base, rel, "dynamic_diff", "changed file from explicit diff source")
        if ref is None:
            repo_context_gap.append(missing or rel)
        else:
            repo_refs.append(ref)

    return (
        sections,
        repo_refs,
        spec_selection.scope_note,
        spec_selection.fallback_reason,
        spec_selection.selection_mode,
        spec_selection.candidates,
        missing_signals,
        repo_context_gap,
        spec_selection.model_resolution,
    )


def _input_hash(
    *,
    task: str | None,
    change_dir: Path,
    signals: PackerSignals,
    candidates: tuple[SpecCandidate, ...],
    dynamic_diff_source: str | None,
    model_resolver_enabled: bool,
    model_call_limit: int,
) -> str:
    digest = hashlib.sha256()
    digest.update((task or "").encode("utf-8"))
    for artifact in list(_CORE_ARTIFACTS) + [str(path.relative_to(change_dir)) for path in sorted(change_dir.glob("specs/**/*.md"))]:
        path = change_dir / artifact
        if path.is_file():
            digest.update(artifact.encode("utf-8"))
            digest.update(_read_text(path).encode("utf-8"))
    digest.update(signals.hash_text().encode("utf-8"))
    digest.update(json.dumps([c.to_report() for c in candidates], sort_keys=True).encode("utf-8"))
    digest.update((dynamic_diff_source or "").encode("utf-8"))
    digest.update(json.dumps({"enabled": model_resolver_enabled, "limit": model_call_limit}, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def plan_packet(
    mode: str,
    change: str,
    task: str | None = None,
    *,
    cwd: str | None = None,
    extra_reads: list[str] | None = None,
    full_change_context: bool = False,
    diff_file: str | None = None,
    diff_from: str | None = None,
    model_resolver_enabled: bool = False,
    model_result: dict[str, Any] | None = None,
    model_call_limit: int = 1,
) -> PacketPlan:
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    change_dir = base / "openspec" / "changes" / change
    if not change_dir.is_dir():
        raise PacketGenerationError(f"change '{change}' not found at {change_dir}")

    template = _load_template(mode).replace("<change-name>", change)
    if task:
        template = template.replace("<task-id>", task)

    signals = _load_signals(change_dir)
    dynamic_files, dynamic_source = _dynamic_diff_paths(base, diff_file=diff_file, diff_from=diff_from)
    if mode != "test-draft":
        dynamic_files = []
        dynamic_source = None

    repo_refs: list[RepoReference] = []
    missing_signals: list[str] = []
    repo_context_gap: list[str] = []
    selection_mode = "deterministic"
    spec_candidates: tuple[SpecCandidate, ...] = ()
    model_resolution: dict[str, Any] | None = None

    if full_change_context:
        sections = _full_change_sections(change_dir)
        scope_note = None
        fallback_reason = None
    else:
        (
            sections,
            repo_refs,
            scope_note,
            fallback_reason,
            selection_mode,
            spec_candidates,
            missing_signals,
            repo_context_gap,
            model_resolution,
        ) = _scoped_sections(
            change_dir,
            task,
            base=base,
            signals=signals,
            dynamic_repo_files=dynamic_files,
            dynamic_diff_source=dynamic_source,
            model_resolver_enabled=model_resolver_enabled,
            model_result=model_result,
            model_call_limit=model_call_limit,
        )

    for read in extra_reads or []:
        path = Path(read)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            raise PacketGenerationError(f"declared read '{read}' could not be resolved at {path}")
        sections.append(PacketSection(label=read, text=_read_text(path), source=read))

    if not sections and not repo_refs:
        raise PacketGenerationError(f"change '{change}' has no packet context")

    resolver_cache_key = _input_hash(
        task=task,
        change_dir=change_dir,
        signals=signals,
        candidates=spec_candidates,
        dynamic_diff_source=dynamic_source,
        model_resolver_enabled=model_resolver_enabled,
        model_call_limit=model_call_limit,
    )

    return PacketPlan(
        template=template,
        sections=tuple(sections),
        repo_references=tuple(repo_refs),
        scope_note=scope_note,
        fallback_reason=fallback_reason,
        selection_mode=selection_mode,
        spec_candidates=spec_candidates,
        missing_signals=tuple(missing_signals),
        repo_context_gap=tuple(repo_context_gap),
        dynamic_diff_source=dynamic_source,
        model_resolution=model_resolution,
        resolver_cache_key=resolver_cache_key,
    )


def build_packet(
    mode: str,
    change: str,
    task: str | None = None,
    *,
    cwd: str | None = None,
    extra_reads: list[str] | None = None,
    full_change_context: bool = False,
    diff_file: str | None = None,
    diff_from: str | None = None,
    model_resolver_enabled: bool = False,
    model_result: dict[str, Any] | None = None,
    model_call_limit: int = 1,
) -> str:
    plan = plan_packet(
        mode,
        change,
        task,
        cwd=cwd,
        extra_reads=extra_reads,
        full_change_context=full_change_context,
        diff_file=diff_file,
        diff_from=diff_from,
        model_resolver_enabled=model_resolver_enabled,
        model_result=model_result,
        model_call_limit=model_call_limit,
    )
    parts = [plan.template.rstrip()]
    if plan.scope_note:
        parts.append(f"Scope note: {plan.scope_note}")
    if plan.repo_references:
        parts.append("## Referenced Repo Context")
        parts.extend(f"- `{ref.path}` ({ref.reason}; source: {ref.source})" for ref in plan.repo_references)
    parts.append("## Inlined Context")
    parts.extend(_inline(section.label, section.text) for section in plan.sections)
    return "\n\n".join(parts) + "\n"
