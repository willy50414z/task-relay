import argparse
import sys
from pathlib import Path
from typing import Sequence

from task_relay.cli.evaluate import handle_evaluate
from task_relay.cli.health import handle_health
from task_relay.cli.run import handle_run
from task_relay.delegation import (
    InstallResult,
    clear,
    install,
    parse_existing_block,
    resolve_install_paths,
    uninstall,
)
from task_relay.wizard import run_wizard

AGENT_NAMES = ["claude", "codex", "deepseek"]


def build_parser(prog: str = "trly") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a raw prompt against an agent target.")
    add_target_args(run_parser, required=True)
    add_input_args(run_parser, "prompt")
    add_common_execution_args(run_parser)
    run_parser.set_defaults(handler=handle_run)

    evaluate_parser = subparsers.add_parser("evaluate", help="Run outcome-routed execution and emit JSON.")
    add_target_args(evaluate_parser, required=True)
    add_input_args(evaluate_parser, "purpose")
    add_common_execution_args(evaluate_parser)
    evaluate_parser.add_argument("--outcome", action="append", required=True, default=[], metavar="STATUS=DESCRIPTION")
    evaluate_parser.add_argument("--output-file", action="append", default=[], metavar="STATUS=PATH")
    evaluate_parser.add_argument("--json", action="store_true", required=True)
    evaluate_parser.set_defaults(handler=handle_evaluate)

    health_parser = subparsers.add_parser("health", help="Check agent availability.")
    health_parser.add_argument("--target", choices=AGENT_NAMES)
    health_parser.add_argument("--json", action="store_true", required=True)
    health_parser.set_defaults(handler=handle_health)

    install_parser = subparsers.add_parser("install", help="Install task-relay delegation guidance interactively.")
    install_parser.add_argument("--primary", choices=["claude", "codex"], help="Primary orchestration agent")
    install_parser.add_argument("--scope", choices=["user", "project"], help="Installation scope")
    install_parser.add_argument("--mode", choices=["main", "hybrid", "delegated-apply"], help="Delegation mode")
    install_parser.add_argument("--sub-agent", choices=["claude", "codex", "deepseek"], help="Delegation sub-agent")
    install_parser.add_argument("--model", action="append", default=[], metavar="ROLE=MODEL_ID", help="Model for a role (e.g. --model primary=claude-sonnet-4-6 --model sub=deepseek-v4-pro[1m])")
    install_parser.add_argument("--cwd", help="Working directory (project scope only)")
    install_parser.set_defaults(handler=handle_install)

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove task-relay delegation guidance.")
    uninstall_parser.add_argument("--scope", choices=["user", "project"], help="Uninstall scope (omit to detect both)")
    uninstall_parser.add_argument("--cwd", help="Working directory (project scope only)")
    uninstall_parser.set_defaults(handler=handle_uninstall)
    return parser


def add_target_args(parser: argparse.ArgumentParser, *, required: bool) -> None:
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument("--target", choices=AGENT_NAMES)
    group.add_argument("--targets", type=parse_targets, help="Comma-separated ordered fallback target list.")


def add_input_args(parser: argparse.ArgumentParser, name: str) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(f"--{name}", dest="input_text")
    group.add_argument(f"--{name}-file", dest="input_file")
    group.add_argument("--stdin", action="store_true", dest="input_stdin")


def add_common_execution_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--cwd")


def main(argv: Sequence[str] | None = None) -> int:
    return _run_main(build_parser(), argv)


def _run_main(parser: argparse.ArgumentParser, argv: Sequence[str] | None) -> int:
    try:
        args = parser.parse_args(argv)
        load_input(args)
        return args.handler(args)
    except SystemExit as exc:
        return int(exc.code)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


def load_input(args) -> None:
    if not hasattr(args, "input_text"):
        return
    if args.input_text is not None:
        return
    if args.input_file is not None:
        args.input_text = Path(args.input_file).read_text(encoding="utf-8")
        return
    if args.input_stdin:
        args.input_text = sys.stdin.read()
        return
    raise ValueError("input is required")


def parse_targets(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_models(raw: list[str]) -> dict[str, str]:
    """Parse --model ROLE=MODEL_ID entries into {role: model_id} dict."""
    models: dict[str, str] = {}
    for entry in raw:
        if "=" not in entry:
            raise ValueError(f"--model must use ROLE=MODEL_ID syntax, got: {entry}")
        role, _, model = entry.partition("=")
        role = role.strip()
        model = model.strip()
        if not role or not model:
            raise ValueError(f"--model must use ROLE=MODEL_ID syntax, got: {entry}")
        if role not in ("primary", "sub"):
            raise ValueError(f"--model role must be 'primary' or 'sub', got: {role}")
        models[role] = model
    return models


# ── Handlers ────────────────────────────────────────────────────────

def handle_install(args) -> int:
    cwd = Path(args.cwd) if args.cwd else Path.cwd()

    # Non-interactive: all required flags provided
    flags_provided = args.primary is not None
    if flags_provided and args.primary and args.scope and args.mode:
        primary = args.primary
        scope = args.scope

        if args.mode == "main":
            result = clear(primary_agent=primary, scope=scope, cwd=cwd)
            if result:
                print(f"Delegation guidance cleared: {result.guidance_path}")
            else:
                print("No managed block found to clear.")
            return 0

        # hybrid or delegated-apply: need sub-agent
        if not args.sub_agent:
            print("--sub-agent is required when mode is not 'main'", file=sys.stderr)
            return 1

        models = _parse_models(args.model)
        result = install(
            primary_agent=primary,
            scope=scope,
            mode=args.mode,
            sub_agent=args.sub_agent,
            models=models,
            cwd=cwd,
        )
        print_summary(result)
        return 0

    # Partial flags: fall back to wizard
    if flags_provided:
        print("Partial flags provided — launching interactive wizard to complete configuration.")

    # Interactive wizard
    def write_fn(state):
        install(
            primary_agent=state.primary_agent,
            scope=state.scope,
            mode=state.mode,
            sub_agent=state.sub_agent,
            models=state.models,
            cwd=state.cwd,
        )

    # Determine prefill path
    prefill_path = None
    if args.primary and args.scope:
        guidance_path, _ = resolve_install_paths(args.primary, args.scope, cwd)
        if guidance_path.exists():
            prefill_path = str(guidance_path)

    def clear_fn():
        if args.primary and args.scope:
            clear(primary_agent=args.primary, scope=args.scope, cwd=cwd)
        else:
            clear(cwd=cwd)

    return run_wizard(write_fn, clear_fn, cwd=cwd, prefill_path=prefill_path)


def handle_uninstall(args) -> int:
    cwd = Path(args.cwd) if args.cwd else Path.cwd()

    results = uninstall(scope=args.scope, cwd=cwd)
    if not results:
        print("No task-relay managed blocks found.")
        return 0

    for result in results:
        print(f"Removed delegation guidance: {result.guidance_path} (scope: {result.scope})")
    return 0


def print_summary(result: InstallResult) -> None:
    print(f"Task-relay delegation guidance {result.action}: {result.guidance_path}")
    print(f"  Primary agent : {result.primary_agent}")
    print(f"  Scope         : {result.scope}")
    print(f"  Mode          : {result.mode}")
    print(f"  Sub-agent     : {result.sub_agent}")
