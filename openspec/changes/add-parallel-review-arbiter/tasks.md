## 1. 設定與安裝介面

- [x] 1.1 新增 review gate 設定模型，支援 reviewer entry、arbiter entry、persona、model 與 global timeout。
- [x] 1.2 更新 `trly install` 參數，加入 `--reviewers` 與 repeatable/comma-separated `--arbiter`。
- [x] 1.3 加入 `--global-timeout` 設定入口與預設值。
- [x] 1.4 將 `--review-chain` 標示為 deprecated，並在 migration window 只將原 primary entry 遷移為單一 reviewer。
- [x] 1.5 更新 wizard state 與互動流程，輸出 `reviewers`/`arbiter` 而非 review-chain。
- [x] 1.6 更新 `delegation.py` managed guidance 生成邏輯，描述 parallel reviewers、serial arbiters 與 Primary 的程式化決策責任。

## 2. Persona 與 Packet 模板

- [x] 2.1 新增 reviewer persona templates，涵蓋 `/review`、`/cso`、`/qa-only` 的 read-only JSON review 指令。
- [x] 2.2 新增 `templates/review-arbiter.md`，包含中立 arbiter、過濾噪音、解決衝突、嚴格 JSON 與非 editor 邊界。
- [x] 2.3 在 persona templates 記錄萃取來源 skill 名稱與日期。
- [x] 2.4 更新 `review-proposal.md`，改為宣告 reviewer unique output path 與 JSON schema。
- [x] 2.5 擴充 packer mode，新增 `review-arbiter` packet generation。
- [x] 2.6 實作 reviewer/arbiter packet 組裝，包含 proposal、design、tasks、delta specs、reviewer JSON 與 prior arbiter JSON。

## 3. Review Gate 執行器

- [x] 3.1 新增 review gate runner 模組，提供 `run_parallel_review()`、`run_arbiter_chain()` 與 `run_review_gate()`。
- [x] 3.2 使用 `asyncio.create_subprocess_exec()` 與 `asyncio.gather()` 並行啟動 reviewer `trly run` subprocesses。
- [x] 3.3 為每個 reviewer 以 agent + persona + 必要序號產生唯一 `--expect-output spec/delegation_review_<id>.json`。
- [x] 3.4 實作 global timeout，確保 reviewer 或 arbiter 超時時 gate fail loudly。
- [x] 3.5 實作 serial arbiter invocation，依序執行 CEO/product arbiter 與 engineering arbiter。

## 4. JSON 驗證與 DAG 決策

- [x] 4.1 定義 reviewer JSON schema 驗證，檢查 verdict、summary、findings 與必要欄位。
- [x] 4.2 定義 arbiter JSON schema 驗證，檢查 `decision`、`confidence`、`summary`、`actionable_items`、`conflict_resolution`，並要求 `REVISE` 的 actionable items 形成 binding revision contract。
- [x] 4.3 實作 final decision aggregation：任一 `REJECT` 為 STOP，任一 `REVISE` 為 revision gate，非 `REJECT` 皆可在 Primary 完成必要修訂後進入 apply。
- [x] 4.4 實作 fail-all reviewer policy，任一必需 reviewer 失敗不得進入 arbiter。
- [x] 4.5 將 reviewer `verdict` 與 arbiter `confidence` 保留為 advisory，不參與第一版 final decision aggregation。
- [x] 4.6 產生合併後的 `spec/delegation_review.md`，保留 reviewer/arbiter JSON artifact paths。
- [x] 4.7 確保 Arbiter 不會直接修改 OpenSpec artifacts；`REVISE` 後 Primary 只能依 Arbiter revision contract 修訂 proposal/design/tasks/specs，不得重判 reviewer 衝突或覆寫 Arbiter 決策。

## 5. CLI 與 DAG 整合

- [x] 5.1 新增或擴充 CLI command 以執行完整 review gate，並回傳穩定 exit codes。
- [x] 5.2 將 review gate 視為 DAG gate node，只有 `REJECT` 會阻止後續 Apply Wave；`REVISE` 在 Primary 完成修訂後可進入 apply。
- [x] 5.3 在 `REVISE` 時輸出 actionable items 與可在 Primary 修訂後進入 apply 的狀態。
- [x] 5.4 在 `REJECT` 時輸出 STOP 狀態，避免自動 apply 或自動重寫提案。
- [x] 5.5 若 `REVISE` 後選擇重跑 gate，確保會全量重跑所有 reviewers 與 arbiters。

## 6. 測試與遷移驗證

- [x] 6.1 新增 install CLI 測試，覆蓋 `--reviewers`、repeatable `--arbiter`、comma-separated `--arbiter`、`--global-timeout` 與 legacy `--review-chain` primary-only migration。
- [x] 6.2 新增 managed guidance 測試，確認輸出不再把 review 描述為 sequential chain。
- [x] 6.3 新增 parallel reviewer 測試，驗證 subprocess fan-out、unique output path、同 agent 不同 persona、不同 agent 相同 persona。
- [x] 6.4 新增 arbiter chain 測試，驗證 prior arbiter JSON 會傳入下一個 stage。
- [x] 6.5 新增 JSON schema failure 測試，覆蓋 missing/empty/invalid reviewer 與 arbiter artifacts。
- [x] 6.6 新增 revision contract schema 測試，覆蓋 `REVISE` 缺 target artifact、required change 或 acceptance criteria。
- [x] 6.7 新增 final decision aggregation 測試，覆蓋 `APPROVE`、`REVISE`、`REJECT`/STOP。
- [x] 6.8 新增 review gate exit code 測試，覆蓋 approve、revise、reject、timeout、argument failure 與 runtime failure。
- [x] 6.9 更新既有 tests，確保 apply-chain fallback 與 raw `trly run --targets` 行為未被改變。

## 7. Review-to-Apply Handoff

- [x] 7.1 輸出 machine-readable `spec/delegation_review_result.json`，包含 final decision、apply readiness flags、artifact paths、aggregated actionable items 與 target artifact baseline digests。
- [x] 7.2 新增 revision readiness 驗證入口，讓 `REVISE` 結果可在 apply 前檢查 target artifacts 是否已相對 gate-time baseline 改變。
- [x] 7.3 新增 handoff / readiness 測試，覆蓋 approve、revise-ready、revise-pending、reject。
