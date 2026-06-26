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
    install_parser.add_argument("--feature", help="Features to enable: review,apply or none (comma-separated)")
    install_parser.add_argument("--review-chain", help="Review agent chain: agent=model,agent=model,...")
    install_parser.add_argument("--apply-chain", help="Apply agent chain: agent=model,agent=model,...")
    install_parser.add_argument("--mode", choices=["main", "hybrid", "delegated-apply"], help="[legacy] Delegation mode — mapped to features")
    install_parser.add_argument("--sub-agent", choices=["claude", "codex", "deepseek"], help="[legacy] Delegation sub-agent — mapped to apply chain")
    install_parser.add_argument("--model", action="append", default=[], metavar="ROLE=MODEL_ID", help="[legacy] Model for a role")
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
        models[role] = model
    return models


def _parse_chain(value: str) -> list[tuple[str, str | None]]:
    """Parse --review-chain / --apply-chain 'agent=model,agent' into [(agent, model), ...]."""
    chain: list[tuple[str, str | None]] = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" in entry:
            agent, _, model = entry.partition("=")
            agent = agent.strip()
            model_val = model.strip() or None
        else:
            agent = entry.strip()
            model_val = None
        if agent:
            chain.append((agent, model_val))
    return chain


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


# ── Handlers ────────────────────────────────────────────────────────

def handle_install(args) -> int:
    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    target_agents = _resolve_install_targets(args)

    # Determine features: new --feature flag takes precedence over legacy --mode
    features: list[str] = []
    feature_flag = getattr(args, "feature", None)
    mode_flag = getattr(args, "mode", None)
    sub_agent_flag = getattr(args, "sub_agent", None)
    model_flag = getattr(args, "model", [])

    if feature_flag:
        if feature_flag.lower() == "none":
            features = []
        else:
            features = [f.strip() for f in feature_flag.split(",") if f.strip()]
    elif mode_flag and mode_flag != "main":
        features = ["apply"]

    # Determine chains: new flags take precedence, legacy --sub-agent maps to apply chain
    review_chain: list[tuple[str, str | None]] = []
    apply_chain: list[tuple[str, str | None]] = []

    review_chain_flag = getattr(args, "review_chain", None)
    apply_chain_flag = getattr(args, "apply_chain", None)

    if review_chain_flag:
        review_chain = _parse_chain(review_chain_flag)
    if apply_chain_flag:
        apply_chain = _parse_chain(apply_chain_flag)
    elif sub_agent_flag:
        models = _parse_models(model_flag)
        model = models.get("sub") or models.get(sub_agent_flag)
        apply_chain = [(sub_agent_flag, model)]

    # Transition from legacy model role format
    if not review_chain_flag and not apply_chain_flag and model_flag and not sub_agent_flag and not mode_flag:
        print("--model flag requires --review-chain or --apply-chain (or legacy --mode/--sub-agent)", file=sys.stderr)
        return 1

    new_flags_provided = any(
        value
        for value in (
            target_agents,
            args.scope,
            feature_flag,
            review_chain_flag,
            apply_chain_flag,
        )
    )
    legacy_flags_provided = any(
        value
        for value in (
            target_agents,
            args.scope,
            mode_flag,
            sub_agent_flag,
            model_flag,
        )
    )

    flags_provided = new_flags_provided or legacy_flags_provided

    if flags_provided and target_agents and args.scope and (features or feature_flag == "none" or (mode_flag == "main")):
        # Non-interactive path: enough flags to proceed without wizard
        if not features and not (legacy_flags_provided and mode_flag != "main" and sub_agent_flag):
            # Clear / no delegation
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

        if not review_chain and not apply_chain:
            if not sub_agent_flag:
                print("--review-chain or --apply-chain is required when features are enabled", file=sys.stderr)
                return 1

        results = [
            install(
                primary_agent=target,
                scope=args.scope,
                features=features,
                review_chain=review_chain,
                apply_chain=apply_chain,
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
                features=state.features,
                review_chain=state.review_chain,
                apply_chain=state.apply_chain,
                cwd=state.cwd,
            )

    def clear_fn(state: WizardState):
        for target in state.target_agents:
            clear(primary_agent=target, scope=state.scope, cwd=state.cwd)

    prefill_state = _resolve_prefill_state(target_agents, args.scope, cwd)

    return run_wizard(write_fn, clear_fn, cwd=cwd, prefill_state=prefill_state, prompt=prompt)


def _non_interactive_install_error() -> str:
    return (
        "install requires non-interactive flags when stdin is not a TTY: "
        "--primary/--targets, --scope, --feature, and --review-chain/--apply-chain when features are enabled"
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
        return _build_prefill_state(candidate, ordered_targets, cwd)

    shared_features = _shared_list_value(candidates, "features")
    shared_review_chain = _shared_chain_value(candidates, "review_chain")
    shared_apply_chain = _shared_chain_value(candidates, "apply_chain")
    shared_scope = _shared_value(candidates, "scope")

    if shared_features is not None and shared_scope:
        return WizardState(
            target_agents=ordered_targets,
            scope=shared_scope,
            features=shared_features,
            review_chain=shared_review_chain or [],
            apply_chain=shared_apply_chain or [],
            cwd=cwd,
        )

    return WizardState(target_agents=ordered_targets if target_agents else [], cwd=cwd)


def _build_prefill_state(candidate: dict, target_agents: list[str], cwd: Path) -> WizardState:
    features = candidate.get("features") or []
    review_chain = candidate.get("review_chain") or []
    apply_chain = candidate.get("apply_chain") or []

    return WizardState(
        target_agents=target_agents,
        scope=candidate.get("scope"),
        features=features,
        review_chain=review_chain,
        apply_chain=apply_chain,
        cwd=cwd,
    )


def _shared_value(candidates: list[dict], key: str) -> str | None:
    values = {candidate.get(key) for candidate in candidates}
    if len(values) == 1:
        return values.pop()
    return None


def _shared_list_value(candidates: list[dict], key: str) -> list | None:
    values = [tuple(candidate.get(key) or []) for candidate in candidates]
    if len(set(values)) == 1:
        return list(values[0])
    return None


def _shared_chain_value(candidates: list[dict], key: str) -> list | None:
    values = [tuple((a, m) for a, m in (candidate.get(key) or [])) for candidate in candidates]
    if len(set(values)) == 1:
        # Convert tuple elements back to tuples
        return [tuple(item) for item in values[0]]
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
