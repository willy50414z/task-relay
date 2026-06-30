from argparse import Namespace
import json
import sys
from pathlib import Path

from task_relay.packer import build_packet, plan_packet
from task_relay.packer_eval import run_context_benchmark, run_eval_set


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
                cache_layout_enabled=getattr(args, "cache_layout", False),
            ),
            ensure_ascii=False,
            indent=2,
        ))
        sys.stdout.write("\n")
        return 0

    packet = build_packet(**common, cache_layout=getattr(args, "cache_layout", False))
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


def handle_pack_benchmark(args: Namespace) -> int:
    report = run_context_benchmark(args.eval_set, cwd=args.cwd)
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
    report = plan.to_report(
        mode=args.mode,
        change=args.change,
        task=args.task,
        full_change_context=False,
        cache_layout_enabled=getattr(args, "cache_layout", False),
    )
    diagnostics: list[dict[str, object]] = []
    for signal in report["missing_signals"]:
        diagnostics.append({"severity": "warning", "code": "missing_signal", "detail": signal})
    for gap in report["repo_context_gap"]:
        diagnostics.append({"severity": "warning", "code": "repo_context_gap", "detail": gap})
    if report.get("fallback_reason"):
        severity = "error" if report["fallback_reason"] == "unresolved_capability_relevance" else "warning"
        diagnostics.append({"severity": severity, "code": "fallback", "detail": report["fallback_reason"]})
    if report.get("budget_status") == "trimmed":
        diagnostics.append({
            "severity": "warning",
            "code": "budget_trimmed",
            "detail": f"optional context trimmed to fit {report.get('budget_limit_bytes')} bytes",
        })
    if report.get("budget_status") == "violation":
        diagnostics.append({
            "severity": "error",
            "code": "budget_violation",
            "detail": f"core context exceeds {report.get('budget_limit_bytes')} byte budget",
        })
    model_resolution = report.get("model_resolution") or {}
    if isinstance(model_resolution, dict) and model_resolution.get("status") == "rejected":
        diagnostics.append({
            "severity": "warning",
            "code": "model_selection_rejected",
            "detail": str(model_resolution.get("reason") or "rejected"),
        })
    sidecar_hint = _sidecar_hint(args.change, args.cwd)
    if sidecar_hint is not None:
        diagnostics.append(sidecar_hint)
    payload = {
        "change": args.change,
        "task": args.task,
        "advisory": True,
        "diagnostics": diagnostics,
        "blocked": any(item["severity"] == "error" for item in diagnostics),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


def _load_model_result(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sidecar_hint(change: str, cwd: str | None) -> dict[str, object] | None:
    base = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    change_dir = base / "openspec" / "changes" / change
    for name in ("packer.yml", "packer.yaml"):
        path = change_dir / name
        if path.is_file():
            return {
                "severity": "info",
                "code": "json_only_sidecar",
                "detail": f"{name} is accepted as a filename, but the file content must still be JSON syntax",
            }
    return None
