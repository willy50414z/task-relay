import argparse
import sys
from pathlib import Path
from typing import Sequence

from task_relay.cli.evaluate import handle_evaluate
from task_relay.cli.health import handle_health
from task_relay.cli.run import handle_run
from task_relay.delegation import install_project_guidance, uninstall_project_guidance

AGENT_NAMES = ["claude", "codex", "deepseek"]
LEVEL_TO_MODE = {1: "hybrid", 2: "delegated-apply"}


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

    install_parser = subparsers.add_parser("install", help="Install project-local OpenSpec delegation guidance.")
    add_install_args(install_parser)
    install_parser.set_defaults(handler=handle_install)

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove project-local OpenSpec delegation guidance.")
    uninstall_parser.add_argument("--cwd")
    uninstall_parser.set_defaults(handler=handle_uninstall)
    return parser


def compat_build_parser() -> argparse.ArgumentParser:
    parser = build_parser("agent-dispatch")
    compat_install = parser._subparsers._group_actions[0].add_parser("install_delegant", help="Compatibility install command.")
    add_install_args(compat_install)
    compat_install.add_argument("--uninstall", action="store_true")
    compat_install.set_defaults(handler=handle_compat_install)
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


def add_install_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["main", "hybrid", "delegated-apply"])
    parser.add_argument("--level", type=int, choices=[1, 2])
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--cwd")


def main(argv: Sequence[str] | None = None) -> int:
    return _run_main(build_parser(), argv)


def compat_main(argv: Sequence[str] | None = None) -> int:
    print("agent-dispatch is deprecated; use trly instead.", file=sys.stderr)
    return _run_main(compat_build_parser(), argv)


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


def resolve_mode(args) -> str:
    if args.level is not None:
        mapped = LEVEL_TO_MODE[args.level]
        if args.mode is not None and args.mode != mapped:
            raise ValueError(
                f"--mode {args.mode} and --level {args.level} are incompatible. Level {args.level} maps to '{mapped}'. Use only --mode."
            )
        return mapped
    if args.mode is not None:
        return args.mode
    if args.yes:
        return "hybrid"
    if not sys.stdin.isatty():
        raise ValueError("install requires --mode in non-interactive mode. Use --yes for the recommended hybrid default.")
    print("Select OpenSpec delegation mode:")
    print("A) main - all apply work stays with the main model")
    print("B) hybrid - main model plans/integrates/validates; submodels handle bounded work (recommended)")
    print("C) delegated-apply - main model delegates apply to a submodel and verifies completion")
    choice = input("Mode [A/B/C]: ").strip().upper()
    if choice == "A":
        return "main"
    if choice == "B":
        return "hybrid"
    if choice == "C":
        return "delegated-apply"
    raise ValueError("mode must be A, B, or C")


def handle_install(args) -> int:
    mode = resolve_mode(args)
    result = install_project_guidance(args.cwd or Path.cwd(), mode)
    print(f"OpenSpec delegation guidance {result.action}: {result.path}")
    print(f"Delegation mode: {result.mode}")
    print("Scope: project-local")
    return 0


def handle_uninstall(args) -> int:
    result = uninstall_project_guidance(args.cwd or Path.cwd())
    print(f"OpenSpec delegation guidance {result.action}: {result.path}")
    return 0


def handle_compat_install(args) -> int:
    print("agent-dispatch install_delegant is deprecated; use trly install.", file=sys.stderr)
    if getattr(args, "uninstall", False):
        return handle_uninstall(args)
    return handle_install(args)
