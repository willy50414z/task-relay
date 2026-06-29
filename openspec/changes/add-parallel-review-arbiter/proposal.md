## Why

現有 review 機制以 `review-chain` 表示，語義上是有順序的 fallback chain：Primary 先呼叫第一個 reviewer，失敗或不足時再呼叫下一個 reviewer，最後仍由 Primary 自行整合判斷。這種模式有三個問題：

- 無法同時取得多個獨立 reviewer 的觀點，review 結果容易受第一個 reviewer 或 Primary 偏好影響。
- review artifact 使用單一輸出檔，無法安全支援平行寫入，也不利於追蹤每個 persona 的判斷來源。
- DAG apply gate 沒有獨立仲裁節點，Primary 必須自行把 review 報告轉成 PASS / REVISE / STOP 類型的流程決策。

本變更將 propose phase 的 review gate 重構為「平行專家審查團 + 串行仲裁者鏈」。Reviewers 並行產生獨立 JSON 報告，Arbiters 再依序閱讀原始 OpenSpec 文件與所有 reviewer 報告，輸出結構化決策 JSON。Primary 只根據 JSON 的 `decision` 欄位執行程式化 DAG 決策：`REJECT` 會停止 Apply 並回到 propose/explore；`APPROVE` 可直接進入 Apply；`REVISE` 則由 Primary 依 Arbiter 的約束性 revision contract 修訂 proposal/design/tasks/specs，完成修訂後即可進入 Apply。Primary 不得重新仲裁 reviewer 衝突，也不得覆寫 Arbiter 裁決。

## What Changes

- 廢棄 review path 對 `--review-chain` 的串行 fallback 語義，新增 `--reviewers` 設定多個平行 reviewer。
- 新增必填的 `--arbiter` 設定串行 arbiter 階段；同一個 agent 可同時出現在 reviewer 與 arbiter 設定中，因為兩者以不同 prompt/persona 與輸出 artifact 執行。
- 新增 `--global-timeout` 設定完整 review gate 的最長等待時間；任一必需 reviewer 或 arbiter 逾時都會 fail loudly。
- 新增 parallel review runner，使用 `asyncio.gather()` 同時啟動多個 `trly run --target <agent>` 子行程，並為每個 reviewer 指定唯一 `--expect-output`。
- 新增 serial arbiter runner，彙整 `proposal.md`、`design.md`、delta specs、tasks 與所有 `delegation_review_*.json`，依序呼叫 product/CEO 與 engineering arbiter persona。
- Arbiter 的 `REVISE` 輸出必須包含可執行的 revision contract；Primary 只負責把該 contract 落到 OpenSpec 文件，不能自行選擇採納或忽略 reviewer/arbiter 意見。
- 新增 machine-readable review result artifact，保留 final decision、actionable items 與 target artifact baseline，供 apply 前 handoff 與 revision readiness 驗證使用。
- 新增 revision readiness 驗證入口，讓 Primary 在 apply 前檢查 `REVISE` contract 指向的 artifacts 是否已被修改。
- 新增 review/arbiter persona templates，從 gstack skills 萃取角色，而不是直接執行會修改程式碼或互動式提問的完整 skill。
- 更新 managed guidance 生成邏輯與模板，讓 Primary 明確知道 review gate 是平行派發、串行仲裁、程式化決策。
- 保留 apply-chain 與一般 `trly run --targets` 的 fallback 語義；本變更只改 propose review gate 的 orchestration。

## Capabilities

### New Capabilities

- `parallel-review-arbitration`：支援 reviewer parallel fan-out、arbiter serial decision chain、DAG gate 決策與 final review artifact 合併。
- `review-persona-templates`：提供 reviewer 與 arbiter persona prompt 模板，包含 code review、security、QA、CEO/product arbiter、engineering arbiter。

### Modified Capabilities

- `review-agent-propose-workflow`：由單一 review-chain 報告改為多 reviewer 獨立報告與 arbiter JSON 裁決。
- `agent-fallback-chains`：釐清 fallback chain 仍用於 ordered fallback；reviewer list 是 parallel fan-out，不是 fallback。
- `openspec-delegation-install`：新增 `--reviewers` 與 `--arbiter`/repeatable arbiter 設定，並標示 `--review-chain` 在 review path 已 deprecated。
- `delegation-output-verification`：從單一 review artifact 驗證擴充為多 reviewer artifact 與 arbiter JSON schema 驗證。
- `delegation-packet-generation`：新增 arbiter packet generation，能把原始 OpenSpec 文件與 reviewer 報告組成綜合審查 packet。
- `task-execution-core`：新增 review gate orchestration API，但不改變既有 raw run 與 fallback run 的 contract。

## Impact

- 主要程式碼：
  - `task_relay/core.py` 或新增 `task_relay/review_gate.py`
  - `task_relay/cli/__init__.py`
  - `task_relay/delegation.py`
  - `task_relay/wizard.py`
  - `task_relay/packer.py`
- 模板與 assets：
  - `task_relay/assets/task-relay-delegation/templates/review-proposal.md`
  - `task_relay/assets/task-relay-delegation/templates/review-arbiter.md`
  - 新增 reviewer persona templates
- 測試：
  - install CLI parser 與 managed block 測試
  - review gate parallel execution 與 timeout 測試
  - reviewer artifact file isolation 測試
  - arbiter JSON parsing/schema/error handling 測試
  - Primary decision mapping 與 DAG gate 測試
