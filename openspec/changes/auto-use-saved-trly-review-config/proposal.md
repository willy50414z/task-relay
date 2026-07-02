## Why

`$trly-review` 目前在找到 saved review config 後仍會問使用者是否套用；這對日常 review flow 是多餘 gate，也會鼓勵 delegate 進入互動式設定而不是直接執行。既然 review config 已由 `trly install` 或 `trly review --save` 明確保存，skill 應預設信任並使用它，只有使用者明確要求重新設定時才進入 reviewer/arbiter selection workflow。

## What Changes

- `$trly-review` 找到 saved review config 時，改為印出與目前確認畫面相同格式的 `Role / Agent / Model / Effort / Personas` table，並宣告「我將根據以下 review config 進行 review」。
- 不再詢問「是否要套用 saved setting」；直接執行 `trly review --change <change>`。
- 只有在觸發 `$trly-review` 的 prompt 明確要求重新設定 review config，或使用者以 review config 設定意圖觸發流程時，才進入現有 reviewer/arbiter selection workflow。
- 保留現有 Python CLI `trly review` / `trly install` 行為，不新增 command panel 或 CLI interactive mode。
- 保留 saved config 的儲存位置：`AGENTS.md` / `CLAUDE.md` managed block。`.task_relay/` 繼續作為 runtime jobs、trace、worktree 等執行狀態位置，不作為 durable review config source of truth。

## Capabilities

### New Capabilities

無。

### Modified Capabilities

- `trly-review-interactive-workflow`: 將 saved config 行為從「顯示並確認是否套用」改為「顯示並自動使用」，並定義何時才進入 reconfiguration workflow。

## Impact

- 主要程式碼：
  - `task_relay/delegation.py`: generated `trly-review/SKILL.md` 的 saved-config 區段文字。
  - `tests/test_delegation.py`: skill generation assertions，確認不再要求 saved config confirmation，並包含 auto-use 與 reconfiguration trigger 規則。
- 不預期修改：
  - `task_relay/cli/__init__.py` 的 `handle_review()` 或 install wizard。
  - managed block schema。
  - `.task_relay/` runtime storage。
  - review gate runner 或 reviewer/arbiter execution model。
