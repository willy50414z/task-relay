import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from task_relay.cli.evaluate import handle_evaluate
from task_relay.cli.health import handle_health
from task_relay.cli.pack import handle_pack, handle_pack_lint, handle_pack_metrics
from task_relay.cli.run import handle_run
from task_relay.cli.trace import handle_trace
from task_relay.delegation import InstallResult, clear, install, parse_existing_block, resolve_install_paths, uninstall
from task_relay.review_config import (
    DEFAULT_GLOBAL_TIMEOUT,
    ReviewRoleEntry,
    default_arbiter_entries,
    migrate_legacy_review_chain,
    parse_role_entries,
)
from task_relay.review_gate import (
    APPROVE_EXIT_CODE,
    CONFIG_EXIT_CODE,
    REJECT_EXIT_CODE,
    REVISE_EXIT_CODE,
    RUNTIME_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    config_from_args,
    exit_code_for_result,
    run_review_gate,
    verify_revision_readiness,
)
from task_relay.wizard import WizardState, make_prompt_adapter, run_wizard

from task_relay.packer import VALID_MODES as PACK_MODES

AGENT_NAMES = ["claude", "codex", "deepseek"]
INSTALL_TARGETS = ["claude", "codex"]


def build_parser(prog: str = "trly") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a raw prompt against an agent target.")
    add_target_args(run_parser, required=True)
    add_input_args(run_parser, "prompt")
    add_common_execution_args(run_parser)
    run_parser.add_argument(
        "--expect-output",
        action="append",
        default=[],
        metavar="PATH",
        help="Verify the agent created this non-empty file; fail loudly otherwise. Repeatable.",
    )
    run_parser.add_argument(
        "--isolate",
        action="store_true",
        help="Run the delegate in an ephemeral git worktree with push disabled; "
             "changes land on a throwaway branch the primary can review/merge.",
    )
    run_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="With --isolate, delegate from clean HEAD even if the main working tree is dirty.",
    )
    run_parser.add_argument(
        "--base",
        default="HEAD",
        help="With --isolate, branch the ephemeral worktree from this ref instead of HEAD.",
    )
    run_parser.set_defaults(handler=handle_run)

    evaluate_parser = subparsers.add_parser("evaluate", help="Run outcome-routed execution and emit JSON.")
    add_target_args(evaluate_parser, required=True)
    add_input_args(evaluate_parser, "purpose")
    add_common_execution_args(evaluate_parser)
    evaluate_parser.add_argument("--outcome", action="append", required=True, default=[], metavar="STATUS=DESCRIPTION")
    evaluate_parser.add_argument("--output-file", action="append", default=[], metavar="STATUS=PATH")
    evaluate_parser.add_argument("--json", action="store_true", required=True)
    evaluate_parser.set_defaults(handler=handle_evaluate)

    pack_parser = subparsers.add_parser("pack", help="Generate a delegation packet with scoped OpenSpec context inlined.")
    pack_parser.add_argument("--mode", required=True, choices=list(PACK_MODES))
    pack_parser.add_argument("--change", required=True, help="OpenSpec change name")
    pack_parser.add_argument("--task", help="Task id to reference in the packet")
    pack_parser.add_argument("--read", action="append", default=[], dest="extra_reads", metavar="PATH", help="Extra repo file to inline. Repeatable.")
    pack_parser.add_argument("--full-change-context", action="store_true", help="Inline the full change instead of scoped defaults.")
    pack_parser.add_argument("--dry-run", action="store_true", help="Report selected files/sections without emitting the full packet.")
    pack_parser.add_argument("--json", action="store_true", help="With --dry-run, emit the scope report as JSON.")
    pack_parser.add_argument("--out", help="Write the packet to this file instead of stdout")
    pack_parser.add_argument("--cwd", help="Project root containing openspec/ (defaults to current dir)")
    pack_parser.add_argument("--diff-file", help="Explicit diff file for test-mode dynamic repo context.")
    pack_parser.add_argument("--diff-from", help="Git ref to diff from for test-mode dynamic repo context.")
    pack_parser.add_argument("--model-resolver", action="store_true", help="Enable opt-in model-assisted scope resolution contract.")
    pack_parser.add_argument("--model-result", help="Structured model resolver result JSON for validation/testing.")
    pack_parser.add_argument("--model-call-limit", type=int, default=1, help="Per-pack model resolver call limit.")
    pack_parser.set_defaults(handler=handle_pack)

    pack_metrics_parser = subparsers.add_parser("pack-metrics", help="Evaluate packer scope selection against a labeled eval set.")
    pack_metrics_parser.add_argument("--eval-set", required=True, help="Path to a JSON eval set.")
    pack_metrics_parser.add_argument("--cwd", help="Project root containing openspec/ (defaults to current dir)")
    pack_metrics_parser.add_argument("--json", action="store_true", required=True)
    pack_metrics_parser.set_defaults(handler=handle_pack_metrics)

    pack_lint_parser = subparsers.add_parser("pack-lint", help="Advisory diagnostics for packer scope signals and fallback behavior.")
    pack_lint_parser.add_argument("--change", required=True, help="OpenSpec change name")
    pack_lint_parser.add_argument("--task", help="Task id to lint")
    pack_lint_parser.add_argument("--mode", default="implementation-draft", choices=list(PACK_MODES))
    pack_lint_parser.add_argument("--cwd", help="Project root containing openspec/ (defaults to current dir)")
    pack_lint_parser.add_argument("--json", action="store_true", required=True)
    pack_lint_parser.set_defaults(handler=handle_pack_lint)

    trace_parser = subparsers.add_parser("trace", help="Summarize delegation trace records.")
    trace_parser.add_argument("--summary", action="store_true", help="Print aggregate totals from the trace sink.")
    trace_parser.add_argument("--change", help="Filter the summary to one OpenSpec change.")
    trace_parser.add_argument("--cwd", help="Project root containing .task_relay/ (defaults to current dir)")
    trace_parser.set_defaults(handler=handle_trace)

    health_parser = subparsers.add_parser("health", help="Check agent availability.")
    health_parser.add_argument("--target", choices=AGENT_NAMES)
    health_parser.add_argument("--json", action="store_true", required=True)
    health_parser.set_defaults(handler=handle_health)

    review_gate_parser = subparsers.add_parser("review-gate", help="Run the full proposal review gate.")
    review_gate_parser.add_argument("--change", required=True, help="OpenSpec change name")
    review_gate_parser.add_argument("--reviewers", help="Override reviewers: agent[:/persona][=model],...")
    review_gate_parser.add_argument("--arbiter", action="append", default=[], help="Override arbiter entries. Repeatable or comma-separated.")
    review_gate_parser.add_argument("--global-timeout", type=int, default=DEFAULT_GLOBAL_TIMEOUT)
    review_gate_parser.add_argument("--cwd", help="Project root containing openspec/ (defaults to current dir)")
    review_gate_parser.add_argument("--json", action="store_true", help="Emit structured JSON result.")
    review_gate_parser.add_argument("--verify-revision", action="store_true", help="Verify whether a prior REVISE contract has been satisfied.")
    review_gate_parser.add_argument("--result-path", help="Override the machine-readable review result artifact path.")
    review_gate_parser.set_defaults(handler=handle_review_gate)

    install_parser = subparsers.add_parser("install", help="Install task-relay delegation guidance interactively.")
    install_group = install_parser.add_mutually_exclusive_group()
    install_group.add_argument("--primary", choices=INSTALL_TARGETS, help="Single installation target for backward compatibility")
    install_group.add_argument("--targets", type=parse_install_targets, help="Comma-separated installation targets (claude,codex)")
    install_parser.add_argument("--scope", choices=["user", "project"], help="Installation scope")
    install_parser.add_argument("--feature", help="Features to enable: review,apply or none (comma-separated)")
    install_parser.add_argument("--reviewers", help="Parallel reviewer entries: agent[:/persona][=model],...")
    install_parser.add_argument(
        "--arbiter",
        action="append",
        default=[],
        help="Serial arbiter entries: agent[:/persona][=model]. Repeatable or comma-separated.",
    )
    install_parser.add_argument(
        "--global-timeout",
        type=int,
        default=DEFAULT_GLOBAL_TIMEOUT,
        help="Global timeout in seconds for the full review gate.",
    )
    install_parser.add_argument("--review-chain", help="Deprecated review chain: agent=model,agent=model,...")
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


def _parse_repeatable_role_entries(values: list[str]) -> list[ReviewRoleEntry]:
    entries: list[ReviewRoleEntry] = []
    for value in values:
        entries.extend(parse_role_entries(value))
    return entries


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
    reviewers: list[ReviewRoleEntry] = []
    arbiters: list[ReviewRoleEntry] = []
    apply_chain: list[tuple[str, str | None]] = []

    reviewers_flag = getattr(args, "reviewers", None)
    arbiter_flag = getattr(args, "arbiter", None) or []
    review_chain_flag = getattr(args, "review_chain", None)
    apply_chain_flag = getattr(args, "apply_chain", None)

    if reviewers_flag:
        reviewers = parse_role_entries(reviewers_flag)
    if arbiter_flag:
        arbiters = _parse_repeatable_role_entries(arbiter_flag)
    if review_chain_flag and reviewers_flag:
        print("--review-chain is deprecated and cannot be combined with --reviewers", file=sys.stderr)
        return 1
    if review_chain_flag and not reviewers:
        legacy_review_chain = _parse_chain(review_chain_flag)
        if legacy_review_chain:
            reviewers = migrate_legacy_review_chain(legacy_review_chain)
            print(
                "warning: --review-chain is deprecated; only the primary review entry was migrated to reviewers.",
                file=sys.stderr,
            )
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
            reviewers_flag,
            arbiter_flag,
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

        if not reviewers and not apply_chain:
            if not sub_agent_flag:
                print("--reviewers or --apply-chain is required when features are enabled", file=sys.stderr)
                return 1

        if "review" in features:
            if not reviewers:
                print("--reviewers is required when review is enabled", file=sys.stderr)
                return 1
            if not arbiters:
                arbiters = default_arbiter_entries()

        results = [
            install(
                primary_agent=target,
                scope=args.scope,
                features=features,
                reviewers=reviewers,
                arbiters=arbiters,
                apply_chain=apply_chain,
                global_timeout=getattr(args, "global_timeout", DEFAULT_GLOBAL_TIMEOUT),
                legacy_review_chain=_parse_chain(review_chain_flag) if review_chain_flag else [],
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
                reviewers=state.reviewers,
                arbiters=state.arbiters,
                apply_chain=state.apply_chain,
                global_timeout=state.global_timeout,
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
        "--primary/--targets, --scope, --feature, and --reviewers/--apply-chain when features are enabled"
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
    shared_reviewers = _shared_role_value(candidates, "reviewers")
    shared_arbiters = _shared_role_value(candidates, "arbiters")
    shared_apply_chain = _shared_chain_value(candidates, "apply_chain")
    shared_scope = _shared_value(candidates, "scope")
    shared_timeout = _shared_value(candidates, "global_timeout")

    if shared_features is not None and shared_scope:
        return WizardState(
            target_agents=ordered_targets,
            scope=shared_scope,
            features=shared_features,
            reviewers=shared_reviewers or [],
            arbiters=shared_arbiters or [],
            apply_chain=shared_apply_chain or [],
            global_timeout=int(shared_timeout) if shared_timeout is not None else DEFAULT_GLOBAL_TIMEOUT,
            cwd=cwd,
        )

    return WizardState(target_agents=ordered_targets if target_agents else [], cwd=cwd)


def _build_prefill_state(candidate: dict, target_agents: list[str], cwd: Path) -> WizardState:
    features = candidate.get("features") or []
    reviewers = candidate.get("reviewers") or []
    arbiters = candidate.get("arbiters") or []
    apply_chain = candidate.get("apply_chain") or []

    return WizardState(
        target_agents=target_agents,
        scope=candidate.get("scope"),
        features=features,
        reviewers=reviewers,
        arbiters=arbiters,
        apply_chain=apply_chain,
        global_timeout=int(candidate.get("global_timeout") or DEFAULT_GLOBAL_TIMEOUT),
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


def _shared_role_value(candidates: list[dict], key: str) -> list[ReviewRoleEntry] | None:
    values = [
        tuple((entry.agent, entry.persona, entry.model) for entry in (candidate.get(key) or []))
        for candidate in candidates
    ]
    if len(set(values)) == 1:
        return [ReviewRoleEntry(agent=agent, persona=persona, model=model) for agent, persona, model in values[0]]
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


def handle_review_gate(args) -> int:
    if getattr(args, "verify_revision", False):
        try:
            payload = verify_revision_readiness(args.change, cwd=args.cwd, result_path=getattr(args, "result_path", None))
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return RUNTIME_EXIT_CODE
        if getattr(args, "json", False):
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        else:
            sys.stdout.write(f"{payload['decision']}\n")
            sys.stdout.write(f"apply_ready: {str(payload['apply_ready']).lower()}\n")
            if payload.get("pending_targets"):
                sys.stdout.write("pending_targets:\n")
                for item in payload["pending_targets"]:
                    sys.stdout.write(f"- {item}\n")
        if payload["decision"] == "REJECT":
            return REJECT_EXIT_CODE
        if payload["decision"] == "REVISE" and not payload["apply_ready"]:
            return REVISE_EXIT_CODE
        return APPROVE_EXIT_CODE

    try:
        config = config_from_args(args)
        result = run_review_gate(args.change, cwd=args.cwd, config=config)
    except TimeoutError:
        return TIMEOUT_EXIT_CODE
    except Exception as exc:
        from task_relay.errors import ReviewGateConfigError, ReviewGateTimeoutError

        print(str(exc), file=sys.stderr)
        if isinstance(exc, ReviewGateConfigError):
            return CONFIG_EXIT_CODE
        if isinstance(exc, ReviewGateTimeoutError):
            return TIMEOUT_EXIT_CODE
        return RUNTIME_EXIT_CODE

    if getattr(args, "json", False):
        payload = {
            "decision": result.decision,
            "summary_path": str(result.summary_path),
            "result_path": str(result.result_path),
            "apply_allowed": result.decision != "REJECT",
            "requires_primary_revision": result.decision == "REVISE",
            "reviewers": [str(item.path) for item in result.reviewer_artifacts],
            "arbiters": [str(item.path) for item in result.arbiter_artifacts],
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(f"{result.decision}\n")
        sys.stdout.write(f"summary: {result.summary_path}\n")
        sys.stdout.write(f"result: {result.result_path}\n")
        if result.decision == "REVISE":
            sys.stdout.write("apply_allowed_after_primary_revision: true\n")
            for arbiter in result.arbiter_artifacts:
                for item in arbiter.payload.get("actionable_items", []):
                    sys.stdout.write(
                        f"- {item.get('target_artifact')}: {item.get('required_change')} "
                        f"(acceptance: {item.get('acceptance_criteria')})\n"
                    )
    return exit_code_for_result(result)
