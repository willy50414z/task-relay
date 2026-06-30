## Context

`task-relay` 目前已經具備三個很強的底層能力：scoped packet generation、review gate、以及 isolated delegation primitives。但這三者還沒有被包成「第一次安裝就能順利用起來」的產品體驗。現在的痛點集中在三類：

1. **可信度缺口**：`trly health` 對 DeepSeek 會假陽性，`run_review.py` 有重複定義，非互動 install 錯誤訊息還指向舊旗標。這些問題不大，但都會直接傷信任。
2. **流程缺口**：`review` 有高階命令，`apply` 仍要求使用者自行拼 `pack + run --isolate`。這讓文件能描述流程，但 CLI 沒有真正承接流程。
3. **證據缺口**：目前 `pack-metrics` 只驗證 packet selection，不足以支撐「token 降低且品質不變」這種對外主張。

這次 change 不重做 delegation 架構，也不引入新的 agent platform。重點是把現有 primitives productize 成更可靠、更可驗證、更容易第一次成功的 workflow。

## Goals / Non-Goals

**Goals:**
- 新增 `trly doctor`，讓 install 後的 agent / model / repo / config 問題能在正式執行前暴露
- 新增高階 `trly apply` 命令，統一 packet generation、isolated run、結果摘要與基本驗證
- 新增 packed vs full context benchmark 流程，量測 token、時間與 downstream quality
- 修正已知可靠度缺陷，避免 CLI 報告與實際 runtime 狀態不一致
- 改善 install 完成後的成功路徑，包含 smoke test 與 next-step guidance

**Non-Goals:**
- 不重寫現有 review gate DAG
- 不新增 GUI、dashboard、background daemon
- 不引入新的 provider 類型或動態線上 model discovery
- 不一次實作完整多 task parallel apply orchestration
- 不在這個 change 內重構整個 `redesign-task-relay-architecture` 分支

## Decisions

### D1. 以 `trly doctor` 作為單一 preflight 入口，而不是把檢查分散到 install / health / run

`health` 只回答「target 看起來能不能用」，不適合承擔 repo/config/worktree 的檢查。`doctor` 會成為更高階的診斷層，統一輸出：

- agent checks
- model checks
- repo/worktree checks
- managed block/config checks
- optional smoke checks

這樣 install、README、CI、issue template 都能指向同一個命令。`health` 保持輕量，`doctor` 提供真實可操作的 preflight。

替代方案：
- 直接擴充 `trly health`
  - 缺點：語義會變混亂，health 不再只是 target health
- 把檢查全部塞進 `trly install`
  - 缺點：只有 install 時能看見，後續 drift 無法重跑

### D2. `trly apply` 採最小高階封裝，不重做現有 primitives

第一版 `trly apply` 不自己發明新執行引擎，而是包裝現有 primitives：

1. 生成 `implementation-draft` 或 `test-draft` packet
2. 呼叫 `run_isolated`
3. 對空 branch fail loud
4. 輸出 branch 名稱與 diff summary
5. 可選跑一組驗證命令

這個設計的重點是把「文件描述的正確手法」變成「CLI 直接提供的正確手法」，不是立刻做 full orchestration engine。

替代方案：
- 只補更多 README 範例
  - 缺點：不能降低出錯率
- 直接做完整 change-level multi-task orchestration
  - 缺點：diff 太大，且會和現有 worktree primitives 交疊過多

### D3. benchmark 要量端到端結果，而不只量 packet selection

現有 `pack-metrics` 很有用，但它回答的是「選對 spec/task block 了沒」，不是「delegate 的最終品質有沒有掉」。新的 benchmark 分兩層：

- **selection layer**
  - 保留並擴充 `pack-metrics`
- **workflow layer**
  - 比較 full context vs packed context
  - 記錄 token / bytes / duration
  - 記錄 reviewer finding 採納率、apply 接受率、驗證通過率

這樣對內能優化 heuristics，對外能支撐產品主張。

替代方案：
- 只擴充 fixture 數量
  - 缺點：仍然停留在 selection layer

### D4. reliability fixes 直接併入這個 change，不另開小修

以下問題都會直接影響 doctor/install/apply 的可信度，應一起修：

- `DeepSeekRunner.check()` 不能永遠回 `ok=True`
- `run_review.py` 只保留一個 `run_review()`
- install 非互動錯誤訊息改成現行 flags

這些修正不單獨立 spec，因為它們不是新的外部 capability，而是為了讓本次新增能力建立在真實可靠的底層上。

## Risks / Trade-offs

- **[Risk] `doctor` 做太多，結果變慢或難懂** → Mitigation：預設只跑 deterministic checks；smoke tests 用明確 flag 啟用，輸出同時提供 human summary 與 machine-readable JSON。
- **[Risk] `apply` 第一版做太大，侵入既有 workflow** → Mitigation：只包裝現有 primitives，不做 full orchestration engine；先支援單 task / 單 packet 主路徑。
- **[Risk] benchmark 指標太理想化，仍無法代表真實專案** → Mitigation：要求跨多個 change、多類型 task，並保留 raw artifacts 供人工審視。
- **[Risk] health/doctor 邏輯重疊，後續維護成本上升** → Mitigation：明確定義 `health` 是 target probe，`doctor` 是 full preflight；底層 probe function 共用。
- **[Risk] 安裝後自動 smoke test 在某些環境造成噪音** → Mitigation：預設跑 cheap checks，需網路或模型呼叫的檢查提供 opt-in 或 clearly marked skip/reason。

## Migration Plan

1. 先補底層 probe 與 reliability fixes，確保 `doctor` 建立在可信狀態上。
2. 新增 `trly doctor` CLI 與 JSON/plain output。
3. 新增 `trly apply` 最小高階封裝，沿用現有 `pack`/`run_isolated`。
4. 擴充 benchmark fixture、metrics 與報告命令。
5. 更新 install 完成訊息與文件，導向 `doctor` 與 `apply`。

Rollback strategy:
- 若 `doctor` 或 `apply` 行為不穩，可保留既有 `health`、`pack`、`run --isolate` 路徑作為 fallback
- CLI 新命令應是 additive，不破壞現有腳本

## Open Questions

- `trly apply` 第一版是否要同時支援 `test-draft`，還是先只做 `implementation-draft`？
- benchmark 的 downstream quality 指標要不要直接納入人工標註欄位，還是先記錄 proxy metrics？
- install 完成後的 smoke test 應預設執行到哪一層，才不會讓第一次安裝體感太重？
