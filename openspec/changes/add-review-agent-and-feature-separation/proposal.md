## Why

目前的 `trly install` 只有 primary + sub-agent 的二元模型，無法支援 propose 階段的 review agent 審核流程。需要將 delegation 架構升級為三角色（review agent、apply agent、fallback chains），並讓使用者可以在安裝時獨立選擇要啟用 review 功能、apply 功能、或兩者皆啟用。

## What Changes

- **新增 review agent 角色**：在 propose 階段由 primary agent 呼叫 review agent 審核 proposal 的完整性與方向正確性，產出 `spec/delegent_review.md`。
- **新增 apply agent 角色**：取代現有的 sub-agent，專門負責實作變更。
- **獨立功能勾選**：`trly install` wizard 新增 checkbox 步驟讓使用者獨立選擇啟用 review / apply 功能。都不勾選等同 mode=main。
- **Fallback chains**：每個功能 (review/apply) 支援 ordered fallback agent chain，每個 agent 可獨立指定 model。
- **新增 review-proposal 範本**：提供 primary agent 用來產生 review agent prompt 的標準範本，定義審核維度與輸出格式。
- **Managed block 格式升級**：從 `primary/mode/sub-agent/models` 擴展為 `primary/features/review-chain/apply-chain`，支援 chain 格式 `agent=model, agent=model`。
- **Wizard 流程重構**：新增 feature checkbox、review chain loop、apply chain loop 步驟。
- **CLI 旗標擴充**：新增 `--feature`、`--review-chain`、`--apply-chain` 非互動式安裝旗標。
- **向後相容**：parse_existing_block 仍能解析舊格式 managed block，舊格式 `mode: hybrid` + `sub-agent: X` 對應為只啟用 apply、`mode: main` 對應為 features 為空。

## Capabilities

### New Capabilities

- `review-agent-propose-workflow`: Review agent 在 propose 階段的審核流程，包含 prompt 範本、輸出規格 (`spec/delegent_review.md`)、與 primary agent 的互動模式。
- `feature-separated-install-wizard`: 功能分離的安裝精靈，支援 checkbox 獨立選擇 review/apply 功能、每個功能的 agent chain 設定（含 fallback loop）、model 選擇。
- `agent-fallback-chains`: Ordered agent fallback chain 機制，每個 agent 可獨立指定 model，chain 格式為 `agent=model, agent=model`。

### Modified Capabilities

- `delegation-install-paths`: Managed block 格式從 primary/mode/sub-agent 擴展為 primary/features/review-chain/apply-chain，需支援新舊格式雙向解析。
- `keyboard-install-wizard`: Wizard 步驟從 5 步擴展為最多 ~12 步（含條件分支），新增 feature checkbox 步驟與 fallback loop 步驟。

## Impact

- Affected code: `task_relay/wizard.py` (WizardState 擴充 + 6+ 新步驟函數)、`task_relay/delegation.py` (build_guidance_block / parse_existing_block / install / _build_skill_md)、`task_relay/cli/__init__.py` (新 CLI 旗標與解析)、`task_relay/assets/task-relay-delegation/templates/` (新增 review-proposal.md 範本)。
- Tests: `test_wizard.py`、`test_cli_install.py`、`test_delegation.py` 皆需擴充。
- 無外部依賴變更。
