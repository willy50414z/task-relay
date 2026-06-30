"""Generate delegation packets with scoped OpenSpec context."""

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
_DEFAULT_DESIGN_SECTION_TITLES = ("Decisions", "Risks / Trade-offs", "Open Questions")
_SIDECAR_NAMES = ("packer.yml", "packer.yaml", "packer.json")
_MODE_BUDGET_BYTES = {
    "review-proposal": 48_000,
    "review-arbiter": 48_000,
    "implementation-draft": 24_000,
    "test-draft": 28_000,
    "review": 24_000,
    "diagnosis": 24_000,
}
_MODEL_SELECTOR_FIELDS = {"specs", "design_sections", "task_dependencies", "extra_reads", "reason"}
_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "if", "in", "into",
    "is", "it", "of", "on", "or", "so", "that", "the", "this", "to", "when", "with",
    "done", "develop", "option", "land", "against", "current", "code", "now",
}
CACHE_BREAK_MARKER = "<!-- trly:cache_break -->"
TEMPLATE_END_MARKER = "<!-- trly:template_end -->"


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

    @property
    def byte_count(self) -> int:
        return len(self.path.encode("utf-8")) + len(self.reason.encode("utf-8"))


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
class TrimmedSection:
    label: str
    source: str
    bytes: int
    reason: str

    def to_report(self) -> dict[str, object]:
        return {
            "label": self.label,
            "source": self.source,
            "bytes": self.bytes,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SpecSelection:
    sections: tuple[PacketSection, ...]
    candidates: tuple[SpecCandidate, ...]
    design_section_titles: tuple[str, ...] = ()
    task_dependencies: tuple[str, ...] = ()
    extra_reads: tuple[str, ...] = ()
    core_spec_paths: tuple[str, ...] = ()
    scope_note: str | None = None
    fallback_reason: str | None = None
    selection_mode: str = "deterministic"
    model_resolution: dict[str, Any] | None = None


@dataclass(frozen=True)
class SelectionResult:
    sections: tuple[PacketSection, ...]
    repo_references: tuple[RepoReference, ...]
    core_section_labels: tuple[str, ...]
    core_repo_reference_paths: tuple[str, ...]
    model_extra_reads: tuple[str, ...]
    scope_note: str | None
    fallback_reason: str | None
    selection_mode: str
    spec_candidates: tuple[SpecCandidate, ...]
    missing_signals: tuple[str, ...]
    repo_context_gap: tuple[str, ...]
    model_resolution: dict[str, Any] | None


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
    budget_status: str = "not_applicable"
    budget_limit_bytes: int | None = None
    trimmed_sections: tuple[TrimmedSection, ...] = ()

    @property
    def byte_estimate(self) -> int:
        header = len(self.template.encode("utf-8"))
        note = len((self.scope_note or "").encode("utf-8"))
        body = sum(section.byte_count for section in self.sections)
        labels = sum(len(section.label.encode("utf-8")) for section in self.sections)
        refs = sum(ref.byte_count for ref in self.repo_references)
        return header + note + body + labels + refs

    def to_report(
        self,
        *,
        mode: str,
        change: str,
        task: str | None,
        full_change_context: bool,
        cache_layout_enabled: bool = False,
    ) -> dict[str, object]:
        static_byte_count, dynamic_byte_count = _cache_layout_byte_counts(self) if cache_layout_enabled else (None, None)
        return {
            "mode": mode,
            "change": change,
            "task": task,
            "full_change_context": full_change_context,
            "cache_layout_enabled": cache_layout_enabled,
            "static_byte_count": static_byte_count,
            "dynamic_byte_count": dynamic_byte_count,
            "selection_mode": self.selection_mode,
            "scope_note": self.scope_note,
            "fallback_reason": self.fallback_reason,
            "byte_estimate": self.byte_estimate,
            "budget_status": self.budget_status,
            "budget_limit_bytes": self.budget_limit_bytes,
            "trimmed_sections": [item.to_report() for item in self.trimmed_sections],
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
        raise PacketGenerationError(f"unknown mode '{mode}'. Valid modes: {', '.join(VALID_MODES)}")
    asset = resources.files("task_relay.assets").joinpath(f"{SKILL_NAME}/templates/{mode}.md")
    if not asset.is_file():
        raise PacketGenerationError(f"template for mode '{mode}' is missing from the package")
    return asset.read_text(encoding="utf-8")


def _inline(label: str, text: str) -> str:
    return f"### {label}\n\n```\n{text.rstrip()}\n```"


def _escape_cache_marker_text(text: str) -> str:
    return (
        text.replace(CACHE_BREAK_MARKER, "&lt;!-- trly&#58;cache_break --&gt;")
        .replace(TEMPLATE_END_MARKER, "&lt;!-- trly&#58;template_end --&gt;")
    )


def _trace_usage_value(value: object) -> int | float | None:
    return value if isinstance(value, (int, float)) else None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _is_static_cache_section(section: PacketSection) -> bool:
    if section.source.startswith("specs/"):
        return True
    if section.source in {"proposal.md", "design.md"}:
        return True
    return False


def _inline_sections(sections: tuple[PacketSection, ...]) -> list[str]:
    return [_inline(section.label, _escape_cache_marker_text(section.text)) for section in sections]


def _cache_layout_parts(plan: PacketPlan) -> tuple[list[str], list[str]]:
    static_sections = tuple(section for section in plan.sections if _is_static_cache_section(section))
    dynamic_sections = tuple(section for section in plan.sections if not _is_static_cache_section(section))

    static_parts = [_escape_cache_marker_text(plan.template.rstrip()), TEMPLATE_END_MARKER]
    if static_sections:
        static_parts.append("## Inlined Context")
        static_parts.extend(_inline_sections(static_sections))

    dynamic_parts: list[str] = []
    if dynamic_sections:
        dynamic_parts.append("## Inlined Context" if not static_sections else "## Task Context")
        dynamic_parts.extend(_inline_sections(dynamic_sections))
    if plan.scope_note:
        dynamic_parts.append(f"Scope note: {_escape_cache_marker_text(plan.scope_note)}")
    if plan.budget_status == "trimmed":
        dynamic_parts.append(f"Budget note: trimmed optional context to fit {plan.budget_limit_bytes} bytes.")
    if plan.repo_references:
        dynamic_parts.append("## Referenced Repo Context")
        dynamic_parts.extend(
            f"- `{ref.path}` ({_escape_cache_marker_text(ref.reason)}; source: {ref.source})"
            for ref in plan.repo_references
        )
    return static_parts, dynamic_parts


def _cache_layout_byte_counts(plan: PacketPlan) -> tuple[int, int]:
    static_parts, dynamic_parts = _cache_layout_parts(plan)
    static_text = "\n\n".join(static_parts)
    dynamic_text = "\n\n".join(dynamic_parts)
    return len(static_text.encode("utf-8")), len(dynamic_text.encode("utf-8"))


def _build_flat_packet(plan: PacketPlan) -> str:
    parts = [_escape_cache_marker_text(plan.template.rstrip())]
    if plan.scope_note:
        parts.append(f"Scope note: {_escape_cache_marker_text(plan.scope_note)}")
    if plan.budget_status == "trimmed":
        parts.append(f"Budget note: trimmed optional context to fit {plan.budget_limit_bytes} bytes.")
    if plan.repo_references:
        parts.append("## Referenced Repo Context")
        parts.extend(
            f"- `{ref.path}` ({_escape_cache_marker_text(ref.reason)}; source: {ref.source})"
            for ref in plan.repo_references
        )
    parts.append("## Inlined Context")
    parts.extend(_inline_sections(plan.sections))
    return "\n\n".join(parts) + "\n"


def _build_cache_packet(plan: PacketPlan) -> str:
    static_parts, dynamic_parts = _cache_layout_parts(plan)
    parts = [*static_parts, CACHE_BREAK_MARKER, *dynamic_parts]
    return "\n\n".join(parts) + "\n"


def _heading_match(line: str) -> re.Match[str] | None:
    return re.match(r"^(#{1,6})\s+(.*)$", line)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


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
                f"packer sidecar {path} must contain JSON syntax. "
                "This release does not accept general YAML in `packer.yml` or `packer.yaml`. "
                f"Migration: rewrite the file as JSON. Parse error: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise PacketGenerationError(f"packer sidecar {path} must contain a JSON object")
        return PackerSignals(path=path, raw=payload)
    return PackerSignals(path=None, raw={})


def _extract_design_sections(path: Path, titles: tuple[str, ...] | list[str] | None = None) -> list[PacketSection]:
    lines = _read_text(path).splitlines()
    target_titles = tuple(titles) if titles is not None else _DEFAULT_DESIGN_SECTION_TITLES
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
        sections.append(PacketSection(label=f"design.md :: {targets[normalized]}", text=block, source="design.md"))
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
    scores.sort(key=lambda item: (-item[0], str(item[1])))
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


def _normalized_unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)


def _core_spec_paths_from_scores(scores: list[tuple[int, Path]], selected: tuple[str, ...], change_dir: Path) -> tuple[str, ...]:
    if not selected:
        return ()
    selected_set = set(selected)
    ranked = [
        (score, str(spec.relative_to(change_dir)))
        for score, spec in scores
        if str(spec.relative_to(change_dir)) in selected_set
    ]
    if not ranked:
        return ()
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return (ranked[0][1],)


def _merge_model_resolution(base: dict[str, Any] | None, updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in updates.items():
        if key == "accepted_fields" and isinstance(value, list):
            merged[key] = sorted(set(merged.get(key, [])) | set(value))
        elif key == "rejected_fields" and isinstance(value, list):
            merged[key] = sorted(set(merged.get(key, [])) | set(value))
        else:
            merged[key] = value
    return merged


def _select_explicit_specs(change_dir: Path, task_signal: dict[str, Any], scores: list[tuple[int, Path]]) -> SpecSelection | None:
    capability = task_signal.get("capability")
    if not isinstance(capability, str) or not capability.strip():
        return None
    spec = change_dir / "specs" / capability.strip() / "spec.md"
    if not spec.is_file():
        return SpecSelection(
            sections=tuple(_all_spec_sections(change_dir)),
            candidates=_candidate_reports(scores, change_dir),
            core_spec_paths=(),
            scope_note=f"declared capability '{capability}' did not resolve; included all delta specs.",
            fallback_reason="invalid_explicit_capability",
            selection_mode="explicit_mapping",
        )
    rel = str(spec.relative_to(change_dir))
    return SpecSelection(
        sections=(_spec_section(spec, change_dir),),
        candidates=_candidate_reports(scores, change_dir, {rel}, source="explicit_mapping"),
        core_spec_paths=(rel,),
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
            core_spec_paths=(),
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
            core_spec_paths=(rel,),
        )

    fallback_paths = tuple(str(spec.relative_to(change_dir)) for _score, spec in scores)
    fallback = SpecSelection(
        sections=tuple(_all_spec_sections(change_dir)),
        candidates=_candidate_reports(scores, change_dir),
        core_spec_paths=_core_spec_paths_from_scores(scores, fallback_paths, change_dir),
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
        model_result, call_meta = _call_model_resolver(change_dir, task_context, scores, task_id=task_id, cwd=cwd)
        if model_result is None:
            return SpecSelection(**{**fallback.__dict__, "model_resolution": call_meta})
        selected = _apply_model_selection(change_dir, scores, fallback, model_result)
        merged = _merge_model_resolution(selected.model_resolution, {"call": call_meta})
        return SpecSelection(**{**selected.__dict__, "model_resolution": merged})
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

    candidates = [{"path": str(spec.relative_to(change_dir)), "score": score} for score, spec in scores]
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
            "cache_creation_input_tokens": _trace_usage_value(getattr(usage, "cache_creation_input_tokens", None)) if usage else None,
            "cache_read_input_tokens": _trace_usage_value(getattr(usage, "cache_read_input_tokens", None)) if usage else None,
            "retries": result.retries if result is not None else 0,
            "error": error,
        }, cwd=cwd)


def _apply_model_selection(
    change_dir: Path,
    scores: list[tuple[int, Path]],
    fallback: SpecSelection,
    model_result: dict[str, Any],
) -> SpecSelection:
    unknown_fields = sorted(set(model_result) - _MODEL_SELECTOR_FIELDS)
    if unknown_fields:
        return SpecSelection(
            **{
                **fallback.__dict__,
                "model_resolution": {
                    "status": "rejected",
                    "reason": "unsupported_selector",
                    "rejected_fields": unknown_fields,
                },
            }
        )

    score_by_rel = {str(spec.relative_to(change_dir)): score for score, spec in scores}
    specs = _normalized_unique(_coerce_list(model_result.get("specs")))
    invalid_specs = [spec for spec in specs if spec not in score_by_rel]
    if invalid_specs:
        return SpecSelection(
            **{
                **fallback.__dict__,
                "model_resolution": {
                    "status": "rejected",
                    "reason": "invalid_pick",
                    "rejected_fields": ["specs"],
                    "invalid": invalid_specs,
                },
            }
        )

    design_sections = _normalized_unique(_coerce_list(model_result.get("design_sections")))
    task_dependencies = _normalized_unique(_coerce_list(model_result.get("task_dependencies")))
    extra_reads = _normalized_unique(_coerce_list(model_result.get("extra_reads")))
    grounded_specs = tuple(spec for spec in specs if score_by_rel.get(spec, 0) > 0)
    has_semantic_fields = bool(design_sections or task_dependencies or extra_reads)
    if specs and not grounded_specs:
        return SpecSelection(
            **{
                **fallback.__dict__,
                "model_resolution": {
                    "status": "rejected",
                    "reason": "unsupported_pick",
                    "rejected_fields": ["specs"],
                },
            }
        )
    if not grounded_specs and not has_semantic_fields:
        return SpecSelection(
            **{
                **fallback.__dict__,
                "model_resolution": {
                    "status": "rejected",
                    "reason": "empty_selection",
                    "rejected_fields": [],
                },
            }
        )

    selected_spec_set = set(grounded_specs) if grounded_specs else {candidate.path for candidate in fallback.candidates if candidate.selected}
    if grounded_specs:
        sections = tuple(_spec_section(change_dir / spec, change_dir) for spec in grounded_specs)
        candidates = _candidate_reports(scores, change_dir, set(grounded_specs), source="model_fallback")
        selection_mode = "model_fallback"
        core_spec_paths = _core_spec_paths_from_scores(scores, grounded_specs, change_dir)
    else:
        sections = fallback.sections
        candidates = fallback.candidates
        selection_mode = fallback.selection_mode
        core_spec_paths = fallback.core_spec_paths

    accepted_fields: list[str] = []
    if grounded_specs:
        accepted_fields.append("specs")
    if design_sections:
        accepted_fields.append("design_sections")
    if task_dependencies:
        accepted_fields.append("task_dependencies")
    if extra_reads:
        accepted_fields.append("extra_reads")

    return SpecSelection(
        sections=sections,
        candidates=candidates,
        design_section_titles=design_sections,
        task_dependencies=task_dependencies,
        extra_reads=extra_reads,
        core_spec_paths=core_spec_paths,
        scope_note=fallback.scope_note if not grounded_specs else None,
        fallback_reason=fallback.fallback_reason if not grounded_specs else None,
        selection_mode=selection_mode,
        model_resolution={
            "status": "accepted",
            "reason": str(model_result.get("reason") or "model selected grounded candidates"),
            "accepted_fields": sorted(accepted_fields),
            "selected_specs": sorted(selected_spec_set),
            "rejected_fields": [],
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


def _task_dependencies(tasks_path: Path, dependencies: tuple[str, ...]) -> tuple[PacketSection, ...]:
    sections: list[PacketSection] = []
    for dep in dependencies:
        section, _heading = _extract_task_block(tasks_path, dep)
        if section is not None:
            sections.append(PacketSection(label=f"dependency {section.label}", text=section.text, source=section.source))
    return tuple(sections)


def _dynamic_diff_paths(base: Path, *, diff_file: str | None = None, diff_from: str | None = None) -> tuple[list[str], str | None]:
    if diff_file:
        path = Path(diff_file)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            raise PacketGenerationError(f"diff file '{diff_file}' could not be resolved at {path}")
        return _paths_from_diff_text(_read_text(path)), f"diff_file:{diff_file}"
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
    return list(_normalized_unique(paths))


def _merge_unique(primary: tuple[str, ...], secondary: tuple[str, ...]) -> tuple[str, ...]:
    return _normalized_unique(list(primary) + list(secondary))


def _scoped_sections(
    change_dir: Path,
    task: str | None,
    *,
    base: Path,
    signals: PackerSignals,
    dynamic_repo_files: list[str] | None = None,
    model_resolver_enabled: bool = False,
    model_result: dict[str, Any] | None = None,
    model_call_limit: int = 1,
) -> SelectionResult:
    sections: list[PacketSection] = []
    repo_refs: list[RepoReference] = []
    missing_signals: list[str] = []
    repo_context_gap: list[str] = []
    core_section_labels: list[str] = []
    core_repo_reference_paths: list[str] = []

    task_signal = signals.for_task(task)
    proposal = change_dir / "proposal.md"
    if task is None and proposal.is_file():
        proposal_section = PacketSection(label="proposal.md", text=_read_text(proposal), source="proposal.md")
        sections.append(proposal_section)
        core_section_labels.append(proposal_section.label)

    tasks_path = change_dir / "tasks.md"
    heading_title = None
    task_text = ""
    task_dependencies = _normalized_unique(_coerce_list(task_signal.get("dependencies")))
    if tasks_path.is_file():
        task_section, heading_title = _extract_task_block(tasks_path, task)
        if task_section is not None:
            sections.append(task_section)
            core_section_labels.append(task_section.label)
            task_text = task_section.text

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

    merged_dependencies = _merge_unique(task_dependencies, spec_selection.task_dependencies)
    if tasks_path.is_file():
        dependency_sections = _task_dependencies(tasks_path, merged_dependencies)
        sections.extend(dependency_sections)
        core_section_labels.extend(section.label for section in dependency_sections)

    design_titles = _merge_unique(_DEFAULT_DESIGN_SECTION_TITLES, _coerce_list(task_signal.get("design_sections")))
    design_titles = _merge_unique(design_titles, spec_selection.design_section_titles)
    design_path = change_dir / "design.md"
    if design_path.is_file():
        design_sections = _extract_design_sections(design_path, design_titles)
        sections.extend(design_sections)

    sections.extend(spec_selection.sections)
    core_section_labels.extend(section.label for section in spec_selection.sections if section.source in set(spec_selection.core_spec_paths))

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
            core_repo_reference_paths.append(ref.path)

    for rel in dynamic_repo_files or []:
        ref, missing = _resolve_repo_reference(base, rel, "dynamic_diff", "changed file from explicit diff source")
        if ref is None:
            repo_context_gap.append(missing or rel)
        else:
            repo_refs.append(ref)

    return SelectionResult(
        sections=tuple(sections),
        repo_references=tuple(repo_refs),
        core_section_labels=tuple(_normalized_unique(core_section_labels)),
        core_repo_reference_paths=tuple(_normalized_unique(core_repo_reference_paths)),
        model_extra_reads=spec_selection.extra_reads,
        scope_note=spec_selection.scope_note,
        fallback_reason=spec_selection.fallback_reason,
        selection_mode=spec_selection.selection_mode,
        spec_candidates=spec_selection.candidates,
        missing_signals=tuple(missing_signals),
        repo_context_gap=tuple(repo_context_gap),
        model_resolution=spec_selection.model_resolution,
    )


def _resolve_extra_read_sections(base: Path, reads: tuple[str, ...], *, source: str) -> tuple[list[PacketSection], list[str]]:
    sections: list[PacketSection] = []
    missing: list[str] = []
    for read in reads:
        path = Path(read)
        if not path.is_absolute():
            path = base / path
        if not path.is_file():
            missing.append(read)
            continue
        label = read
        sections.append(PacketSection(label=label, text=_read_text(path), source=source))
    return sections, missing


def _resolve_budget_limit(mode: str, signals: PackerSignals) -> int:
    raw = signals.raw.get("budget_bytes")
    if raw is None:
        return _MODE_BUDGET_BYTES[mode]
    try:
        limit = int(raw)
    except (TypeError, ValueError) as exc:
        raise PacketGenerationError(f"sidecar budget_bytes must be an integer, got {raw!r}") from exc
    if limit <= 0:
        raise PacketGenerationError("sidecar budget_bytes must be positive")
    return limit


def _estimated_tokens(byte_count: int) -> int:
    return max(1, round(byte_count / 4)) if byte_count > 0 else 0


def _section_removal_priority(section: PacketSection, core_labels: set[str], score_by_spec: dict[str, int]) -> tuple[int, int, str]:
    if section.label in core_labels:
        return (999, 0, section.label)
    if section.source == "extra_read:model":
        return (0, 0, section.label)
    if section.source == "extra_read:cli":
        return (1, 0, section.label)
    if section.source == "design.md":
        return (3, 0, section.label)
    if section.source.startswith("specs/"):
        return (4, score_by_spec.get(section.source, 0), section.source)
    return (998, 0, section.label)


def _repo_ref_removal_priority(ref: RepoReference, core_paths: set[str]) -> tuple[int, str]:
    if ref.path in core_paths:
        return (999, ref.path)
    if ref.source == "dynamic_diff":
        return (2, ref.path)
    return (998, ref.path)


def _packet_byte_estimate(template: str, scope_note: str | None, sections: list[PacketSection], repo_references: list[RepoReference]) -> int:
    header = len(template.encode("utf-8"))
    note = len((scope_note or "").encode("utf-8"))
    body = sum(section.byte_count + len(section.label.encode("utf-8")) for section in sections)
    refs = sum(ref.byte_count for ref in repo_references)
    return header + note + body + refs


def _apply_budget(
    *,
    template: str,
    scope_note: str | None,
    sections: tuple[PacketSection, ...],
    repo_references: tuple[RepoReference, ...],
    core_section_labels: tuple[str, ...],
    core_repo_reference_paths: tuple[str, ...],
    budget_limit_bytes: int,
    spec_candidates: tuple[SpecCandidate, ...],
) -> tuple[tuple[PacketSection, ...], tuple[RepoReference, ...], str, tuple[TrimmedSection, ...]]:
    current_sections = list(sections)
    current_refs = list(repo_references)
    if _packet_byte_estimate(template, scope_note, current_sections, current_refs) <= budget_limit_bytes:
        return tuple(current_sections), tuple(current_refs), "within_budget", ()

    core_labels = set(core_section_labels)
    core_paths = set(core_repo_reference_paths)
    score_by_spec = {candidate.path: candidate.score for candidate in spec_candidates}
    trimmed: list[TrimmedSection] = []

    removable_items: list[tuple[tuple[int, int, str], str, PacketSection | RepoReference]] = []
    removable_items.extend(
        (
            _section_removal_priority(section, core_labels, score_by_spec),
            "section",
            section,
        )
        for section in current_sections
        if section.label not in core_labels
    )
    removable_items.extend(
        (
            (_repo_ref_removal_priority(ref, core_paths)[0], 0, _repo_ref_removal_priority(ref, core_paths)[1]),
            "ref",
            ref,
        )
        for ref in current_refs
        if ref.path not in core_paths
    )
    removable_items.sort(key=lambda item: item[0])

    for _priority, kind, value in removable_items:
        if _packet_byte_estimate(template, scope_note, current_sections, current_refs) <= budget_limit_bytes:
            break
        if kind == "section":
            section = value
            if section not in current_sections:
                continue
            current_sections.remove(section)
            trimmed.append(TrimmedSection(label=section.label, source=section.source, bytes=section.byte_count, reason="budget_trim"))
            continue
        ref = value
        if ref not in current_refs:
            continue
        current_refs.remove(ref)
        trimmed.append(TrimmedSection(label=ref.path, source=ref.source, bytes=ref.byte_count, reason="budget_trim"))

    status = "trimmed" if _packet_byte_estimate(template, scope_note, current_sections, current_refs) <= budget_limit_bytes else "violation"
    return tuple(current_sections), tuple(current_refs), status, tuple(trimmed)


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

    if full_change_context:
        sections = tuple(_full_change_sections(change_dir))
        repo_refs: tuple[RepoReference, ...] = ()
        scope_note = None
        fallback_reason = None
        selection_mode = "full_change_context"
        spec_candidates: tuple[SpecCandidate, ...] = ()
        missing_signals: tuple[str, ...] = ()
        repo_context_gap: tuple[str, ...] = ()
        model_resolution = None
        budget_status = "not_applicable"
        budget_limit_bytes = None
        trimmed_sections: tuple[TrimmedSection, ...] = ()
    else:
        selection = _scoped_sections(
            change_dir,
            task,
            base=base,
            signals=signals,
            dynamic_repo_files=dynamic_files,
            model_resolver_enabled=model_resolver_enabled,
            model_result=model_result,
            model_call_limit=model_call_limit,
        )
        sections = selection.sections
        repo_refs = selection.repo_references
        scope_note = selection.scope_note
        fallback_reason = selection.fallback_reason
        selection_mode = selection.selection_mode
        spec_candidates = selection.spec_candidates
        missing_signals = selection.missing_signals
        repo_context_gap = list(selection.repo_context_gap)
        model_resolution = selection.model_resolution

        model_extra_sections, missing_model_reads = _resolve_extra_read_sections(base, selection.model_extra_reads, source="extra_read:model")
        cli_extra_sections, missing_cli_reads = _resolve_extra_read_sections(base, _normalized_unique(extra_reads or []), source="extra_read:cli")
        repo_context_gap.extend(missing_model_reads)
        if missing_model_reads:
            model_resolution = _merge_model_resolution(model_resolution, {
                "status": "rejected" if not model_extra_sections else model_resolution.get("status", "accepted") if model_resolution else "accepted",
                "reason": "missing_extra_read" if not model_extra_sections else (model_resolution or {}).get("reason", "model selected grounded candidates"),
                "rejected_fields": ["extra_reads"],
                "missing_extra_reads": missing_model_reads,
            })
        if missing_cli_reads:
            raise PacketGenerationError(f"declared read(s) could not be resolved: {', '.join(missing_cli_reads)}")

        combined_sections = list(sections) + model_extra_sections + cli_extra_sections
        core_section_labels = selection.core_section_labels
        core_repo_reference_paths = selection.core_repo_reference_paths
        budget_limit_bytes = _resolve_budget_limit(mode, signals)
        trimmed_sections_list: tuple[TrimmedSection, ...]
        sections, repo_refs, budget_status, trimmed_sections_list = _apply_budget(
            template=template,
            scope_note=scope_note,
            sections=tuple(combined_sections),
            repo_references=repo_refs,
            core_section_labels=core_section_labels,
            core_repo_reference_paths=core_repo_reference_paths,
            budget_limit_bytes=budget_limit_bytes,
            spec_candidates=spec_candidates,
        )
        trimmed_sections = trimmed_sections_list

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
        sections=sections,
        repo_references=repo_refs,
        scope_note=scope_note,
        fallback_reason=fallback_reason,
        selection_mode=selection_mode,
        spec_candidates=spec_candidates,
        missing_signals=missing_signals,
        repo_context_gap=tuple(repo_context_gap),
        dynamic_diff_source=dynamic_source,
        model_resolution=model_resolution,
        resolver_cache_key=resolver_cache_key,
        budget_status=budget_status,
        budget_limit_bytes=budget_limit_bytes,
        trimmed_sections=trimmed_sections,
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
    cache_layout: bool = False,
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
    if plan.budget_status == "violation":
        raise PacketGenerationError(
            json.dumps(
                {
                    "error": "packet_budget_violation",
                    "budget_limit_bytes": plan.budget_limit_bytes,
                    "byte_estimate": plan.byte_estimate,
                },
                ensure_ascii=False,
            )
        )

    if cache_layout:
        return _build_cache_packet(plan)
    return _build_flat_packet(plan)
