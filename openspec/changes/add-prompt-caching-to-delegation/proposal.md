## Why

當同一個 OpenSpec change 內有多個 task 需要依序委派時，每次委派重複傳送了完全相同的 spec、design section 與模板指令，造成大量 token 浪費。Anthropic Prompt Caching 可讓這些靜態內容只在下游 agent 首次請求時以全價寫入 cache，後續委派以 ~10% 成本讀取。目前 delegation pipeline 缺少兩件事：封包內容沒有按「可快取/不可快取」排列，也沒有走 SDK 路徑以精準控制 `cache_control` breakpoint。

## What Changes

- 重構 packet 輸出結構，將同 change 不變的內容（spec、design section、模板指令）集中在前段、每次 task 不同的內容（task block、scope note、extra reads）放在末段，並標記 cache breakpoint 位置
- 新增基於 Anthropic API SDK 的 agent runner，支援 `cache_control: {"type": "ephemeral"}` 標記，作為 `claude --print` CLI 之外的第二條 delegation 路徑
- 擴充 benchmark 報告，加入 cache hit rate、cache write/read token 與實際節省的 token 成本欄位
- Task Relay 提供 cache layout 與 SDK runner 機制；是否啟用 cache layout 由 caller / primary agent 在建立委派封包時決定，不由 `trly pack` 或 `trly apply` 自動偵測連續委派

## Capabilities

### New Capabilities
- `packet-cache-layout`: 定義 packet 如何將靜態內容（同 change 共用）與動態內容（同 task 特有）分離，並在兩者之間插入 cache breakpoint，使 Anthropic Prompt Caching 可以將前段快取、後段每次重新傳送。
- `sdk-cache-runner`: 定義一個新的 agent runner，直接透過 Anthropic API SDK 發送請求，支援 `cache_control` breakpoint 標記、cache 命中與寫入的 usage 回報，以及 cache TTL 過期時的降級行為。
- `packet-cache-benchmarking`: 在既有的 packed-vs-full benchmark 報告中新增 cache 相關觀測欄位（cache hit rate、cache write tokens、cache read tokens、total token savings），並提供同 change 多 task 連續委派的模擬測試。

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `task_relay/packer.py` — `build_packet()` 輸出結構需支援 cache layout
  - `task_relay/agents/claude.py` — 既有 CLI runner 保持不變
  - `task_relay/agents/anthropic_sdk.py` — **新增** SDK-based runner
  - `task_relay/agents/__init__.py` — 註冊新 runner
  - `task_relay/core.py` — `_run_with_fallback` 可能需要感知 caching 語義（cache session 生命週期）
  - `task_relay/packer_eval.py` — benchmark 報告新增 cache 欄位
  - `task_relay/cli/pack.py` — 串接既有 pack flow 對 `cache_layout` 參數的傳遞
- 不影響既有 `claude --print` CLI 路徑；SDK runner 為 opt-in 功能
- 需要使用者設定 `ANTHROPIC_API_KEY` 環境變數（SDK runner 必要）
