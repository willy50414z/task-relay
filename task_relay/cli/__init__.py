import argparse
import sys
from pathlib import Path
from typing import Sequence

from task_relay.cli.evaluate import handle_evaluate
from task_relay.cli.health import handle_health
from task_relay.cli.run import handle_run
from task_relay.delegation import InstallResult, clear, install, parse_existing_block, resolve_install_paths, uninstall
from task_relay.wizard import WizardState, make_prompt_adapter, run_wizard

AGENT_NAMES = ["claude", "codex", "deepseek"]
INSTALL_TARGETS = ["claude", "codex"]


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
    install_group = install_parser.add_mutually_exclusive_group()
    install_group.add_argument("--primary", choices=INSTALL_TARGETS, help="Single installation target for backward compatibility")
    install_group.add_argument("--targets", type=parse_install_targets, help="Comma-separated installation targets (claude,codex)")
    install_parser.add_argument("--scope", choices=["user", "project"], help="Installation scope")
    install_parser.add_argument("--mode", choices=["main", "hybrid", "delegated-apply"], help="Delegation mode")
    install_parser.add_argument("--sub-agent", choices=["claude", "codex", "deepseek"], help="Delegation sub-agent")
    install_parser.add_argument("--model", action="append", default=[], metavar="ROLE=MODEL_ID", help="Model for a role (supported role: sub)")
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


def parse_install_targets(value: str) -> list[str]:
    targets = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [item for item in targets if item not in INSTALL_TARGETS]
    if invalid:
        raise ValueError(f"Unknown install target(s): {', '.join(invalid)}")
    deduped: list[str] = []
    for item in targets:
        if item not in deduped:
            deduped.append(item)
    if not deduped:
        raise ValueError("At least one install target is required.")
    return deduped


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
        if role != "sub":
            raise ValueError(f"--model role must be 'sub', got: {role}")
        models[role] = model
    return models


def _resolve_install_targets(args) -> list[str]:
    if args.targets:
        return list(args.targets)
    if args.primary:
        return [args.primary]
    return []


def _print_install_results(results: list[InstallResult]) -> None:
    for result in results:
        print(f"Task-relay delegation guidance {result.action}: {result.guidance_path}")
        print(f"  Primary agent : {result.primary_agent}")
        print(f"  Scope         : {result.scope}")
        print(f"  Mode          : {result.mode}")
        print(f"  Sub-agent     : {result.sub_agent}")


# ── Handlers ────────────────────────────────────────────────────────

def handle_install(args) -> int:
    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    target_agents = _resolve_install_targets(args)

    flags_provided = any(
        value
        for value in (
            target_agents,
            args.scope,
            args.mode,
            args.sub_agent,
            args.model,
        )
    )
    if flags_provided and target_agents and args.scope and args.mode:
        if args.mode == "main":
            results = []
            for target in target_agents:
                result = clear(primary_agent=target, scope=args.scope, cwd=cwd)
                if result:
                    results.append(result)
            if results:
                for result in results:
                    print(f"Delegation guidance cleared: {result.guidance_path}")
            else:
                print("No managed block found to clear.")
            return 0

        if not args.sub_agent:
            print("--sub-agent is required when mode is not 'main'", file=sys.stderr)
            return 1

        models = _parse_models(args.model)
        results = [
            install(
                primary_agent=target,
                scope=args.scope,
                mode=args.mode,
                sub_agent=args.sub_agent,
                models=models,
                cwd=cwd,
            )
            for target in target_agents
        ]
        _print_install_results(results)
        return 0

    if not sys.stdin.isatty():
        print(_non_interactive_install_error(), file=sys.stderr)
        return 1

    if flags_provided:
        print("Partial flags provided — launching interactive wizard to complete configuration.")

    prompt = make_prompt_adapter()

    def write_fn(state: WizardState):
        for target in state.target_agents:
            install(
                primary_agent=target,
                scope=state.scope,
                mode=state.mode,
                sub_agent=state.sub_agent,
                models=state.models,
                cwd=state.cwd,
            )

    def clear_fn(state: WizardState):
        for target in state.target_agents:
            clear(primary_agent=target, scope=state.scope, cwd=state.cwd)

    prefill_state = _resolve_prefill_state(target_agents, args.scope, cwd)

    return run_wizard(write_fn, clear_fn, cwd=cwd, prefill_state=prefill_state, prompt=prompt)


def _non_interactive_install_error() -> str:
    return (
        "install requires required non-interactive flags when stdin is not a TTY: "
        "--primary/--targets, --scope, --mode, and --sub-agent when mode is not 'main'"
    )


def _resolve_prefill_state(target_agents: list[str], scope: str | None, cwd: Path) -> WizardState | None:
    candidates: list[dict] = []
    for agent in INSTALL_TARGETS:
        if target_agents and agent not in target_agents:
            continue
        for candidate_scope in ("project", "user"):
            if scope and candidate_scope != scope:
                continue
            guidance_path, _ = resolve_install_paths(agent, candidate_scope, cwd)
            parsed = parse_existing_block(guidance_path)
            if parsed:
                parsed = dict(parsed)
                parsed["guidance_path"] = str(guidance_path)
                candidates.append(parsed)

    if not candidates:
        return None

    selected_targets = [entry.get("primary") for entry in candidates if entry.get("primary") in INSTALL_TARGETS]
    ordered_targets = [agent for agent in INSTALL_TARGETS if agent in selected_targets]

    if len(candidates) == 1:
        candidate = candidates[0]
        return WizardState(
            target_agents=ordered_targets,
            scope=candidate.get("scope"),
            mode=candidate.get("mode"),
            sub_agent=candidate.get("sub_agent"),
            models=_prefill_models(candidate),
            cwd=cwd,
        )

    shared_scope = _shared_value(candidates, "scope")
    shared_mode = _shared_value(candidates, "mode")
    shared_sub_agent = _shared_value(candidates, "sub_agent")
    shared_sub_model = _shared_sub_model(candidates)

    if shared_scope and shared_mode and shared_sub_agent and shared_sub_model:
        return WizardState(
            target_agents=ordered_targets,
            scope=shared_scope,
            mode=shared_mode,
            sub_agent=shared_sub_agent,
            models={"sub": shared_sub_model},
            cwd=cwd,
        )

    return WizardState(target_agents=ordered_targets if target_agents else [], cwd=cwd)


def _prefill_models(parsed: dict) -> dict[str, str]:
    models = parsed.get("models") or {}
    sub_agent = parsed.get("sub_agent")
    if models.get("sub"):
        return {"sub": models["sub"]}
    if sub_agent:
        model = models.get(sub_agent) or models.get(f"{sub_agent} (sub)")
        if model:
            return {"sub": model}
    return {}


def _shared_value(candidates: list[dict], key: str) -> str | None:
    values = {candidate.get(key) for candidate in candidates}
    if len(values) == 1:
        return values.pop()
    return None


def _shared_sub_model(candidates: list[dict]) -> str | None:
    values = [_prefill_models(candidate).get("sub") for candidate in candidates]
    if any(value is None for value in values):
        return None
    if len(set(values)) == 1:
        return values[0]
    return None


def handle_uninstall(args) -> int:
    cwd = Path(args.cwd) if args.cwd else Path.cwd()

    results = uninstall(scope=args.scope, cwd=cwd)
    if not results:
        print("No task-relay managed blocks found.")
        return 0

    for result in results:
        print(f"Removed delegation guidance: {result.guidance_path} (scope: {result.scope})")
    return 0
