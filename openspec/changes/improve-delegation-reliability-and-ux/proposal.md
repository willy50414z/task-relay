## Why

`task-relay` 的 `review`/`apply` 路線已經有不錯的核心 primitives，但目前還有三個會直接限制 adoption 的缺口：preflight 不夠可靠、`apply` 沒有對稱的高階工作流、以及缺少能公開證明 token/quality tradeoff 的 benchmark。除此之外，還有幾個明確 defect 會削弱使用者信任，例如 DeepSeek health check 假陽性、`run_review.py` 的重複定義、以及 install 非互動錯誤訊息仍指向舊旗標。

現在補這一輪很有必要，因為這些問題都卡在「第一次成功率」與「是否敢在真實專案用」兩個關鍵門檻。若不先補可靠度與可驗證性，後續再加更多 agent 功能，只會放大使用者的不確定感。

## What Changes

- 新增 `trly doctor` preflight 命令，檢查 agent 可用性、model 設定、repo/worktree 條件、managed block 結構與 scope 衝突，並提供可執行的修復指引。
- 新增高階 `apply` orchestration 命令，包裝 packet generation、isolated run、empty-branch fail loud、diff summary 與基本驗證，讓使用者不必手動拼 `pack + run --isolate`。
- 新增 benchmark / evaluation 流程，比較 full-change context 與 packed context，量測 token、時間與 downstream quality 指標，讓「省 token 但不降品質」變成可驗證主張。
- 修正 delegation reliability 缺陷：
  - DeepSeek health check 不再永遠回 `ok=true`
  - 移除 `run_review.py` 的重複 `run_review()` 定義，保留單一正確路徑
  - 更新 install 非互動錯誤訊息與引導，改成目前支援的 flags
- 改善安裝完成後的 UX，包含 smoke test、next-step guidance，並讓 install/setup 更容易暴露設定問題而不是延後到第一次正式執行才炸。

## Capabilities

### New Capabilities

- `delegation-preflight`: 提供 `trly doctor` 與安裝後 smoke checks，驗證 agent、model、repo、managed block 與 scope 狀態。
- `apply-orchestration`: 提供高階 apply 命令，統一包裝 packet generation、isolated delegation、結果摘要與接受前驗證。
- `delegation-benchmarking`: 提供 packed vs full context 的 benchmark/eval 流程與可重跑報告輸出。
- `install-success-guidance`: 安裝完成後提供 smoke test、設定摘要、衝突警告與下一步操作指引。

### Modified Capabilities

- None.

## Impact

- Affected code:
  - `task_relay/cli/__init__.py`
  - `task_relay/cli/health.py`
  - 新增 `task_relay/cli/doctor.py`
  - 新增 apply orchestration 的 CLI / workflow 模組
  - `task_relay/agents/deepseek.py`
  - `task_relay/workflow/run_review.py`
  - `task_relay/wizard.py`
  - `task_relay/delegation.py`
  - `task_relay/packer_eval.py` 與 benchmark fixtures / reporting
- Tests:
  - doctor / preflight 測試
  - apply orchestration 測試
  - health check / install UX regression tests
  - benchmark reporting tests
- User-facing behavior:
  - 安裝後能更早看到設定問題
  - apply 路徑從低階 primitives 升級成可直接操作的高階命令
  - 對外可以用 benchmark 報告支撐 token 與 quality 主張
