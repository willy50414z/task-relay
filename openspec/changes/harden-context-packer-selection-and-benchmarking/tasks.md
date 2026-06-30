## 1. Semantic Assembly Contract

- [x] 1.1 重構 context-packer 的 selection result 結構，明確區分 specs、design sections、task dependencies 與 repo context
- [x] 1.2 讓 model fallback 真正套用支援的 `design_sections`、`task_dependencies` 與 repo context selectors
- [x] 1.3 對不支援或無效的 model selection 欄位回傳 machine-readable rejection reason，避免靜默忽略
- [x] 1.4 補 regression tests，覆蓋 semantic selection accepted / rejected / downgraded 路徑

## 2. Budgeting And Trimming

- [x] 2.1 以 frozen `PacketPlan` 為前提，為 `plan_packet`、`build_packet` 與 `to_report()` 加入 `budget_status`、`budget_limit_bytes` 與 `trimmed_sections` 欄位
- [x] 2.2 實作以 bytes 為唯一強制單位的 hard-budget trimming，預設讀 per-mode 內建值並支援 sidecar `budget_bytes` override
- [x] 2.3 實作 deterministic trimming 順序，先裁減 model extra reads、再裁減 CLI extra reads、dynamic diff 與次要 context，並在核心 context 超限時回報 machine-readable violation
- [x] 2.4 補 packet budget 測試，驗證超限時的 trimming 順序與輸出穩定性
- [x] 2.5 補 trimmed packet integrity integration test，驗證 trimming 後的 `build_packet()` 輸出仍是結構完整、可供 delegate 使用的 prompt

## 3. Benchmark And Diagnostics

- [x] 3.1 擴充 `packer_eval` 報告結構，分開呈現 selection accuracy、context cost 與 quality outcome，並保持既有欄位相容
- [x] 3.2 採用 estimate-first with optional trace enrichment：無 trace 時回報 estimated tokens 與 unavailable 的 actual token/cost，有 trace 時再回填實際 usage
- [x] 3.3 為 benchmark sample 實作具名 quality proxy 欄位：`review_artifact_sections_present`、`verification_passed`、`apply_exit_code`、`retry_count`
- [x] 3.4 擴充 `pack-lint`，讓高風險 fallback、repo context gap 與 sidecar 格式陷阱更早暴露
- [x] 3.5 補 benchmark fixtures 與測試，驗證 packed-vs-full 報告的新欄位與 unavailable path

## 4. Sidecar Contract And Docs

- [x] 4.1 落實 JSON-only sidecar contract，明確規定 `packer.json`、`packer.yml`、`packer.yaml` 都必須使用 JSON syntax
- [x] 4.2 更新 sidecar parse / lint error 訊息，清楚說明支援格式與 migration 指引
- [x] 4.3 更新 `docs/context-packer-review.md`、`docs/review-apply.md` 與相關 CLI 文件，反映 semantic assembly、budgeting 與 benchmark contract
