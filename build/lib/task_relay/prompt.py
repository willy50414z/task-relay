from pathlib import Path

from task_relay.types import Outcome, effective_status


def build_prompt(purpose: str, outcomes: list[Outcome], workspace: Path | None = None) -> str:
    outcome_lines: list[str] = []
    for index, outcome in enumerate(outcomes):
        status = effective_status(outcome, index)
        if not outcome.output_files or status == "error":
            continue
        outcome_lines.append(f'If the outcome is "{status}" ({outcome.description}), write:')
        for filename in outcome.output_files:
            path = (workspace / filename).resolve() if workspace else Path(filename)
            outcome_lines.append(f"  {path}")
        outcome_lines.append("")
    if not outcome_lines:
        return purpose
    return "\n".join([purpose, "", "---", "", *outcome_lines]).rstrip()
