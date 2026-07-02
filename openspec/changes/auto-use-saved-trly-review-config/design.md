## Context

`$trly-review` 的 routing 設定目前由 generated skill instruction 驅動。使用者可以透過 `trly install` 或 `trly review --save` 把 reviewer / arbiter 設定寫入 managed guidance，Codex 專案範圍使用 `AGENTS.md`，Claude 專案範圍使用 `CLAUDE.md`。`.task_relay/` 則用於 jobs、results、trace、worktree 等 runtime 狀態。

目前 generated `trly-review/SKILL.md` 在找到 saved review config 後會先顯示 table，再詢問使用者是否套用。這個確認步驟對已保存的專案 config 來說是多餘的，而且在 automation 中會造成互動式停頓。

## Goals

- Saved review config 存在時，`$trly-review` 預設直接使用該 config。
- 顯示格式維持與目前確認畫面相同，讓使用者仍能看到實際 reviewer / arbiter routing。
- 只有明確 reconfiguration intent 或 routing override intent 才進入 reviewer / arbiter selection workflow。
- 不新增 Python CLI command panel，也不更動 durable config 儲存位置。

## Non-Goals

- 不修改 `trly review` runner、review gate JSON contract、arbiter decision flow。
- 不新增 `.task_relay` 下的 durable review config 檔案。
- 不改變 `trly install` wizard 或 `trly review --save` 的 storage schema。
- 不在 propose 階段執行 delegated review 或 apply。

## Proposed Design

主要修改點是 `task_relay/delegation.py::_build_review_skill_md()` 產生的 `trly-review/SKILL.md` workflow 文字。

Saved config branch 改為：

1. 先 resolve OpenSpec change。
2. 查找 managed guidance 中的 Task Relay review config。
3. 若 config 存在且觸發 prompt 沒有 reconfiguration intent，印出：

   ```text
   我將根據以下 review config 進行 review：
   ```

   接著印出既有 table：

   ```md
   | Role | Agent | Model | Effort | Personas |
   | --- | --- | --- | --- | --- |
   | reviewer | codex | gpt-5.5 | high | review |
   | arbiter | claude | default | n/a | plan-eng-review |
   ```

4. 直接執行：

   ```bash
   trly review --change <change>
   ```

5. 不詢問是否要套用 saved config。

Reconfiguration branch 在以下情況進入既有 reviewer / arbiter selection workflow：

- 沒有 saved review config。
- 觸發 prompt 明確要求重新設定，例如「重新設定」、「重設」、「改 review config」、「設定 review config」、「換 reviewer」、「換 arbiter」。
- 觸發 prompt 使用英文 reconfiguration intent，例如 `reconfigure`、`reset review config`、`change review config`。
- 觸發 prompt 包含 routing override / save intent，例如 `--reviewers`、`--arbiter`、`--save`、`--no-save`。

## Storage Decision

Saved review config 的 durable source of truth 維持在 managed guidance：

- Codex project scope: `AGENTS.md`
- Claude project scope: `CLAUDE.md`
- User / other scopes: 沿用現有 install / persist 行為

`.task_relay/` 不適合存 durable review config，原因是它已承擔 runtime execution state，包括 job packets、results、trace、worktree metadata。把 durable config 放進 `.task_relay/` 會增加 source-of-truth 衝突，也會讓清理 runtime state 時誤刪長期 routing 設定的風險上升。

## Test Strategy

- 更新 generated skill 的測試，確認 saved config branch 使用 auto-run wording。
- 確認 skill instruction 不再要求「ask whether to apply」saved config。
- 確認 explicit reconfiguration / routing override trigger 被文件化。
- 確認修改沒有引入 `.task_relay` 作為 durable review config storage 的指示。
