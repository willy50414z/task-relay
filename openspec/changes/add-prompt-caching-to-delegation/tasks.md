## 1. Packet Cache Layout

- [x] 1.1 `[delegate:codex]` 在 `packer.py` 的 `build_packet()` 新增 `cache_layout: bool = False` 參數，控制是否啟用快取排列；depends: none；static: `specs/packet-cache-layout/spec.md` + `design.md` Decisions 1/2/5；dynamic reads: `task_relay/packer.py`
- [x] 1.2 `[delegate:codex]` 實作 `_build_cache_packet()`，將 static sections（template、specs、design）排在 `<!-- trly:cache_break -->` 之前，dynamic sections（task block、notes、repo refs、extra reads）排在之後；depends: 1.1；static: `specs/packet-cache-layout/spec.md` + `design.md` Decisions 1/2；dynamic reads: `task_relay/packer.py`
- [x] 1.3 `[delegate:codex]` 實作 marker escape：若任何 section 內容包含 `<!-- trly:cache_break -->` 字面字串，自動替換為不含 `trly:cache_break` 子字串的安全形式（例如 HTML entity encoding），避免誤切割；depends: 1.2；static: `specs/packet-cache-layout/spec.md` marker scenarios；dynamic reads: `task_relay/packer.py`
- [x] 1.4 `[delegate:codex]` 在 `PacketPlan.to_report()` 中新增 `cache_layout_enabled` 與 `static_byte_count`、`dynamic_byte_count` 欄位；depends: 1.2；static: `specs/packet-cache-layout/spec.md` + `specs/packet-cache-benchmarking/spec.md`；dynamic reads: `task_relay/packer.py`
- [x] 1.5 `[delegate:codex]` 將 `trly pack` CLI (`cli/pack.py`) 的 `handle_pack()` 串接 `cache_layout` 參數，確認 caller 傳入的值會正確傳遞給 `build_packet()`；depends: 1.1/1.4；static: `design.md` Decision 5；dynamic reads: `task_relay/cli/pack.py`, `task_relay/cli/__init__.py`, `task_relay/cli/apply.py`
- [x] 1.6 `[delegate:codex]` 在 cache layout 中於模板結尾插入獨立一行 `<!-- trly:template_end -->`，提供 SDK runner 確定性的 system/user 邊界；depends: 1.2；static: `specs/packet-cache-layout/spec.md` template-boundary scenarios + `design.md` Decision 4；dynamic reads: `task_relay/packer.py`
- [x] 1.7 `[codex-only]` 將 propose/apply 委派任務整理成 delegate-ready queue：每個 task 明確標示可委派粒度、相依順序、context-packer 需要固定在 static side 的 spec/design 範圍，以及 task-scoped dynamic reads，確保 apply 階段有可分派的任務封包；depends: 1.1-5.9；static: 本 change 全部 specs + `design.md`；dynamic reads: `openspec/changes/add-prompt-caching-to-delegation/tasks.md`

## 2. SDK Cache Runner

- [x] 2.1 `[delegate:codex]` 確認 `anthropic` Python SDK 為專案依賴（加入 `pyproject.toml` 若尚未存在）；depends: none；static: `specs/sdk-cache-runner/spec.md`；dynamic reads: `pyproject.toml`
- [x] 2.2 `[delegate:codex]` 新增 `task_relay/agents/anthropic_sdk.py`，實作 `AnthropicSDKRunner` 類別；depends: 1.2/1.6/2.1；static: `specs/sdk-cache-runner/spec.md` + `design.md` Decisions 3/4/5；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.3 `[delegate:codex]` 實作 `_parse_cache_markers()`：以完整 marker 字串精確匹配 `<!-- trly:cache_break -->`，切割為 static 與 dynamic portions，禁止用 `trly:cache_break` 子字串做寬鬆判斷；depends: 2.2；static: `specs/sdk-cache-runner/spec.md` marker scenarios；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.4 `[delegate:codex]` 實作 `_build_messages()`：將 spec/design static portion 作為單一 user content block 並附加單一 `cache_control: {"type": "ephemeral"}`，dynamic portion 不帶 cache_control，與 design 的 system 一個 + user static 一個快取點一致；depends: 2.3/2.5；static: `specs/sdk-cache-runner/spec.md` + `design.md` Decision 4；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.5 `[delegate:codex]` 實作 `_extract_template()`：只依 `<!-- trly:template_end -->` 從 static portion 中分離模板內容，放入 `system` 參數並附加 cache_control；若 marker 缺失，保守退回不分離 system prompt；depends: 1.6/2.2；static: `specs/sdk-cache-runner/spec.md` template-boundary scenarios；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.6 `[delegate:codex]` 實作 `run()`：呼叫 `anthropic.Anthropic().messages.create()`，解析 response 並回傳 `AgentRunResult`（含 `usage.cache_creation_input_tokens` 與 `usage.cache_read_input_tokens`）；depends: 2.2-2.5；static: `specs/sdk-cache-runner/spec.md` usage scenarios；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.7 `[delegate:codex]` 實作 `check()`：驗證 `ANTHROPIC_API_KEY` 環境變數是否存在、SDK 是否可 import；depends: 2.1/2.2；static: `specs/sdk-cache-runner/spec.md` check scenario；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.8 `[delegate:codex]` 處理無 cache marker 的向後相容 path：整個 prompt 作為單一 user message，無 cache_control；depends: 2.3/2.4；static: `specs/sdk-cache-runner/spec.md` backward-compatibility scenarios；dynamic reads: `task_relay/agents/anthropic_sdk.py`
- [x] 2.9 `[delegate:codex]` 擴充 `AgentUsage` 型別，新增 `cache_creation_input_tokens: int | None = None` 與 `cache_read_input_tokens: int | None = None`，確保現有 ClaudeRunner/CodexRunner/DeepSeekRunner 的 usage 建構處不需修改即可通過型別檢查；depends: 2.6；static: `specs/sdk-cache-runner/spec.md` usage compatibility scenarios；dynamic reads: `task_relay/types.py`, `task_relay/core.py`, `task_relay/packer.py`

## 3. Runner Registration And CLI Integration

- [x] 3.1 `[delegate:codex]` 在 `agents/__init__.py` 中以 `"claude-sdk"` 名稱註冊 `AnthropicSDKRunner`，加入 `BUILTIN_AGENTS`；depends: 2.2；static: `specs/sdk-cache-runner/spec.md` registration scenario；dynamic reads: `task_relay/agents/__init__.py`, `task_relay/models.py`
- [x] 3.2 `[delegate:codex]` 確認 `trly apply --target claude-sdk` 能正確路由到 SDK runner；depends: 3.1；static: `specs/sdk-cache-runner/spec.md` route scenario；dynamic reads: `task_relay/cli/apply.py`, `task_relay/cli/__init__.py`, `tests/test_apply.py`
- [x] 3.3 `[delegate:codex]` 確認 `trly doctor` 能檢測 `claude-sdk` 的可用狀態；depends: 3.1；static: `specs/sdk-cache-runner/spec.md` check scenario；dynamic reads: `task_relay/doctor.py`, `task_relay/models.py`, `tests/test_doctor.py`
- [x] 3.4 `[delegate:test]` 確保既有 `--target claude`（CLI runner）路徑完全不受影響；depends: 1.2/3.1；static: `design.md` Decisions 1/5；dynamic reads: `tests/test_packer.py`, `task_relay/agents/claude.py`
- [x] 3.5 `[delegate:test]` 補 CLI runner + cache layout packet 回歸路徑，確認 `claude` CLI target 收到含 marker 且重排後的 prompt 仍能正常執行，不依賴 SDK cache 功能；depends: 1.2/1.6；static: `design.md` Decision 1；dynamic reads: `tests/test_packer.py`

## 4. Benchmark Extension

- [x] 4.1 `[delegate:codex]` 在 `packer_eval.py` 的 `run_eval_set()` 回傳結構中新增 `cache_metrics` 區塊；depends: 1.4/2.9；static: `specs/packet-cache-benchmarking/spec.md`；dynamic reads: `task_relay/packer_eval.py`
- [x] 4.2 `[delegate:codex]` 實作 `_compute_cache_metrics()`：從 `AgentRunResult.usage` 提取 `cache_creation_input_tokens` / `cache_read_input_tokens` 作為權威來源，計算 hit/miss 與節省量；沒有 API usage 時只可輸出明確標示為非權威的 byte-based 粗估；depends: 4.1；static: `specs/packet-cache-benchmarking/spec.md` savings scenarios + `design.md` Decision 6；dynamic reads: `task_relay/packer_eval.py`
- [x] 4.3 `[delegate:test]` 在 benchmark fixture 中新增 multi-task sequential delegation 測試案例（同 change 多 task）；depends: 4.1/4.2；static: `specs/packet-cache-benchmarking/spec.md` sequential scenarios；dynamic reads: `tests/test_packer.py`
- [x] 4.4 `[delegate:test]` 無 SDK runner usage 資料時，`cache_metrics` 回傳 `null`（向後相容）；depends: 4.1/4.2；static: `specs/packet-cache-benchmarking/spec.md` CLI-runner scenario；dynamic reads: `tests/test_packer.py`, `tests/test_packer_eval.py`

## 5. Tests

- [x] 5.1 `[delegate:test]` 補 `tests/test_packer.py`：驗證 `cache_layout=True` 時輸出包含正確的 marker 位置與內容排列；depends: 1.2/1.6；static: `specs/packet-cache-layout/spec.md`；dynamic reads: `tests/test_packer.py`
- [x] 5.2 `[delegate:test]` 補 `tests/test_packer.py`：驗證 `cache_layout=False` 時輸出不變（regression）；depends: 1.1；static: `specs/packet-cache-layout/spec.md` disabled scenario；dynamic reads: `tests/test_packer.py`
- [x] 5.3 `[delegate:test]` 補 `tests/test_packer.py`：驗證 marker escape 邏輯；depends: 1.3；static: `specs/packet-cache-layout/spec.md` marker-escape scenarios；dynamic reads: `tests/test_packer.py`
- [x] 5.4 `[delegate:test]` 補 `tests/test_anthropic_sdk_runner.py`：驗證 marker 解析（單一 marker、多 marker 驗證錯誤、無 marker）；depends: 2.3/2.8；static: `specs/sdk-cache-runner/spec.md` marker scenarios；dynamic reads: `tests/test_anthropic_sdk_runner.py`
- [x] 5.5 `[delegate:test]` 補 `tests/test_anthropic_sdk_runner.py`：驗證 `_build_messages()` 產出的 content blocks 結構與 cache_control 位置；depends: 2.4；static: `specs/sdk-cache-runner/spec.md` cache-control scenarios；dynamic reads: `tests/test_anthropic_sdk_runner.py`
- [x] 5.6 `[delegate:test]` 補 `tests/test_anthropic_sdk_runner.py`：驗證 system prompt 分離邏輯；depends: 2.5；static: `specs/sdk-cache-runner/spec.md` template-boundary scenarios；dynamic reads: `tests/test_anthropic_sdk_runner.py`
- [x] 5.7 `[delegate:test]` 補 `tests/test_packer_eval.py`：驗證 cache metrics 欄位在有/無 SDK usage 時的正確性；depends: 4.1/4.2/4.4；static: `specs/packet-cache-benchmarking/spec.md`；dynamic reads: `tests/test_packer_eval.py`
- [x] 5.8 `[delegate:test]` 補 `tests/test_anthropic_sdk_runner.py`：mock `anthropic.messages.create()` 回傳（含假 `usage.cache_creation_input_tokens` / `usage.cache_read_input_tokens`），驗證 request 結構、cache usage 擷取與無 API key 的預設 CI 可執行路徑；depends: 2.6/2.7；static: `specs/sdk-cache-runner/spec.md` usage scenarios；dynamic reads: `tests/test_anthropic_sdk_runner.py`
- [x] 5.9 `[delegate:test] [manual-only]` 補 integration test：模擬同 change 兩次連續 delegation，驗證第二次的 cache hit 行為；需真實 Anthropic API 的版本必須採 record/replay 或標記為 manual-only，不進預設 CI、不要求 `ANTHROPIC_API_KEY`；depends: 4.3/5.8；static: `specs/packet-cache-benchmarking/spec.md` sequential scenarios；dynamic reads: `tests/test_packer.py`
