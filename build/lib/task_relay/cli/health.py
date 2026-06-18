import json
from argparse import Namespace

from task_relay.agents import check_all, check_target


def handle_health(args: Namespace) -> int:
    if args.target:
        statuses = {args.target: check_target(args.target)}
    else:
        statuses = check_all()
    print(json.dumps({name: {"ok": status.ok, "reason": status.reason} for name, status in statuses.items()}, sort_keys=True))
    return 0
