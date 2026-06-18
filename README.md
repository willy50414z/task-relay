# task-relay

`task-relay` — structured agent task runner with outcome routing via file signals.

## Install

```bash
python -m pip install -e .
trly --help
```

Requires Python 3.11 or newer. Supported local CLIs in v0.2 are `claude`, `codex`, and `deepseek` via the Claude CLI bridge.

## Quick start

```python
from task_relay import Outcome, evaluate

evaluate(
    target="claude",
    purpose="Review this spec.",
    outcomes=[
        Outcome(status="complete", description="The spec is complete", callback=lambda result: None),
        Outcome(
            status="incomplete",
            description="The spec has gaps",
            output_files=["questions.txt"],
            callback=lambda result: print(result.files["questions.txt"].decode("utf-8")),
        ),
    ],
)
```

## CLI

```bash
trly run --target claude --prompt "hello"
trly evaluate --target codex --purpose "review this" --outcome complete="Done" --json
trly health --json
trly install --mode hybrid --cwd .
trly uninstall --cwd .
```

## Migration

- Canonical package: `task_relay`
- Canonical CLI: `trly`

## v0.2 Non-goals

- No async queue or job store
- No HTTP API or webhook runtime
- No browser relay / `opencli` runtime support
- No plugin discovery for third-party adapters
