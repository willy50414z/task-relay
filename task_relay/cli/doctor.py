from __future__ import annotations

import json
from argparse import Namespace

from task_relay.doctor import build_doctor_report, format_doctor_report


def handle_doctor(args: Namespace) -> int:
    report = build_doctor_report(
        cwd=getattr(args, "cwd", None),
        target_agents=getattr(args, "targets", None),
        scope=getattr(args, "scope", None),
    )
    if getattr(args, "json", False):
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_doctor_report(report))
    return 0 if report.ok else 1
