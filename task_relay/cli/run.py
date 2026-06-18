from argparse import Namespace
import sys

from task_relay.core import run


def handle_run(args: Namespace) -> int:
    output = run(
        target=args.target,
        targets=args.targets,
        prompt=args.input_text,
        model=args.model,
        effort=args.effort,
        timeout=args.timeout,
        cwd=args.cwd,
    )
    sys.stdout.write(output)
    return 0
