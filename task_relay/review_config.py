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
    if not persona.startswith("/"):
        persona = f"/{persona}"
    return agent, persona
