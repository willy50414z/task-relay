from argparse import Namespace
import json
import sys
from pathlib import Path

from task_relay.packer import build_packet, plan_packet
from task_relay.packer_eval import run_eval_set


def handle_pack(args: Namespace) -> int:
    if getattr(args, "json", False) and not getattr(args, "dry_run", False):
        raise ValueError("--json requires --dry-run for trly pack")

    model_result = _load_model_result(getattr(args, "model_result", None))
    common = dict(
        mode=args.mode,
        change=args.change,
        task=args.task,
        cwd=args.cwd,
        extra_reads=getattr(args, "extra_reads", None) or None,
        full_change_context=getattr(args, "full_change_context", False),
        diff_file=getattr(args, "diff_file", None),
        diff_from=getattr(args, "diff_from", None),
        model_resolver_enabled=getattr(args, "model_resolver", False),
        model_result=model_result,
        model_call_limit=getattr(args, "model_call_limit", 1),
    )

    if getattr(args, "dry_run", False):
        plan = plan_packet(**common)
        if not getattr(args, "json", False):
            raise ValueError("--dry-run currently requires --json")
        sys.stdout.write(json.dumps(
            plan.to_report(
                mode=args.mode,
                change=args.change,
                task=args.task,
                full_change_context=getattr(args, "full_change_context", False),
            ),
            ensure_ascii=False,
            indent=2,
        ))
        sys.stdout.write("\n")
        return 0

    packet = build_packet(**common)
    if args.out:
        Path(args.out).write_text(packet, encoding="utf-8")
        sys.stderr.write(f"[task-relay] packet written to {args.out}\n")
    else:
        sys.stdout.write(packet)
    return 0


def handle_pack_metrics(args: Namespace) -> int:
    report = run_eval_set(args.eval_set, cwd=args.cwd)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


def handle_pack_lint(args: Namespace) -> int:
    plan = plan_packet(
        mode=args.mode,
        change=args.change,
        task=args.task,
        cwd=args.cwd,
        full_change_context=False,
    )
    report = plan.to_report(mode=args.mode, change=args.change, task=args.task, full_change_context=False)
    diagnostics: list[dict[str, object]] = []
    for signal in report["missing_signals"]:
        diagnostics.append({"severity": "warning", "code": "missing_signal", "detail": signal})
    for gap in report["repo_context_gap"]:
        diagnostics.append({"severity": "warning", "code": "repo_context_gap", "detail": gap})
    if report.get("fallback_reason"):
        diagnostics.append({"severity": "warning", "code": "fallback", "detail": report["fallback_reason"]})
    payload = {
        "change": args.change,
        "task": args.task,
        "advisory": True,
        "diagnostics": diagnostics,
        "blocked": False,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


def _load_model_result(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))
