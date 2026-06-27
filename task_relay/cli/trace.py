from __future__ import annotations

from argparse import Namespace

from task_relay.trace import format_summary, load_trace_records, resolve_trace_path, summarize_trace_records


def handle_trace(args: Namespace) -> int:
    if not getattr(args, "summary", False):
        raise ValueError("trace currently supports only --summary")
    path = resolve_trace_path(args.cwd)
    records = load_trace_records(path)
    summary = summarize_trace_records(records, change=getattr(args, "change", None))
    print(format_summary(summary))
    return 0
