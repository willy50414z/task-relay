## 1. WizardState 與資料模型擴充

- [x] 1.1 擴充 `WizardState` dataclass: 新增 `features: list[str]`、`review_chain: list[tuple[str, str | None]]`、`apply_chain: list[tuple[str, str | None]]` 欄位，保留 `target_agents`、`scope`、`cwd`，移除 `mode`、`sub_agent`、`models`
- [x] 1.2 更新 `WizardState` 所有現有建構點 (run_wizard prefill、_resolve_prefill_state、prompt_* 函數) 使用新欄位
- [x] 1.3 移除 `VALID_MODES`、`VALID_SUB_AGENTS` 常式中與 mode 相關的引用，保留 agent 選擇列表

## 2. Managed Block 格式升級

- [x] 2.1 重構 `build_guidance_block()`: 接受 features 與 chains 參數，產生 `features`、`review-chain`、`apply-chain` 欄位，chain 值格式為 `agent=model, agent=model`
- [x] 2.2 擴充 `parse_existing_block()`: 解析 `features`、`review-chain`、`apply-chain` 新欄位，chain 值解析為 `list[tuple[str, str | None]]`
- [x] 2.3 實作 legacy format 解析相容: `mode: main` → features 為空，`mode: hybrid` / `delegated-apply` + `sub-agent` + `models` → features 為 `["apply"]`，apply-chain 從 sub-agent 及 models 提取
- [x] 2.4 更新 `_build_skill_md()`: skill 描述加入 review workflow 說明、review-proposal template 用途、agent chain 概念
- [x] 2.5 更新 `_mode_header()` / `_mode_policy()`: 適應新的 features/chains 結構，描述 review agent 審核流程與 apply agent 實作流程

## 3. Wizard 步驟重構

- [x] 3.1 實作 `prompt_features(state, prompt) -> WizardState`: checkbox 步驟讓使用者選擇 review / apply / both / neither
- [x] 3.2 實作 `prompt_chain_primary(state, prompt, chain_name) -> WizardState`: select 步驟選擇主 agent
- [x] 3.3 實作 `prompt_chain_model(state, prompt, chain_name, agent) -> WizardState`: select 步驟選擇該 agent 的 model (從 catalog)
- [x] 3.4 實作 fallback loop 函數 `prompt_chain_fallback_loop(state, prompt, chain_name) -> WizardState`: confirm loop — 顯示目前 chain 狀態 → 詢問是否加 fallback → select agent (排除已選) → select model → repeat 直到使用者拒絕或 agent 耗盡
- [x] 3.5 重構 `run_wizard()`: 整合新步驟，條件分支 — 若 features 為空則 clear 並返回，若有 review 則走 review chain 設定，若有 apply 則走 apply chain 設定
- [x] 3.6 更新 `confirm_and_write()`: 摘要顯示新的 features 與 chains 格式 (agent (model) → agent (model))

## 4. CLI 旗標擴充

- [x] 4.1 新增 `--feature` flag: 接受 `review,apply` 或 `none`，用於非互動式安裝
- [x] 4.2 新增 `--review-chain` flag: 接受 `agent=model, agent=model` 格式字串
- [x] 4.3 新增 `--apply-chain` flag: 同上格式
- [x] 4.4 實作 `_parse_chain(value: str) -> list[tuple[str, str | None]]` 解析函數
- [x] 4.5 更新 `handle_install()`: 支援新旗標的非互動式路徑，移除對 `--mode` 和 `--sub-agent` 的依賴 (保留解析但映射到新格式)
- [x] 4.6 更新 `_non_interactive_install_error()`: 錯誤訊息反映新旗標需求

## 5. Prefill 與向後相容

- [x] 5.1 實作 legacy-to-new 映射邏輯: `parse_existing_block` 回傳的 legacy 欄位自動轉換為 features/chains 格式
- [x] 5.2 更新 `_resolve_prefill_state()`: 從 legacy 或 new format block 預填 WizardState，支援多候選情況
- [x] 5.3 更新 `prefill_from_existing()`: 處理新欄位的預填
- [x] 5.4 確保 install 寫入時一律使用新格式 (不保留 legacy format)

## 6. Review Prompt 範本

- [x] 6.1 建立 `task_relay/assets/task-relay-delegation/templates/review-proposal.md`: 定義審核維度 (需求明確性、方向正確性、計畫完整性、使用者意圖)、輸出規格 (`spec/delegent_review.md`)、互動邊界、可用工具 (gstack)、timeout 指引
- [x] 6.2 更新 `_copy_templates()`: 將 review-proposal.md 加入 template 複製清單
- [x] 6.3 更新 `task_relay/assets/__init__.py`: 確保新 template 可被 package resources 找到

## 7. Skill Bundle 更新

- [x] 7.1 更新 `_build_skill_md()`: skill 描述納入 three-agent 架構 (primary/review/apply) 與 propose review workflow
- [x] 7.2 更新 `_write_agent_config()`: 根據 review chain 與 apply chain 的 primary agent 寫入對應的 agent config
- [x] 7.3 確保 `install_skill_bundle()` 正確處理多個 agent config (review primary + apply primary 可能不同)

## 8. 測試

- [x] 8.1 擴充 `test_wizard.py`: 測試 `prompt_features`、`prompt_chain_primary`、`prompt_chain_model`、`prompt_chain_fallback_loop`、完整 run_wizard 流程 (含各種 feature 組合)
- [x] 8.2 擴充 `test_delegation.py`: 測試新的 `build_guidance_block` (features + chains)、`parse_existing_block` (new format)、legacy format 解析與映射、chain 格式解析
- [x] 8.3 擴充 `test_cli_install.py`: 測試 `--feature`、`--review-chain`、`--apply-chain` 非互動式安裝、`--feature none` 清除行為、legacy flag 向後相容
- [x] 8.4 測試 template 安裝: 確認 review-proposal.md 被正確複製到 skill bundle
- [x] 8.5 測試 backward compat: legacy managed block 被正確 prefilled 並升級寫入新格式
