# Migration Guide: agent-cli-dispatcher to task-relay

本文是獨立遷移指南，目標是把使用者與專案從舊套件 `agent-cli-dispatcher` / `llm_eval` / `agent-dispatch` 遷移到新套件 `task-relay` / `task_relay` / `trly`。

這份文件只描述遷移方式與相容策略。架構細節請看 `openspec/changes/redesign-task-relay-architecture/design.md`。

## 遷移總覽

| 舊名稱 | 新名稱 | 狀態 |
|---|---|---|
| PyPI package `agent-cli-dispatcher` | `task-relay` | 新 canonical package |
| Python import `llm_eval` | `task_relay` | `llm_eval` 暫時保留 shim |
| CLI `agent-dispatch` | `trly` | `agent-dispatch` 暫時保留 alias |
| enum `LLMTarget` | agent name string | 改為 registry resolution |
| `.llm_eval/<job_id>/` workspace | `.task_relay/<job_id>/` workspace | 新 workspace root |
| `LLM_KEEP_IO=1` | `TASK_RELAY_KEEP_IO=1` | 新 debug retention flag |

相容 alias 預計在 `v0.3.0` 移除。新程式碼應直接使用 `task_relay` 與 `trly`。

## 何時需要遷移

你需要遷移，如果你的程式碼或腳本符合任一條件：

- Python 程式碼有 `from llm_eval import ...`
- CLI 腳本使用 `agent-dispatch run`
- CLI 腳本使用 `agent-dispatch evaluate`
- OpenSpec delegation 安裝流程使用 `agent-dispatch install_delegant`
- 程式碼依賴 `LLMTarget.CLAUDE`、`LLMTarget.CODEX`、`LLMTarget.DEEPSEEK`
- 測試或 CI 直接 assert 舊 command name、舊 package name、舊 workspace path

## 安裝新套件

在新 repo 或 checkout 中安裝：

```bash
python -m pip install -e .
trly --help
```

Python 版本需求是 `>=3.11`。

`task-relay` v0.2 內建支援：

- `claude`
- `codex`
- `deepseek` via Claude CLI bridge

## Python API 遷移

### Import

舊寫法：

```python
from llm_eval import evaluate, run, Outcome, JobResult, LLMTarget
```

新寫法：

```python
from task_relay import evaluate, run, Outcome, JobResult
```

`llm_eval` 仍可暫時 import，但會發出 `DeprecationWarning`：

```text
llm_eval is deprecated; import from task_relay instead.
Compatibility aliases are planned for removal in v0.3.0.
```

### Target values

舊寫法使用 enum：

```python
from llm_eval import LLMTarget, run

answer = run(
    target=LLMTarget.CLAUDE,
    prompt="Explain this repository.",
)
```

新寫法使用 agent name string：

```python
from task_relay import run

answer = run(
    target="claude",
    prompt="Explain this repository.",
)
```

Fallback targets 也改成 string list：

```python
from task_relay import run

answer = run(
    targets=["claude", "deepseek"],
    prompt="Explain this repository.",
)
```

### Outcome-routed evaluation

舊寫法：

```python
from llm_eval import LLMTarget, Outcome, evaluate

evaluate(
    target=LLMTarget.CLAUDE,
    purpose="Review this spec.",
    outcomes=[
        Outcome(
            status="complete",
            description="The spec is complete",
            callback=lambda result: print("done"),
        ),
        Outcome(
            status="incomplete",
            description="The spec has gaps",
            output_files=["questions.txt"],
            callback=lambda result: print(result.files["questions.txt"].decode("utf-8")),
        ),
    ],
)
```

新寫法：

```python
from task_relay import Outcome, evaluate

evaluate(
    target="claude",
    purpose="Review this spec.",
    outcomes=[
        Outcome(
            status="complete",
            description="The spec is complete",
            callback=lambda result: print("done"),
        ),
        Outcome(
            status="incomplete",
            description="The spec has gaps",
            output_files=["questions.txt"],
            callback=lambda result: print(result.files["questions.txt"].decode("utf-8")),
        ),
    ],
)
```

### Callable purpose

如果 prompt 需要 workspace path，`purpose` 仍可接受 callable：

```python
from pathlib import Path

from task_relay import Outcome, evaluate

def purpose(workspace: Path) -> str:
    return f"Write status_complete in {workspace}"

evaluate(
    target="claude",
    purpose=purpose,
    outcomes=[
        Outcome(
            status="complete",
            description="Task completed",
            callback=lambda result: print(result.status),
        )
    ],
)
```

### Exceptions

新 package 匯出更具體的 error classes：

```python
from task_relay import (
    AgentExecutionError,
    AgentNotFoundError,
    AgentQuotaError,
    AgentTimeoutError,
    ConfigError,
    OutcomeResolutionError,
    TaskRelayError,
)
```

建議新程式碼不要只 catch `Exception`。依照情境捕捉具體錯誤：

```python
from task_relay import AgentQuotaError, OutcomeResolutionError, evaluate

try:
    evaluate(...)
except AgentQuotaError as exc:
    print(f"Quota exhausted: {exc}")
except OutcomeResolutionError as exc:
    print(f"Agent did not produce a valid outcome: {exc}")
```

如果你已經使用 `on_exception`，行為仍保留：

```python
evaluate(
    target="claude",
    purpose="Review this.",
    outcomes=[...],
    on_exception=lambda exc: print(f"failed: {exc}"),
)
```

## CLI 遷移

### Raw prompt execution

舊指令：

```bash
agent-dispatch run --target claude --prompt "Explain this repository."
```

新指令：

```bash
trly run --target claude --prompt "Explain this repository."
```

Prompt file：

```bash
trly run --target codex --prompt-file prompt.md
```

Stdin：

```bash
type prompt.md | trly run --target deepseek --stdin
```

PowerShell 也可以：

```powershell
Get-Content prompt.md | trly run --target deepseek --stdin
```

### Fallback targets

舊指令：

```bash
agent-dispatch run --targets claude,deepseek --prompt-file prompt.md
```

新指令：

```bash
trly run --targets claude,deepseek --prompt-file prompt.md
```

### Outcome-routed evaluation

舊指令：

```bash
agent-dispatch evaluate --target deepseek \
  --purpose-file purpose.md \
  --outcome complete="Implementation is complete" \
  --outcome failed="Implementation failed or is incomplete" \
  --output-file failed=errors.txt \
  --json
```

新指令：

```bash
trly evaluate --target deepseek \
  --purpose-file purpose.md \
  --outcome complete="Implementation is complete" \
  --outcome failed="Implementation failed or is incomplete" \
  --output-file failed=errors.txt \
  --json
```

### Health checks

舊指令：

```bash
agent-dispatch health --json
agent-dispatch health --target codex --json
```

新指令：

```bash
trly health --json
trly health --target codex --json
```

### OpenSpec delegation install

舊指令：

```bash
agent-dispatch install_delegant --mode hybrid --cwd .
agent-dispatch install_delegant --uninstall --cwd .
```

新指令：

```bash
trly install --mode hybrid --cwd .
trly uninstall --cwd .
```

Deprecated `--level` mapping remains available through compatibility behavior:

| Old flag | New mode |
|---|---|
| `--level 1` | `--mode hybrid` |
| `--level 2` | `--mode delegated-apply` |

Prefer `--mode` for all new scripts.

## Configuration migration

`task-relay` reads config from:

```text
~/.task-relay/config.yml
```

Minimal config:

```yaml
default_agent: claude
agents:
  claude:
    model: claude-sonnet-4-6
  codex:
    model: gpt-5.5
    effort: high
  deepseek:
    model: deepseek-v4-pro[1m]
    effort: max
```

Precedence:

1. Explicit function args or CLI flags
2. `~/.task-relay/config.yml`
3. Built-in defaults

Example: this CLI flag wins over config:

```bash
trly run --target codex --model gpt-5.5 --effort xhigh --prompt "Review this."
```

Reserved but unsupported in v0.2:

```yaml
agents:
  gemini-web:
    type: opencli
```

This intentionally fails in v0.2 with a config error. Browser relay is reserved for a later version.

## Environment variables

| Old | New | Purpose |
|---|---|---|
| `LLM_KEEP_IO=1` | `TASK_RELAY_KEEP_IO=1` | Keep prompt/output/workspace files for debugging |
| `DEEPSEEK_AUTH_TOKEN` | `DEEPSEEK_AUTH_TOKEN` | Required for DeepSeek through Claude-compatible bridge |

Example:

```bash
set TASK_RELAY_KEEP_IO=1
trly evaluate --target claude --purpose "debug this" --outcome complete="Done" --json
```

PowerShell:

```powershell
$env:TASK_RELAY_KEEP_IO = "1"
trly evaluate --target claude --purpose "debug this" --outcome complete="Done" --json
```

## Test migration checklist

Update tests in this order:

1. Replace imports:

   ```python
   from llm_eval import ...
   ```

   with:

   ```python
   from task_relay import ...
   ```

2. Replace enum usage:

   ```python
   LLMTarget.CLAUDE
   ```

   with:

   ```python
   "claude"
   ```

3. Replace CLI command assertions:

   ```text
   agent-dispatch
   ```

   with:

   ```text
   trly
   ```

4. Update workspace path expectations:

   ```text
   .llm_eval/
   ```

   to:

   ```text
   .task_relay/
   ```

5. Add compatibility tests if your project still promises old behavior:

   - `import llm_eval` emits `DeprecationWarning`
   - `agent-dispatch` emits a deprecation warning and still runs
   - `agent-dispatch install_delegant --level 1` maps to hybrid mode

6. Run:

   ```bash
   pytest
   ```

## CI migration checklist

Update CI scripts:

- Install from the new package/repo path.
- Run `trly --help` instead of `agent-dispatch --help`.
- Run new test suite against `task_relay`.
- If packaging is tested, inspect metadata for:
  - package name `task-relay`
  - version `0.2.0`
  - script `trly`
  - temporary script `agent-dispatch`

Suggested commands:

```bash
python -m pip install -e .
trly --help
pytest
python -m build
```

## Verification

After migration, verify these flows:

```bash
trly run --target claude --prompt "Say OK"
trly run --targets claude,deepseek --prompt "Say OK"
trly evaluate --target claude --purpose "Create status_complete" --outcome complete="Done" --json
trly health --json
trly install --mode hybrid --cwd .
trly uninstall --cwd .
```

For Python:

```python
from task_relay import Outcome, evaluate, run

assert isinstance(run(target="claude", prompt="Say OK"), str)

received = []
evaluate(
    target="claude",
    purpose="Create status_complete.",
    outcomes=[
        Outcome(
            status="complete",
            description="Done",
            callback=lambda result: received.append(result),
        )
    ],
)
assert received[0].status == "complete"
```

## Rollback

If the migration fails before publishing:

1. Stop using `task-relay`.
2. Keep `agent-cli-dispatcher` as the active package.
3. Do not publish `task-relay` until the failing flow has a regression test.

If `task-relay` is already published and a regression appears:

1. Keep the old `agent-cli-dispatcher` package available.
2. Publish a `task-relay` patch release.
3. Keep compatibility aliases until the patch is verified.
4. Do not remove `llm_eval` or `agent-dispatch` aliases before `v0.3.0`.

## Common failure modes

### `LLMTarget` import fails

Cause: new API no longer exposes the old enum as canonical behavior.

Fix:

```python
run(target="claude", prompt="...")
```

### `agent-dispatch install_delegant` still works but warns

Cause: compatibility command is intentionally temporary.

Fix:

```bash
trly install --mode hybrid --cwd .
```

### `type: opencli` config fails

Cause: browser relay is reserved but not implemented in v0.2.

Fix: use a built-in local CLI agent in v0.2:

```yaml
default_agent: claude
agents:
  claude:
    model: claude-sonnet-4-6
```

### DeepSeek fails with missing token

Cause: DeepSeek still requires `DEEPSEEK_AUTH_TOKEN`.

Fix:

```bash
set DEEPSEEK_AUTH_TOKEN=your-token
```

PowerShell:

```powershell
$env:DEEPSEEK_AUTH_TOKEN = "your-token"
```

## Final cutover checklist

- [ ] All Python imports use `task_relay`.
- [ ] All new CLI scripts use `trly`.
- [ ] No production code depends on `LLMTarget`.
- [ ] No tests assume `.llm_eval/` workspace paths.
- [ ] Config is stored under `~/.task-relay/config.yml`.
- [ ] CI runs `pytest` against the new package.
- [ ] README points users to `task-relay`, `task_relay`, and `trly`.
- [ ] Compatibility warnings are tested.
- [ ] Removal of compatibility aliases is scheduled for `v0.3.0`.

