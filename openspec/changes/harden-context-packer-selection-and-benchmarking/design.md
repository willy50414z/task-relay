## Context

`task_relay/packer.py` 目前已經有 deterministic selection、sidecar explicit mapping、dynamic diff repo references 與 model fallback，但這些能力之間的 contract 尚未完全對齊。最明顯的落差是 model fallback prompt 宣稱可回傳 `design_sections`、`task_dependencies`、`extra_reads`，實作卻只會套用 `specs`，導致 context-packer 對外看起來像 semantic context assembly，實際上只是 semantic spec selection。

另一個問題是 packet 目前只有 `byte_estimate`，沒有 hard budget 與 deterministic trimming。當 `extra_reads`、dynamic diff 或 ambiguous-task fallback 疊加時，packet 大小可能快速失控，讓「縮小 context」功能反而成為 token 膨脹來源。

最後，`task_relay/packer_eval.py` 的 packed-vs-full benchmark 只量 bytes 與本地時間，token 欄位是空值，`quality_proxy` 也只是 fixture 中的靜態輸入，無法證明 packed context 在真實 delegate 流程中的成本與品質表現。

## Goals / Non-Goals

**Goals:**
- 讓 context-packer 的 model fallback schema 與 packet assembly 行為一致。
- 引入 packet 預算、trimming 順序與可觀測輸出，避免 packet 無上限膨脹。
- 擴充 benchmark / eval 報告，讓 packed-vs-full 比較至少能觀察 token、成本與 downstream quality proxy。
- 強化 pack diagnostics，使高風險 fallback 與 sidecar 格式問題能在正式委派前被發現。

**Non-Goals:**
- 不在這個 change 內重新設計整個 OpenSpec artifact 結構。
- 不引入新的外部 vector DB、embedding index 或持久化檢索系統。
- 不承諾一次解決所有 retrieval precision 問題；本 change 先把 deterministic-first pipeline 做到可控、可驗證。

## Decisions

### 1. 保持 deterministic-first，model fallback 只做受限 disambiguation

context-packer 應維持：

1. explicit sidecar mapping
2. deterministic heuristic
3. model fallback
4. full fallback

這個順序，而不是把 model 當成主要 routing 機制。理由是 packet assembly 必須可預測、可診斷，否則 benchmark 結果與 bug 重現都會變得不穩。

替代方案是讓 model 直接決定整份 packet 的所有內容，但這會提高不可預測性，也會讓「token 下降」和「品質持平」更難驗證。

### 2. 把 model fallback contract 收斂成真正可執行的 packet mutation

model fallback 若宣稱可回傳：

- `specs`
- `design_sections`
- `task_dependencies`
- `extra_reads`

則 packet builder 必須真的把這些結果套進 `PacketPlan`。若某欄位暫時不支援，就不應出現在 prompt 與回報 schema 中。

我們選擇「補齊 contract」，而不是單純刪掉 schema，因為 review 與 apply 對 bounded context 的真正需求，本來就不只 spec selection。

sidecar 與 model fallback 的優先序如下：

1. CLI 顯式輸入 (`extra_reads`, `diff_file`, `diff_from`)
2. sidecar 顯式 mapping
3. model fallback 補充缺漏欄位

同一欄位若 sidecar 已明確指定，model fallback 只能補充未指定內容，不可覆蓋 sidecar 的顯式選擇。`extra_reads` 來源會先合併、去重，再進入 trimming 階段。

### 3. 導入 hard budget 與 deterministic trimming

`PacketPlan` 需要新增預算相關欄位，例如：

- `budget_status`
- `trimmed_sections`
- `budget_limit_bytes`

本 change 採用 **bytes** 作為唯一強制執行的 trim 單位。`byte_estimate` 會直接對應 trim loop 與報告中的 budget 判定。token 只作為 benchmark 報告中的觀測或估算欄位，不作為 trim threshold。

budget 來源與語義如下：

- 預設來源：`trly pack` 內建 per-mode 預設值
- override 來源：change sidecar 的 `budget_bytes`
- 行為語義：**hard limit**。超過預算時必須進入 deterministic trimming，而不是僅報告超限

packet 超出預算時，應按固定順序裁減：

1. optional extra reads
2. dynamic diff repo refs
3. non-required design sections
4. lower-ranked specs
5. full fallback downgrade note

這比「只回報 byte_estimate 讓使用者自己猜」更符合可操作的工程系統。

spec 排名規則如下：

1. sidecar explicit capability 指定的 spec 永遠視為 core spec，不可先於 heuristic specs 被裁減
2. 其餘 spec 依 deterministic score 由高到低排序
3. score 相同時依 spec path 字典序排序，確保 trimming 穩定

若預算小到連 core task / core spec context 都無法完整容納，系統應回報 machine-readable budget violation，而不是靜默裁掉核心內容。

### 4. benchmark 分成 selection / cost / quality 三層

未來 benchmark 應同時回答三個問題：

1. 選得準不準
2. 真的省多少 token / cost
3. downstream quality 有沒有退化

因此 `task_relay/packer_eval.py` 的報告要擴充為三層：

- selection accuracy：spec/task/design/repo context recall / precision
- context cost：bytes、estimated tokens、actual tokens、cost
- quality outcome：review artifact completeness、apply verification pass rate、fallback / retry rate

本 change 採用 **estimate-first with optional trace enrichment**：

- 無 trace 時：報告 deterministic estimated token 欄位與 `unavailable` 的 actual token / cost 欄位
- 有 trace 時：以 trace usage 回填 actual token / cost

這樣 benchmark 可以在沒有 live delegate integration 的情況下先落地，同時保留之後接真實 usage 資料的能力。

### 5. sidecar 格式要麼真正支援 YAML，要麼明確收斂到 JSON

目前檔名接受 `packer.yml` / `packer.yaml`，但解析是 `json.loads()`。這個 DX 不一致會直接造成誤用。

此 change 明確採用 **JSON-only contract**：

- `packer.json`、`packer.yml`、`packer.yaml` 都必須包含 JSON syntax
- `.yml/.yaml` 不提供一般 YAML 語法寬容解析
- 非 JSON 內容必須以清楚的 lint / parse error 失敗，不可靜默忽略

這個選擇符合 deterministic-first 原則，也能用最小 diff 把現有行為說清楚。

## Risks / Trade-offs

- [Risk] model fallback contract 補齊後，packet builder 邏輯會變複雜
  → Mitigation: 將 selected specs、design sections、dependencies、repo refs 分離成明確的 selection result 結構，而不是在字串拼接階段隱式處理。

- [Risk] hard budget 可能導致 packet 少掉某些次要上下文，讓個別 delegate 結果變差
  → Mitigation: 保留 `trimmed_sections` 與 `budget_status`，並在 dry-run / benchmark 中讓使用者看到被裁掉的內容。

- [Risk] 真實 token / cost benchmark 可能需要 trace 或 delegate integration，讓測試成本增加
  → Mitigation: 先讓 benchmark 支援可選的 trace-backed metrics；無 trace 時仍保留 bytes-only fallback，但不得再宣稱品質不變。

- [Risk] sidecar 格式收斂可能讓少數既有使用方式需要調整
  → Mitigation: 在 lint 與文件中提供清楚 migration 說明，優先避免 silent parse failure。

## Migration Plan

1. 先調整 packet selection / model fallback result schema，讓 contract 對齊。
2. 為 `PacketPlan` 與 `to_report()` 補上 budget 與 trimming 相關欄位。
3. 擴充 `pack-lint`、`pack-metrics`、`pack-benchmark` 的輸出結構。
4. 補齊 regression tests 與 benchmark fixtures。
5. 更新文件與使用說明，明確描述 sidecar 格式、benchmark 指標與新 diagnostics。

Rollback 方式：

- 若新的 budget/trimming 導致問題，可先保留 diagnostics 與 reporting，暫時停用 hard enforcement。
- 若 trace-backed benchmark 不穩，可退回 bytes-only 模式，但文件不得再聲稱 token / quality 已被驗證。

## Open Questions

- `budget_bytes` 是否只先放 sidecar override，還是同一輪就補 `trly pack --packet-budget` CLI override？
