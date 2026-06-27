# Context Packer 強化建議

## 目的

這份文件整理 `harden-delegation-runtime` 完成後，對 `trly pack` / context packer 的下一步強化建議。
目標不是取代目前已落地的 deterministic scoped packer，而是在保留可預測性、可除錯性與 scope boundary 的前提下，提升 packet scope selection 的準確率。

## 現況摘要

目前 packer 已具備以下特性：

- 依 `mode` 載入固定 packet template。
- 預設只 inline scoped context，而非整個 change。
- 會抽取目標 task block。
- 會抽取 `design.md` 的 `Decisions` / `Risks / Trade-offs` / `Open Questions`。
- 會用 deterministic token overlap 選擇最相關的 delta spec。
- 無法唯一判斷 spec relevance 時，會 fallback 到全部 delta specs，並顯示 `Scope note:`。
- 支援 `--full-change-context` 與 `--dry-run --json`。

這個設計的優點是穩定、便宜、可重現；缺點是當 task 文案、spec 命名或 design 結構不夠清楚時，準確率會下降，容易落入 fallback 或帶入不足的 repo context。

## 問題陳述

目前準確率問題主要來自三個面向：

1. OpenSpec artifact 缺乏供 packer 使用的顯式結構訊號。
2. propose 結束後沒有針對「這個 task 未來是否能被正確打包」做檢查。
3. 當 deterministic 規則無法唯一決定 scope 時，只能保守 fallback 到全部 specs，無法在維持可審核性的前提下做更精準的 resolution。

## 建議方向

### 1. 在 propose artifact 中加入 packer 可直接消費的顯式訊號

優先建議加入下列結構：

- `task -> capability` mapping
- `task -> likely files / tests` 候選清單
- `task dependencies`（前置 task 或必要上下文）
- `design.md` 中額外可抽取的實作區段，例如：
  - `Implementation Notes`
  - `Affected Modules`
  - `Verification`

這些訊號的目的，是讓 packer 先依明確標註決定 scope，而不是優先依賴 token overlap 猜測。

### 2. 在 propose 後加入 packetability / pack-lint 檢查

新增一個 post-propose 檢查步驟，用來回答：

- 每個 task 是否能唯一對到一份 spec？
- 每個 task 是否能抽到合理的 task block？
- `design.md` 是否具備 packer 預期的 section？
- 哪些 task 目前一定會 fallback 到 all specs？
- 哪些 task 可能缺少實作所需的 repo file context？

這類檢查應儘量是 deterministic，輸出為可操作的診斷，而不是自動修改 proposal/design/tasks。

### 3. 擴充 `--dry-run --json` 的診斷能力

目前 dry-run 已能輸出 selected sections、byte estimate、fallback reason。下一步可考慮補上：

- `selection_mode`：`deterministic` / `explicit_mapping` / `model_fallback`
- `spec_candidates` 與各自分數
- `missing_signals`：例如缺少 task->capability mapping、缺少 design section
- `repo_context_gap`：判定目前 packet 可能仍缺少哪些 repo file 類型

這可以讓 primary 在真正委派前先知道 packet 是否健康。

### 4. 將 model fallback 限縮為 scope resolver，而不是 packet author

當 deterministic 規則無法唯一解析時，可以考慮引入 DeepSeek 作為 fallback，但建議只讓它做：

- 選擇最相關的 capability spec
- 建議要附帶的 design sections
- 建議要附帶的 task dependencies
- 建議要補充的 repo file 候選

不建議讓模型直接自由生成最終 packet。最終 packet 仍應由本地 renderer 根據結構化結果輸出。

### 5. 對 model fallback 加上明確 guard

若要引入 DeepSeek fallback，建議至少遵守下列限制：

- 只在 deterministic 無法唯一解析時才啟用。
- 輸出必須是結構化結果，而不是自由文字 packet。
- 模型只能從受限候選集合中選擇，不可任意發明路徑。
- 低信心時回退到保守模式（all specs + visible scope note）。
- `--dry-run --json` 必須明確顯示 fallback 已被使用。

## 建議執行順序

### Phase 1：先強化 deterministic 路線

1. 定義 `task -> capability` mapping 來源。
2. 補 proposal/design/tasks 的 packetability 檢查。
3. 擴充 dry-run 診斷資訊。
4. 視需要新增 design section extraction 規則。

### Phase 2：補 repo-aware 顯式訊號

1. 增加 `likely files / tests` metadata。
2. 增加前置 task / dependency context 規則。
3. 定義何時允許 packer 補帶 repo file 候選。

### Phase 3：最後才加入 model-assisted fallback

1. 定義 fallback 觸發條件。
2. 定義 DeepSeek 的結構化輸出 schema。
3. 將結果接回既有 `PacketPlan` / renderer。
4. 在 dry-run 中顯示決策來源、信心、fallback reason。

## 建議資料形狀

若未來引入 model-assisted scope resolver，建議回傳類似下列結構：

```json
{
  "specs": ["specs/delegation-packet-generation/spec.md"],
  "design_sections": ["Decisions", "Implementation Notes"],
  "task_dependencies": ["4.2"],
  "extra_reads": ["task_relay/packer.py", "tests/test_packer.py"],
  "confidence": 0.74,
  "reason": "task wording and design notes both point to packet generation behavior"
}
```

本地 packer 仍應保有最終控制權：

- 驗證路徑是否合法
- 驗證 section 是否存在
- 決定是否接受低信心建議
- 決定是否回退到保守模式

## 非目標

這份建議刻意不包含以下方向：

- 讓模型直接生成最終 packet markdown。
- 在 fallback 路徑中隱藏模型介入事實。
- 用 model fallback 取代 deterministic baseline。
- 引入高維護成本但目前尚未必要的完整 manifest 系統。

## 建議結論

最務實的強化路線是：

1. 先讓 propose 產生更好的結構訊號。
2. 在 propose 後加入 packetability 檢查。
3. 讓 packer 先吃顯式 mapping 與診斷資訊。
4. 只有在 deterministic 無法唯一解析時，才用 DeepSeek 做受限的 scope resolution fallback。

這樣可以在不犧牲可預測性與可審核性的前提下，逐步提高 context packer 的準確率。
