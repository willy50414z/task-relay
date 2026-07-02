## Context

目前 Task Relay 已有 job session、stdout/stderr log、`last_output_at`、expected-output verification、trace JSONL、`PacketPlan.to_report()` 等基礎能力，但這些訊號還沒有被整合成「一次 delegation 為什麼成功或失敗」的可觀測性契約。

從 `/home/willy/code/invest_lab/.task_relay` 的近期紀錄可見三個實際痛點：

- DeepSeek error 高度集中在 20/30/45/60 秒 timeout 批次，但成功 job 中位數約 180 秒，最長接近 486 秒。這代表 timeout policy 與模型/packet 規模不匹配。
- Codex parent 端 usage limit 在數秒內失敗，會讓 parent proposal/apply flow 中斷。這應被記錄為可恢復 orchestration failure，而不是混在 delegate runtime failure 裡。
- 某些 DeepSeek job process exit 0 且 job status 為 `succeeded`，但 stdout 是詢問 reviewer/arbiter routing，沒有產出 pipeline 需要的 artifact。這是 semantic failure，不應算成功。

目前 `jobs.py` 的 foreground timeout 是硬 wall-clock 行為：`proc.wait(timeout=spec.timeout)` 或 `asyncio.wait_for(proc.wait(), timeout=spec.timeout)` 到點後直接 terminate process tree。雖然 log pump 會更新 `.last_output`，但 foreground path 不會因為近期仍有輸出而延長 timeout；`stall_timeout` 主要用於 status/background diagnostics。

## Goals / Non-Goals

**Goals:**

- 讓每次 apply/review/autopilot delegation 都能回答：
  - context-packer 是否正常運作？
  - packet 選了哪些 sections / repo references？
  - 是否有 missing signals、repo context gaps、trimmed sections？
  - job timeout 設定是什麼？soft deadline / hard cap / idle window 分別是多少？
  - timeout 前 process 是否還活著？最近一次 stdout/stderr 或 expected output activity 是什麼時間？
  - process 是自然退出、semantic failure、quota failure、timeout、stalled、還是被使用者 stop？
  - failure 是否可 resume？resume 從哪個 change/task/job 繼續？
- 把 timeout handler 改成可解釋的 state machine：soft deadline 可延長，hard timeout 不延長，terminate 前記錄 liveness/activity，grace period 後才 force kill。
- 讓 context-packer report 成為 first-class artifact，不再靠推測 logs 裡是否含有足夠上下文。
- 讓 review/apply output contract 的 semantic failure 在 job metadata、trace、debug summary 中一致呈現。

**Non-Goals:**

- 不更換 DeepSeek/Codex/Claude backend。
- 不引入外部 observability service、database、OpenTelemetry collector。
- 不自動修復 Codex usage limit 或購買額度；只記錄可恢復 failure 與 resume metadata。
- 不把 idle/stall 判斷當作模型仍在思考的可靠證明。Claude/DeepSeek JSON output 模式可能長時間不 stream token，因此 idle signal 只能用於 diagnostics 或明確啟用的 stall termination。
- 不修改已存在的歷史 `.task_relay/jobs` 紀錄；新欄位只影響新 job。

## Decisions

### D1: 建立 per-job runtime diagnostics artifact

每個 managed job 除了 `meta.json`、`stdout.log`、`stderr.log`、`combined.log` 外，新增 machine-readable diagnostics，例如：

- `.task_relay/jobs/<job-id>/diagnostics.json`

內容包含：

- `timeout_policy`: soft deadline、hard timeout、idle/stall window、grace period、extension count/limit。
- `activity`: `last_stdout_at`、`last_stderr_at`、`last_expected_output_at`、`last_activity_at`、activity source。
- `termination`: timeout reason、pre-kill liveness、pid/pgid、SIGTERM/SIGKILL timestamps。
- `semantic_contract`: expected outputs、schema validation status、interactive-output detection。
- `packet_report_path`: 若此 job 由 packed prompt 產生，連到 packer diagnostics。
- `resume`: 若 failure 可 resume，記錄 resume scope 與下一步。

替代方案是只擴充 `meta.json`。不採用，因為 `meta.json` 已經是 status 索引檔，塞入完整 packer/debug report 會讓 jobs list/status 的熱路徑變重。`meta.json` 保留摘要和 path，完整診斷放 `diagnostics.json`。

### D2: context-packer report 必須在 build packet 時寫出

context-packer 是否正常運作不能從 delegate stdout 反推。`PacketPlan.to_report()` 已能產生結構化 report，因此 `trly apply` / review packet build path 應在 delegate 啟動前寫出：

- `openspec/changes/<change>/apply/task-<task-id>-debug-summary.md`
- `openspec/changes/<change>/apply/task-<task-id>-packer-report.json`
- review gate 可寫入 `openspec/changes/<change>/review/<reviewer-id>-packer-report.json`

report 至少包含：

- `selection_mode`
- `byte_estimate`
- `budget_status`
- `budget_limit_bytes`
- `trimmed_sections`
- `missing_signals`
- `repo_context_gap`
- `spec_candidates`
- `sections`
- `repo_references`
- `cache_layout_enabled`
- `static_byte_count`
- `dynamic_byte_count`
- packet hash，用來對照 delegate 實際收到的 prompt。

替代方案是只把 report 印到 stdout。不採用，因為 timeout/job failure 時 stdout 可能截斷或混入模型輸出，不適合作為可靠 artifact。

### D3: timeout 使用 soft deadline + hard cap

現有 `timeout` 繼續作為 hard cap，避免打破既有「到點必停」的安全直覺。新增可選 soft deadline policy：

- `soft_timeout`: 到點時進行 liveness/activity decision。
- `hard_timeout`: 絕對上限，永不因 activity 延長。
- `idle_timeout`: 多久沒有 stdout/stderr/expected-output activity 才標記 stalled。
- `activity_extension`: soft deadline 到點但近期仍有 activity 時，每次延長的秒數。
- `max_extensions`: soft extension 次數上限，且不得超過 hard timeout。

重要語義：

- process 已死亡：不 kill，記錄 exit/expected-output/semantic status。
- process 活著且 soft deadline 到點：
  - 若 `last_activity_at` 在 activity window 內，延長 soft deadline，寫入 diagnostics event。
  - 若沒有近期 activity，標記 `stalled` 或 `timeout_pending_termination`，依 policy 決定是否 terminate。
- hard timeout 到點：不再延長，記錄 pre-kill liveness/activity，送 SIGTERM，grace period 後仍活著才 SIGKILL。

替代方案是「只要 log 還在輸出就無限延長」。不採用，因為模型或 wrapper 可能持續輸出 warning/heartbeat 但沒有實質進展，會造成永不結束的 job。

### D4: role-aware timeout defaults

不同 role 需要不同預設值：

- DeepSeek apply implementation/test draft：hard timeout 預設至少 1800 秒。
- DeepSeek review packet：hard timeout 預設至少 900 秒。
- Full review gate：global hard timeout 預設至少 2400 秒，因為包含 parallel reviewers 與 serial arbiters。
- Codex parent proposal/apply orchestration：hard timeout 可維持較長，但 usage limit 應快速分類成 resumable failure。
- Stall/idle window 預設 900 秒，且預設只做 diagnostics，不在 foreground path 主動 kill。

CLI 應保留手動 override。若使用者明確傳入較短 timeout，系統可接受，但 diagnostics 必須標記 `timeout_policy_source=user_override`，避免事後誤判為 backend 不穩。

### D5: semantic output contract 與 process status 分離

job process exit 0 只能代表 wrapper process 成功，不代表 delegation semantic success。系統應分離：

- `process_status`: `exited_zero` / `exited_nonzero` / `timeout` / `killed`
- `contract_status`: `passed` / `missing_output` / `empty_output` / `invalid_json` / `schema_invalid` / `interactive_output`
- `job.status`: pipeline-facing final status；只要 contract failed，就不得是 `succeeded`。

review/apply path 必須在 job metadata 與 diagnostics 中記錄 expected output path 與 validation reason。reviewer/arbiter JSON schema validation failure 要出現在 review summary，而不是只拋 exception。

### D6: Codex parent quota failure 轉成 resumable orchestration failure

Codex usage limit 是 parent orchestration failure，不是 DeepSeek delegate failure。當 error text 命中 hard quota / usage limit pattern 時，系統應寫出：

- failure kind：`parent_quota_exhausted`
- target/model
- job id/log path
- source command 或 workflow phase
- last known change/task/session
- retry-after 或從 error text 解析出的 next available time，若可取得
- suggested resume command 或 resume marker path

替代方案是讓 `AgentQuotaError` 照舊 bubbling。這會保留 stack trace，但缺少 autopilot 可讀的 resume contract。

## Risks / Trade-offs

- [Risk] soft extension 可能讓真的卡住的 process 多跑一段時間。→ Mitigation: hard timeout 永不延長；extension 次數與延長秒數有上限。
- [Risk] idle/stall signal 對不 stream output 的模型不可靠。→ Mitigation: 預設只把 idle/stall 作為 diagnostics，不在 hard timeout 前主動 kill，除非使用者明確啟用 stall termination。
- [Risk] diagnostics artifact 增加檔案數量。→ Mitigation: `meta.json` 只保存摘要與 path，完整 report 放單獨 JSON/Markdown；cleanup 跟隨 job cleanup。
- [Risk] context-packer report 可能含 repo file paths。→ Mitigation: report 只寫入本地 `.task_relay` / OpenSpec change artifact，不送外部服務；沿用現有 UTF-8 text-file rule。
- [Risk] role-aware defaults 可能和使用者手動 timeout 衝突。→ Mitigation: 手動 override 優先，但 diagnostics 明確標記來源與過短 timeout warning。
- [Risk] semantic failure detection 可能誤判合法中文說明為互動式提問。→ Mitigation: interactive-output detection 只作為 contract failure 的補充；review/apply 以 expected output/schema validation 為主要判定。

## Migration Plan

1. 先新增 diagnostics 寫入與 timeout decision logging，不改預設 termination 行為。
2. 接著加入 soft deadline fields 與 role-aware timeout policy，讓 apply/review callers 採用新預設。
3. 再讓 semantic contract status 進入 job final status、trace summary、review/apply debug summary。
4. 最後加入 parent quota resumability metadata 與 trace/CLI 顯示。

Rollback strategy:

- 若 soft deadline 行為造成 regression，可關閉 soft extension，保留 hard timeout 與 diagnostics。
- 若 diagnostics artifact 寫入失敗，不得讓 delegate job 本身成功變失敗；應在 meta 中記錄 diagnostics write error，但仍依 process/contract status 判定。

## Open Questions

- `--timeout` 是否長期維持 hard cap，並新增 `--soft-timeout`，還是只在內部 JobSpec 支援 soft timeout？建議 v1 維持 CLI 相容，先只在 internal policy 使用 soft deadline。
- parent resumability 是否只寫 marker，還是新增 `trly resume` CLI？建議 v1 先寫 marker 與 suggested command，不新增完整 resume orchestrator。
