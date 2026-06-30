from __future__ import annotations

from argparse import Namespace
import time

from task_relay import jobs


def handle_jobs(args: Namespace) -> int:
    action = getattr(args, "jobs_command", None)
    if action == "list":
        return _handle_list(args)
    if action == "status":
        return _handle_status(args)
    if action == "logs":
        return _handle_logs(args)
    if action == "stop":
        return _handle_stop(args)
    if action == "cleanup":
        return _handle_cleanup(args)
    raise ValueError("jobs subcommand is required")


def _handle_list(args: Namespace) -> int:
    records = jobs.list_jobs(cwd=getattr(args, "cwd", None))
    if not records:
        print("no jobs")
        return 0
    for record in records:
        if isinstance(record, dict):
            print(f"{record.get('id')} unreadable {record.get('error')}")
            continue
        age = _format_age(record.started_at)
        label = record.role or "-"
        change = record.change or "-"
        print(
            f"{record.job_id}\t{record.status}\t{record.target or '-'}\t"
            f"{label}\t{change}\t{age}\t{record.log_path}"
        )
    return 0


def _handle_status(args: Namespace) -> int:
    record = jobs.status(args.job_id, cwd=getattr(args, "cwd", None))
    fields = [
        ("id", record.job_id),
        ("status", record.status),
        ("pid", record.pid),
        ("exit_code", record.returncode),
        ("target", record.target),
        ("model", record.model),
        ("role", record.role),
        ("change", record.change),
        ("task", record.task),
        ("started_at", _format_ts(record.started_at)),
        ("ended_at", _format_ts(record.ended_at)),
        ("last_output_at", _format_ts(record.last_output_at)),
        ("log", record.log_path),
        ("stdout_log", record.stdout_log_path),
        ("stderr_log", record.stderr_log_path),
        ("expected_outputs", ", ".join(record.expected_outputs) if record.expected_outputs else "-"),
        ("error", record.error),
    ]
    for key, value in fields:
        print(f"{key}: {value if value is not None else '-'}")
    return 0


def _handle_logs(args: Namespace) -> int:
    if getattr(args, "follow", False):
        try:
            for chunk in jobs.follow_logs(args.job_id, cwd=getattr(args, "cwd", None), stream=args.stream):
                print(chunk, end="")
        except KeyboardInterrupt:
            return 130
        return 0
    print(
        jobs.logs(
            args.job_id,
            cwd=getattr(args, "cwd", None),
            stream=args.stream,
            tail=getattr(args, "tail", None),
        ),
        end="",
    )
    return 0


def _handle_stop(args: Namespace) -> int:
    record = jobs.stop(args.job_id, cwd=getattr(args, "cwd", None))
    print(f"{record.job_id}: {record.status}")
    return 0


def _handle_cleanup(args: Namespace) -> int:
    count = jobs.cleanup(
        cwd=getattr(args, "cwd", None),
        older_than_days=getattr(args, "older_than", 7),
        status_filter=getattr(args, "status", None),
    )
    print(f"removed jobs: {count}")
    return 0


def _format_age(started_at: float | None) -> str:
    if started_at is None:
        return "-"
    return f"{time.time() - started_at:.0f}s"


def _format_ts(value: float | None) -> str:
    if value is None:
        return "-"
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(value))
