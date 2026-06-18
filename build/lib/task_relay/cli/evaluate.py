import json
from argparse import Namespace

from task_relay.core import evaluate_result
from task_relay.types import JobResult, Outcome


def handle_evaluate(args: Namespace) -> int:
    outcomes = parse_outcomes(args.outcome, args.output_file)
    result = evaluate_result(
        args.targets if args.targets is not None else [args.target],
        args.input_text,
        outcomes,
        model=args.model,
        effort=args.effort,
        timeout=args.timeout,
        cwd=args.cwd,
    )
    print(json.dumps(job_result_to_json(result), sort_keys=True))
    return 0


def parse_outcomes(outcome_values: list[str], output_file_values: list[str]) -> list[Outcome]:
    output_files_by_status: dict[str, list[str]] = {}
    for value in output_file_values:
        status, path = parse_assignment(value, "--output-file")
        output_files_by_status.setdefault(status, []).append(path)

    outcomes: list[Outcome] = []
    seen: set[str] = set()
    for value in outcome_values:
        status, description = parse_assignment(value, "--outcome")
        if status in seen:
            raise ValueError(f"duplicate outcome status: {status}")
        seen.add(status)
        outcomes.append(
            Outcome(
                status=status,
                description=description,
                callback=lambda result: None,
                output_files=output_files_by_status.pop(status, None),
            )
        )
    if output_files_by_status:
        unknown = ", ".join(sorted(output_files_by_status))
        raise ValueError(f"--output-file references unknown outcome status: {unknown}")
    return outcomes


def parse_assignment(value: str, flag_name: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"{flag_name} must use STATUS=VALUE syntax")
    key, parsed_value = value.split("=", 1)
    key = key.strip()
    parsed_value = parsed_value.strip()
    if not key or not parsed_value:
        raise ValueError(f"{flag_name} must use STATUS=VALUE syntax")
    return key, parsed_value


def job_result_to_json(result: JobResult) -> dict[str, object]:
    return {
        "status": result.status,
        "target": result.target,
        "duration_seconds": result.duration_seconds,
        "stdout": result.stdout,
        "files": {name: content.decode("utf-8", errors="replace") for name, content in result.files.items()},
    }
