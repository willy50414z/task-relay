## 1. Reliability Baseline

- [x] 1.1 修正 `task_relay/agents/deepseek.py` 的 `check()`，讓缺少 token、CLI 不可用或基本探測失敗時回報真實失敗狀態
- [x] 1.2 清理 `task_relay/workflow/run_review.py` 的重複 `run_review()` 定義，保留單一路徑並補上對應測試
- [x] 1.3 更新 `task_relay/wizard.py` 的非互動錯誤訊息，改成目前支援的 install flags
- [x] 1.4 補 reliability regression tests，覆蓋 DeepSeek health、review wrapper、install guidance 三條路徑

## 2. Doctor / Preflight

- [x] 2.1 設計 doctor 檢查結果資料結構與 plain/json 輸出格式
- [x] 2.2 新增 `task_relay/cli/doctor.py` 與 CLI parser wiring，支援 `trly doctor`
- [x] 2.3 實作 agent / model checks，驗證已設定 target、token、CLI 與 model catalog 對應
- [x] 2.4 實作 repo / worktree / path checks，驗證 git repo、worktree 可用性、guidance 與 skill 目錄可寫狀態
- [x] 2.5 實作 managed block 與 scope conflict checks，偵測缺 reviewer、缺 apply chain、scope 衝突等問題
- [x] 2.6 補 doctor 測試，覆蓋 blocking failure、partial failure 與 success JSON 輸出

## 3. Apply Orchestration

- [x] 3.1 設計高階 apply 命令的參數與輸出契約，明確對應 `implementation-draft` / `test-draft`
- [x] 3.2 實作 apply workflow，整合 packet generation、`run_isolated`、empty-branch fail loud 與 branch summary
- [x] 3.3 加入可選 verification hook，讓 apply 可在 delegation 後執行指定驗證命令並回報結果
- [x] 3.4 補 apply workflow 測試，覆蓋 implementation path、test-draft path、empty output 與 verification failure

## 4. Benchmarking

- [x] 4.1 定義 packed vs full context benchmark case format，支援多 change、多 task 類型樣本
- [x] 4.2 擴充 `task_relay/packer_eval.py` 或新增 workflow benchmark runner，記錄 context size、duration 與可用 token 指標
- [x] 4.3 設計 downstream quality signals，至少記錄 review/apply/verification 的 outcome proxies
- [x] 4.4 產出 machine-readable benchmark report artifact，保留每個 sample 的 mode 與 metrics
- [x] 4.5 補 benchmark fixtures 與測試，驗證報告結構與對照模式輸出

## 5. Install Success Guidance

- [x] 5.1 更新 install 完成摘要，列出 configured targets/features 與建議下一步命令
- [x] 5.2 設計 install 後的 cheap validation / smoke checks，避免把設定問題延後到第一次正式 run
- [x] 5.3 讓 install 在 post-write validation 成功或失敗時輸出對應 guidance
- [x] 5.4 更新 `README.md`、`docs/install.md` 與相關 skill/generated guidance，反映 `doctor`、高階 `apply` 與新的 install 成功路徑
