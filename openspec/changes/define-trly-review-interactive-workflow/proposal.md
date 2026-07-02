## Why

`$trly-review` 目前已有 review gate、reviewer/arbiter 設定解析與 `trly review` wrapper，但 skill 觸發後的使用者體驗仍不夠明確。Primary agent 需要一個穩定 contract：先展示既有 review 設定並取得確認；若沒有設定或使用者拒絕，則以一致的互動流程建立 reviewer 與 arbiter routing，最後依 arbiter 裁決更新 OpenSpec change artifacts。

## What Changes

- 定義 `$trly-review` 觸發後的完整互動流程：resolve change、讀取 saved config、以表格展示設定、確認是否套用、或逐步建立新設定。
- 定義 reviewer/arbiter 的互動選擇順序：agent、model、Codex effort、persona，以及是否新增下一位 reviewer/arbiter。
- 定義 setting display format，將現有 `agent:/persona=model` 設定轉成人類可讀的 `Role / Agent / Model / Effort / Personas` 表格。
- 定義 persona alias 行為，例如 `ceo` 對應 `/plan-ceo-review`、`engineer` 對應 `/plan-eng-review`。
- 保持現有 managed block storage format，不新增獨立 effort 欄位；Codex effort 由 model id 顯示與回寫。
- 明確規範 `$trly-review` 在 `APPROVE`、`REJECT`、`REVISE` 的後續行為，尤其 `REVISE` 時 Primary 只能套用 arbiter-adjudicated `actionable_items`。
- 讓 propose workflow 準備 delegate-ready review UX contract，但不在 propose 階段執行 reviewer 或 arbiter delegate。

## Capabilities

### New Capabilities

- `trly-review-interactive-workflow`: 定義 `$trly-review` skill 的互動式設定選擇、既有設定確認、review execution handoff，以及 arbiter revision contract 套用規則。

### Modified Capabilities

- None.

## Impact

- 主要程式碼：
  - `task_relay/delegation.py`
  - `task_relay/cli/__init__.py`
  - `task_relay/review_config.py`
  - `task_relay/workflow/review_gate.py`
- Skill/generated assets：
  - generated `trly-review/SKILL.md`
  - generated `task-relay-delegation/SKILL.md`
- 測試：
  - skill content generation tests
  - review config formatting/parsing tests
  - CLI saved-config display or helper tests
  - `REVISE` revision contract workflow tests
