from argparse import Namespace
import sys

from task_relay.core import run, run_background, run_isolated


def handle_run(args: Namespace) -> int:
    if getattr(args, "background", False):
        if getattr(args, "isolate", False):
            raise ValueError("--background cannot be combined with --isolate")
        job_id = run_background(
            target=args.target,
            targets=args.targets,
            prompt=args.input_text,
            model=args.model,
            effort=args.effort,
            timeout=args.timeout,
            cwd=args.cwd,
        )
        sys.stdout.write(f"{job_id}\n")
        return 0

    if getattr(args, "isolate", False):
        output, branch = run_isolated(
            target=args.target,
            targets=args.targets,
            prompt=args.input_text,
            model=args.model,
            effort=args.effort,
            timeout=args.timeout,
            cwd=args.cwd,
            allow_dirty=getattr(args, "allow_dirty", False),
            base=getattr(args, "base", "HEAD"),
        )
        sys.stdout.write(output)
        sys.stderr.write(f"\n[task-relay] delegated changes on branch: {branch}\n")
        return 0

    output = run(
        target=args.target,
        targets=args.targets,
        prompt=args.input_text,
        model=args.model,
        effort=args.effort,
        timeout=args.timeout,
        cwd=args.cwd,
        expect_output=getattr(args, "expect_output", None) or None,
    )
    sys.stdout.write(output)
    return 0
