# Context Packer Review

本文整理目前 `task-relay` 內 `context-packer` 的設計狀態、已落地的改善，以及仍值得持續觀察的風險，聚焦於 `task_relay/packer.py`、`task_relay/packer_eval.py` 與對應測試。

## 結論摘要

目前的 `context-packer` 已經從「可用骨架」收斂到「可檢查的 bounded context 組裝器」：

- 能把 OpenSpec change 壓縮成 bounded packet
- 支援 deterministic selection、sidecar explicit mapping、dynamic diff context
- 在 ambiguity 發生時可退回 full spec fallback，並保留 dry-run / metrics / lint 報告
- model fallback 已能實際影響 spec、design sections、task dependencies 與 extra reads
- packet 已有 hard budget、deterministic trimming 與 machine-readable violation 狀態

它現在已能較可信地支撐「有界 context」與「可診斷 trimming」這兩個產品敘述；但若要更強地宣稱「token 顯著下降且品質穩定」，仍有幾個限制需要持續注意：

1. benchmark 的 actual token / cost 仍仰賴可選 trace enrichment，不是每個 sample 都有 live usage。
2. deterministic heuristic 仍以 token overlap 為主，長期 precision 上限有限。
3. budget 與 trimming 雖已可觀測，但預設值是否最適合真實大型 repo，仍需要實戰校準。

## 現況優點

### 1. selection 策略仍維持 deterministic-first

目前 selection 順序是：

1. explicit mapping
2. deterministic heuristic
3. model fallback
4. full fallback

這個排序讓 `context-packer` 仍然偏向可預測、可重現、可診斷，而不是把模型變成預設 routing 機制。

### 2. 可觀測性比一般 prompt packer 好，且已補上 budget 診斷

`PacketPlan` 已經有一些實用的診斷欄位：

- `selection_mode`
- `fallback_reason`
- `spec_candidates`
- `missing_signals`
- `repo_context_gap`
- `resolver_cache_key`
- `budget_status`
- `budget_limit_bytes`
- `trimmed_sections`

這讓 `trly pack --dry-run --json` 與 `trly pack-lint` 可以作為工程診斷工具，而不只是字串產生器。

### 3. 測試骨架合理，且新增 semantic / budget regression

目前測試已覆蓋：

- target task block extraction
- explicit sidecar mapping
- dynamic diff repo references
- model fallback accepted / rejected / unsupported selector path
- design sections / task dependencies / extra reads 會真的進入 packet
- packet budget trimming 順序與 machine-readable violation
- packed vs full benchmark 的新欄位與 unavailable path
- `pack-lint` 對 fallback / budget / JSON-only sidecar 的診斷

## 已完成改善

### 1. model resolver contract 已與實作對齊

相關位置：

- [task_relay/packer.py](/home/willy/code/task-relay/task_relay/packer.py)

`_call_model_resolver()` 與 `_apply_model_selection()` 現在已對齊。model fallback 可回傳並實際套用：

- `specs`
- `design_sections`
- `task_dependencies`
- `extra_reads`
- `reason`

另外，若模型回傳：

- 未知 selector
- 無效 spec path
- 不支援的 selection shape
- 缺失的 extra reads

report 會帶 machine-readable rejection / downgrade reason，而不是靜默忽略。

### 2. packet 已有 hard budget、deterministic trimming 與 violation contract

相關位置：

- [task_relay/packer.py](/home/willy/code/task-relay/task_relay/packer.py)

現在 packet plan/report 會顯示：

- `budget_status`
- `budget_limit_bytes`
- `trimmed_sections`

trimming 順序固定為：

1. model extra reads
2. CLI extra reads
3. dynamic diff repo refs
4. non-core design sections
5. lower-ranked specs

若裁到只剩核心 task / core spec / core repo context 仍超限，`build_packet()` 會以 machine-readable `packet_budget_violation` 失敗，而不是靜默刪除核心內容。

### 3. benchmark 報告已拆成 selection / cost / quality 三層

相關位置：

- [task_relay/packer_eval.py](/home/willy/code/task-relay/task_relay/packer_eval.py)

`run_eval_set()` 與 `run_context_benchmark()` 現在除了保留既有欄位外，也新增：

- `selection_accuracy`
- `context_cost`
- `quality_outcome`

`context_cost` 採用 estimate-first with optional trace enrichment：

- 無 trace 時：`actual_*` 欄位明確標記為 `unavailable`
- 有 trace filter 時：可回填實際 token / cost

`quality_outcome` 則固定使用具名 machine-readable 欄位：

- `review_artifact_sections_present`
- `verification_passed`
- `apply_exit_code`
- `retry_count`

### 4. sidecar contract 已明文化為 JSON-only

相關位置：

- [task_relay/packer.py](/home/willy/code/task-relay/task_relay/packer.py)
- [task_relay/cli/pack.py](/home/willy/code/task-relay/task_relay/cli/pack.py)

檔名仍接受：

- `packer.json`
- `packer.yml`
- `packer.yaml`

但三者內容都必須是 JSON syntax。parse error 與 `pack-lint` 都會清楚提示這個限制，避免使用者誤以為一般 YAML 語法也可直接使用。

## 仍需注意的風險

### 1. deterministic heuristic 仍偏脆弱

目前 `_score_specs()` 仍以簡單 token overlap 為主。當：

- spec 數量增多
- task 命名模糊
- 多個 spec 共用類似詞彙

就更容易出現 tie，然後退回 full fallback。這在 demo repo 還可接受，但對長期大型專案來說 precision 上限有限。

### 2. actual token / cost 並非每次 benchmark 都能量到

benchmark 已支援 optional trace enrichment，但若：

- 沒有 trace
- eval sample 沒提供對應 trace filter
- trace record 不足以區分 packed / full

就只能回報 estimated tokens 與 `unavailable` 的 actual usage。這比假裝量到了更誠實，但仍不足以單靠 benchmark 就下定論。

### 3. 預設 budget 需要實戰校準

目前 per-mode default budget 已存在，但這些值仍是工程預設，不是產品最佳值。實際大型 repo 可能需要依：

- review / apply agent 差異
- model context window
- 工作型態

做更細的校準或暴露更多 override。

## 建議的產品化方向

如果 `context-packer` 要成為 `task-relay` 的長期核心能力，我會把它定義成：

> A deterministic-first, inspectable context assembly pipeline with optional semantic disambiguation.

這個定義的重點不是「很聰明」，而是：

- 可預測
- 可診斷
- 可量測
- 在需要時才使用模型 disambiguation

## 相關檔案

- [task_relay/packer.py](/home/willy/code/task-relay/task_relay/packer.py)
- [task_relay/packer_eval.py](/home/willy/code/task-relay/task_relay/packer_eval.py)
- [task_relay/cli/pack.py](/home/willy/code/task-relay/task_relay/cli/pack.py)
- [tests/test_packer.py](/home/willy/code/task-relay/tests/test_packer.py)
- [docs/review-apply.md](/home/willy/code/task-relay/docs/review-apply.md)
