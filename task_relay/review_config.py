from __future__ import annotations

from dataclasses import dataclass

DEFAULT_REVIEWER_PERSONA = "/review"
DEFAULT_ARBITER_CHAIN: tuple["ReviewRoleEntry", ...] = (
    # Default arbiters keep product arbitration ahead of engineering arbitration.
    # Model selection remains optional and can be filled by install/wizard callers.
)
DEFAULT_GLOBAL_TIMEOUT = 900


@dataclass(frozen=True)
class ReviewRoleEntry:
    agent: str
    persona: str | None = None
    model: str | None = None

    def normalized_persona(self, default: str | None = None) -> str | None:
        return self.persona or default


@dataclass(frozen=True)
class ReviewGateConfig:
    reviewers: tuple[ReviewRoleEntry, ...] = ()
    arbiters: tuple[ReviewRoleEntry, ...] = ()
    global_timeout: int = DEFAULT_GLOBAL_TIMEOUT
    legacy_review_chain: tuple[tuple[str, str | None], ...] = ()


@dataclass(frozen=True)
class ReviewSettingRow:
    role: str
    agent: str
    model: str
    effort: str
    personas: str


PERSONA_ALIASES: dict[str, str] = {
    "review": "/review",
    "cso": "/cso",
    "qa": "/qa-only",
    "qa-only": "/qa-only",
    "ceo": "/plan-ceo-review",
    "engineer": "/plan-eng-review",
    "plan-ceo-review": "/plan-ceo-review",
    "plan-eng-review": "/plan-eng-review",
}


def parse_role_entries(value: str) -> list[ReviewRoleEntry]:
    entries: list[ReviewRoleEntry] = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        model = None
        if "=" in entry:
            entry, _, raw_model = entry.partition("=")
            model = raw_model.strip() or None
        agent, persona = _split_agent_persona(entry.strip())
        entries.append(ReviewRoleEntry(agent=agent, persona=persona, model=model))
    return entries


def format_role_entries(entries: list[ReviewRoleEntry] | tuple[ReviewRoleEntry, ...]) -> str:
    formatted: list[str] = []
    for entry in entries:
        value = entry.agent
        if entry.persona:
            value = f"{value}:{entry.persona}"
        if entry.model:
            value = f"{value}={entry.model}"
        formatted.append(value)
    return ", ".join(formatted)


def normalize_persona_alias(value: str) -> str:
    persona = value.strip()
    if not persona:
        raise ValueError("persona cannot be empty")
    key = persona.removeprefix("/").strip()
    if not key:
        raise ValueError("persona cannot be a bare slash")
    return PERSONA_ALIASES.get(key, f"/{key}")


def review_setting_rows(config: ReviewGateConfig) -> list[ReviewSettingRow]:
    rows: list[ReviewSettingRow] = []
    rows.extend(_entry_rows("reviewer", config.reviewers))
    rows.extend(_entry_rows("arbiter", config.arbiters))
    return rows


def format_review_setting_table(config: ReviewGateConfig) -> str:
    lines = [
        "| Role | Agent | Model | Effort | Personas |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in review_setting_rows(config):
        lines.append(f"| {row.role} | {row.agent} | {row.model} | {row.effort} | {row.personas} |")
    return "\n".join(lines)


def migrate_legacy_review_chain(
    review_chain: list[tuple[str, str | None]] | tuple[tuple[str, str | None], ...],
) -> list[ReviewRoleEntry]:
    if not review_chain:
        return []
    agent, model = review_chain[0]
    return [ReviewRoleEntry(agent=agent, persona=DEFAULT_REVIEWER_PERSONA, model=model)]


def default_arbiter_entries() -> list[ReviewRoleEntry]:
    return [
        ReviewRoleEntry(agent="claude", persona="/plan-ceo-review"),
        ReviewRoleEntry(agent="claude", persona="/plan-eng-review"),
    ]


def _split_agent_persona(entry: str) -> tuple[str, str | None]:
    if ":" not in entry:
        agent = entry.strip()
        if not agent:
            raise ValueError(f"invalid role entry: {entry!r}")
        return agent, None
    agent, _, raw_persona = entry.partition(":")
    agent = agent.strip()
    persona = raw_persona.strip()
    if not agent:
        raise ValueError(f"invalid role entry: {entry!r}")
    if not persona:
        raise ValueError(f"invalid role entry: {entry!r}")
    return agent, normalize_persona_alias(persona)


def _entry_rows(role: str, entries: tuple[ReviewRoleEntry, ...]) -> list[ReviewSettingRow]:
    return [
        ReviewSettingRow(
            role=role,
            agent=entry.agent,
            model=_display_model(entry),
            effort=_display_effort(entry),
            personas=_display_persona(entry.persona),
        )
        for entry in entries
    ]


def _display_model(entry: ReviewRoleEntry) -> str:
    model = entry.model or "default"
    if entry.agent == "codex":
        base, effort = _split_codex_effort(model)
        if effort:
            return base
    return model


def _display_effort(entry: ReviewRoleEntry) -> str:
    if entry.agent != "codex" or not entry.model:
        return "n/a"
    _, effort = _split_codex_effort(entry.model)
    return effort or "n/a"


def _display_persona(persona: str | None) -> str:
    return (persona or DEFAULT_REVIEWER_PERSONA).removeprefix("/")


def _split_codex_effort(model: str) -> tuple[str, str | None]:
    base, sep, suffix = model.rpartition("-")
    if sep and suffix in {"high", "medium", "fast"} and base:
        return base, suffix
    return model, None
