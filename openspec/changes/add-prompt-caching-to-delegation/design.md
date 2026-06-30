## Context

目前 delegation pipeline 的封包是純文字，透過 `claude --print` CLI 以 stdin 傳送。Anthropic Prompt Caching 需要兩件事：(1) prompt 內容必須將可快取部分集中在前面，並在 API request 中以 `cache_control: {"type": "ephemeral"}` 標記；(2) 需要直接走 Anthropic API SDK，因為 CLI 不暴露 cache breakpoint 控制。

packet assembly 現有邏輯（`packer.py:1171-1181`）把所有 section 以 flat 順序串接，沒有區分靜態/動態。runner 側目前只有 CLI-based 實作（`ClaudeRunner`、`CodexRunner`、`DeepSeekRunner`），沒有任何 SDK-based runner。

Anthropic cache TTL 為 5 分鐘，server-side 基於內容 hash 自動管理快取。連續委派同 change 的多個 task 時，只要靜態部分內容完全一致，API 就會自動命中快取。

## Goals / Non-Goals

**Goals:**
- 讓 packet 輸出支援 cache layout：靜態內容（模板、spec、design）在前，動態內容（task block、notes、extra reads）在後，中間以明確 marker 分隔
- 新增基於 Anthropic API SDK 的 runner，將 packet 中的 cache marker 轉換為 `cache_control` API 參數
- 讓同 change 連續委派的 token 消耗可觀測（cache write/read tokens 出現在 usage 報告中）
- 既有 CLI runner 的執行方式與 runner contract 不變；cache layout 會改變 prompt 內容排列，因此需用回歸測試確認 CLI runner 仍能消費該封包

**Non-Goals:**
- 不修改 `claude --print` CLI 的行為或對其新增 cache 支援
- 不實作跨 session 的持久化快取（依賴 Anthropic server-side cache）
- 不為 DeepSeek / Codex runner 新增 cache 支援（它們的 API 不一定有等效機制）
- 不在這個 change 內實作「預先寫入 cache」或「cache warming」

## Decisions

### 1. 用 text marker 標記 cache breakpoint，而非結構化 contract

**選擇**：在 packet 文字中插入特殊 marker `<!-- trly:cache_break -->`，由 SDK runner 解析並切割 content blocks。

**替代方案**：
- 改變 `build_packet()` 回傳型別（從 `str` 變成 structured object）：這會破壞所有現有 caller（`handle_apply`、`handle_pack`、`review_gate`），diff 過大
- 分開回傳 static 和 dynamic 兩個字串：caller 需要改 signature，且 cache metadata 要另尋管道傳遞

**理由**：text marker 可讓現有 caller 維持 `str` 型別，不需要改動 runner contract。cache layout 不只是多一行 marker，也會把 scope note、budget note、repo references 等 task-scoped 內容放到後段；這會改變所有 runner 看到的 prompt 組織。此重排不應改變 delegation 結果，因為模板、spec、design、task block、scope/budget/repo refs 的語義內容都保留，只是依快取穩定性重新排序；仍需新增「CLI runner + cache layout packet」回歸測試確認既有 CLI runner 可正確消費。

### 2. Cache layout 的靜態/動態邊界

**選擇**：cache breakpoint 放在 spec 與 design section 之後、task block 之前。

```
[Template]                      ← static system instructions
<!-- trly:template_end -->      ← deterministic template boundary
[Spec sections]                 ← static
[Design sections]               ← static
<!-- trly:cache_break -->
[Task block]                    ← dynamic
[Scope note / Budget note]      ← dynamic
[Repo references]               ← dynamic
[Extra reads]                   ← dynamic
```

**理由**：
- 模板在所有同 mode delegation 中完全相同
- Spec 和 design section 是 change-scoped，同 change 的所有 task 共用
- Task block、scope note、budget note、extra reads 是 task-scoped，每次 delegation 可能不同
- Repo references 在有 `--diff-from` 時可能跨 task 不同（不同 task 改不同檔案），歸在動態側較安全
- `<!-- trly:template_end -->` 明確定義模板結束位置，避免 SDK runner 透過標題、空行或 section 名稱啟發式判斷模板邊界

### 3. SDK runner 實現方式

**選擇**：新增 `AnthropicSDKRunner`，使用 `anthropic` Python SDK，將帶有 cache marker 的 prompt 轉換為 Messages API request。

核心邏輯：
1. 收到 `AgentRunRequest` 時，以完整 marker 字串精確檢查 prompt 是否包含 `<!-- trly:cache_break -->`
2. 若有：在 cache marker 處切割 static / dynamic portion；static portion 再以 `<!-- trly:template_end -->` 精確切出 template 與 spec/design content
3. template 作為單一 `system` text block，附加 `cache_control: {"type": "ephemeral"}`
4. spec/design static portion 作為單一 user content block，附加 `cache_control: {"type": "ephemeral"}`
5. dynamic portion 作為單一 user content block，不附加 `cache_control`
6. 若無 cache marker：整個 prompt 作為單一 user content block，不做 system prompt 分離、不附加 cache_control（向後相容於無 marker 的 packet）
7. 呼叫 `anthropic.Anthropic().messages.create()`，傳入 `model`、`max_tokens`、`system`、`messages`
8. 解析 response，從 `usage.cache_creation_input_tokens` 和 `usage.cache_read_input_tokens` 提取 cache metrics
9. 回傳 `AgentRunResult`，`usage` 欄位包含 cache 相關 token 數

**替代方案**：
- 用 `system` prompt 放靜態內容：Anthropic 也支援 system prompt 的 cache_control，但 system prompt 在 messages 之前，可以分開 cache。不過 system prompt 有長度限制，大量 spec 內容不一定適合全放 system。

**理由**：直接走 SDK 是最精準控制 `cache_control` 的方式。SDK runner 與 CLI runner 並存，使用者可透過 `--target claude-sdk` 選擇。

### 4. 模板內容放入 system prompt

**選擇**：cache layout 中的模板部分（任務指令、輸出格式、非目標、逾時等）從 user message 移入 system prompt，並在 system prompt 上也附加 cache_control。

**理由**：
- 模板是 mode-scoped 的靜態指令，最適合快取
- system prompt 獨立於 user message，語義上更乾淨（指令 vs 內容）
- system prompt 同樣支援 `cache_control`，第一次寫入後續命中

實際 API request 結構：
```
system: [{type: "text", text: "<template>", cache_control: {type: "ephemeral"}}]
messages: [
  {role: "user", content: [
    {type: "text", text: "<spec sections + design sections>", cache_control: {type: "ephemeral"}},
    {type: "text", text: "<task block + notes + repo refs + extra reads>"}
  ]}
]
```

模板提取規則：
- `build_packet(cache_layout=True)` SHALL 在模板後插入獨立一行 `<!-- trly:template_end -->`
- SDK runner SHALL 只用完整 marker 精確比對切割模板，不得以標題名稱、空行數或內容片段猜測
- 若 cache marker 存在但 template marker 缺失，SDK runner SHALL 保守地將整個 static portion 放在 user static block，不得把 spec/design 誤移入 system prompt

### 5. Runner 註冊與 CLI 介面

**選擇**：在 `agents/__init__.py` 中以 `"claude-sdk"` 名稱註冊新 runner。`trly apply --target claude-sdk` 選擇使用。

不新增 `--cache` flag。當使用 `claude-sdk` target 且 packet 包含 cache marker 時，SDK runner 會依 marker 轉換為 API `cache_control`；packet 不含 marker 時，SDK runner 仍可正常運作（無 cache）。

**理由**：cache 是 SDK runner 的內建行為，不是獨立開關。減少 CLI 參數數量。

cache layout 的啟用責任在 caller / primary agent。Task Relay 提供 `build_packet(cache_layout=True)` 與 SDK runner 的能力，但不在 `trly apply` 層級用「同 change + 同 mode + 5 分鐘」自動偵測來改變封包 layout；若未來要新增自動偵測，需另補 session tracking spec 與 task。

### 6. Benchmark 擴充

**選擇**：在 `packer_eval` 的 report 中新增 `cache_metrics` 區塊，僅在 SDK runner 有回傳 usage 時填入。

欄位：
- `static_byte_count`：cache breakpoint 之前的 byte 數
- `dynamic_byte_count`：cache breakpoint 之後的 byte 數
- `cache_write_tokens`：API usage 回報的 cache 寫入 token 數
- `cache_read_tokens`：API usage 回報的 cache 讀取 token 數
- `cache_hit`：此請求是否命中 cache
- `estimated_savings_tokens`：以 API usage 的 cache token 欄位為權威來源計算；沒有 API usage 時只能輸出明確標示為非權威的 byte-based 粗估

## Risks / Trade-offs

- [Risk] text marker 解析脆弱，若 packet 內容本身包含 `<!-- trly:cache_break -->` 字串會誤切割
  → Mitigation: marker 使用足夠獨特的完整字串，runner 端只做完整 marker 精確比對；packer 端將內容中的 marker escape 成完全不含 `trly:cache_break` 子字串的形式

- [Risk] SDK runner 需要 `ANTHROPIC_API_KEY`，增加部署依賴
  → Mitigation: CLI runner 保持不變，SDK runner 為 opt-in。`trly doctor` 檢測 SDK runner 可用性

- [Risk] cache TTL 5 分鐘限制，若 task 之間間隔過長則 cache 失效
  → Mitigation: 在 trace/benchmark 中記錄 cache hit/miss，讓使用者可觀測實際命中率。不做 cache warming

- [Risk] system prompt 放模板內容可能遇到長度限制
  → Mitigation: 模板通常很短（~2KB），遠低於 system prompt 限制。若未來模板變長，可將部分內容移回 user message 的第一個 block（同樣可 cache）

- [Risk] 同 change 的不同 task 可能選到不同 spec（model fallback 不穩定時），導致靜態內容不同、cache miss
  → Mitigation: 這實際上是正確行為——選到不同 spec 時不該命中舊 cache。這也督促 model fallback 穩定性

## Migration Plan

1. 先在 `packer.py` 的 `build_packet()` 新增 `cache_layout` 參數（預設 False），啟用時插入 cache breakpoint marker
2. 新增 `AnthropicSDKRunner`，實作 marker 解析與 `cache_control` 轉換
3. 在 `agents/__init__.py` 註冊 `claude-sdk`
4. 擴充 benchmark 報告結構，加入 cache metrics
5. 補測試：marker 解析、cache layout 輸出、SDK runner request 結構驗證
6. 預設行為不變；cache layout 由 caller / primary agent 在呼叫 `build_packet(cache_layout=True)` 的路徑啟用，`claude-sdk` target 在看到 cache marker 時自動轉換為 API `cache_control`

Rollback：若 SDK runner 有問題，使用者切回 `--target claude`（CLI runner）即可。若 cache layout 有問題，caller 停止傳入 `cache_layout=True`。

## Open Questions

- system prompt 的 cache_control 是否需要與 user message 分開的 breakpoint？還是合併成一個 cache point？
- 是否要支援 multi-turn conversation 的 cache 持續（目前 delegation 都是 single-turn，但未來可能擴充）？
