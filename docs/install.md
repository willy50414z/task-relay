# trly install — 安裝與設定指南

`trly install` 用於在 agent 指引檔案中寫入 task-relay 委派設定區塊（managed block），並安裝對應的技能包（skill bundle）。支援互動式精靈（interactive wizard）與非互動式 CLI 旗標兩種使用方式。

## 快速開始

```bash
# 互動式精靈（在 TTY 環境中執行，不需任何旗標）
trly install

# 非互動式安裝（適用於 CI / 腳本 / 無 TTY 環境）
trly install --targets codex,claude --scope project --feature review,apply \
  --review-chain claude=claude-opus-4-8,deepseek=deepseek-v4-pro[1m] \
  --apply-chain deepseek=deepseek-v4-pro[1m]

# 清除委派設定（等同於 mode: main）
trly install --targets codex --scope project --feature none

# 移除委派設定
trly uninstall
trly uninstall --scope project
```

## 概念

task-relay 透過在 agent 指引檔案中寫入 managed block 來設定委派行為。每個 managed block 以 `<!-- task-relay:start -->` 開頭、`<!-- task-relay:end -->` 結尾，內容為 YAML 風格的 key-value 設定，並包含人類可讀的政策說明。

同時，task-relay 會在對應的技能目錄中安裝 `task-relay-delegation` 技能包，內含 agent 設定檔與輸出範本。

## 互動式精靈流程

在 TTY 環境中執行 `trly install`（不加旗標）會啟動箭頭鍵互動式精靈，逐步引導使用者完成設定：

### 步驟 1：選擇安裝目標（Installation Targets）

使用 **Space** 勾選要設定的 agent，支援多選：

| 選項 | 說明 |
|------|------|
| `claude` | Claude Code — 寫入 `CLAUDE.md` 及 `~/.claude/skills/` 或 `./.claude/skills/` |
| `codex` | OpenAI Codex — 寫入 `AGENTS.md` 及 `~/.codex/skills/` 或 `./.codex/skills/` |

### 步驟 2：選擇範圍（Scope）

使用 **Up/Down** 選擇後按 **Enter**：

| 選項 | 安裝路徑 |
|------|----------|
| `user` | `~/.claude/CLAUDE.md` 或 `~/.codex/AGENTS.md` — 全域預設，所有專案適用 |
| `project` | `./CLAUDE.md` 或 `./AGENTS.md` — 僅當前專案 |

### 步驟 3：選擇功能（Features）

使用 **Space** 勾選要啟用的功能，支援多選：

| 功能 | 說明 |
|------|------|
| `review` | Review — 審查 agent 驗證提案的清晰度、正確性與完整性 |
| `apply` | Apply — 實作 agent 執行變更（取代舊版 sub-agent 概念） |

若完全不選功能，則等同於 `mode: main`，會清除現有的 managed block。

### 步驟 4：設定 Review Chain（若有啟用 review）

1. 選擇 primary review agent（`claude` / `codex` / `deepseek`）
2. 從最新的模型型錄中選擇該 agent 使用的模型
3. 選擇是否加入 fallback agent（可重複加入直到 agent 用盡或使用者拒絕）

### 步驟 5：設定 Apply Chain（若有啟用 apply）

流程與 review chain 相同：
1. 選擇 primary apply agent
2. 選擇模型
3. 選擇是否加入 fallback agent

### 步驟 6：確認並寫入

精靈會顯示設定摘要，確認後寫入指引檔案與技能包。

## 非互動式 CLI 旗標

在無 TTY 環境（如 CI/CD、腳本）中使用時，必須提供足夠的旗標以跳過精靈：

### 必要旗標

| 旗標 | 說明 |
|------|------|
| `--targets TARGETS` | 逗號分隔的安裝目標，例如 `claude,codex` |
| `--scope {user,project}` | 安裝範圍 |
| `--feature FEATURES` | 啟用的功能，逗號分隔：`review,apply`；或 `none` 表示不啟用任何功能 |

### 功能旗標

| 旗標 | 說明 | 範例 |
|------|------|------|
| `--feature FEATURES` | 啟用的功能列表 | `--feature review,apply` |
| `--feature none` | 清除委派設定 | `--feature none` |
| `--review-chain CHAIN` | Review agent 鏈 | `--review-chain claude=claude-opus-4-8,deepseek` |
| `--apply-chain CHAIN` | Apply agent 鏈 | `--apply-chain deepseek=deepseek-v4-pro[1m]` |

### Chain 格式

```
agent=model, agent=model, agent
```

- 以逗號分隔各 agent
- 每個 agent 可選擇性指定 model（以 `=` 分隔）
- 若不指定 model，則使用該 agent 的預設模型
- 第一個 agent 為 primary，後續為 fallback（依序嘗試）

範例：
```
--review-chain claude=claude-opus-4-8,deepseek=deepseek-v4-pro[1m]
--apply-chain deepseek=deepseek-v4-pro[1m],codex=gpt-5.5-medium
```

### 舊版相容旗標（Legacy）

為向後相容，以下舊版旗標仍可使用，但會自動映射到新的 features/chains 格式：

| 舊版旗標 | 映射結果 |
|----------|----------|
| `--primary AGENT` | `--targets AGENT` |
| `--mode hybrid` | `--feature apply` |
| `--mode delegated-apply` | `--feature apply` |
| `--sub-agent AGENT` | `--apply-chain AGENT` |
| `--model sub=MODEL_ID` | apply chain primary model |
| `--mode main` | `--feature none` |

> **建議**：新腳本請使用 `--targets`、`--feature`、`--review-chain`、`--apply-chain` 新旗標。舊版旗標可能在未來版本中移除。

## 預填（Prefill）

當目標指引檔案中已存在 task-relay managed block 時，互動式精靈會自動偵測並預填選項：

- 若所有已安裝的 target 共享相同的 features、scope、chains，則預填這些值
- 若設定之間有衝突（例如不同 target 使用不同的 features），則不預填 features/chains，但仍預填 targets
- 支援從舊版格式（`mode`/`sub-agent`/`models`）自動遷移到新格式

## Managed Block 格式

安裝後在指引檔案中寫入的區塊格式如下：

```markdown
<!-- task-relay:start -->
## Task Relay Delegation

- primary: codex
- scope: project
- features: review, apply
- review-chain: claude=claude-opus-4-8, deepseek=deepseek-v4-pro[1m]
- apply-chain: deepseek=deepseek-v4-pro[1m]

Delegation: codex orchestrates — review via claude=claude-opus-4-8, deepseek=deepseek-v4-pro[1m]; apply via deepseek=deepseek-v4-pro[1m].

Primary model (codex) owns:
- Architecture, security, data migration, destructive operations, credentials.
- OpenSpec artifact interpretation, scope, and state changes.
- Integration of delegated output and final verification.

## Review Workflow (propose phase)
...

## Apply Workflow (implementation phase)
...

## Task Tags
...

<!-- task-relay:end -->
```

### 欄位說明

| 欄位 | 說明 |
|------|------|
| `primary` | 主要 orchestrator agent 名稱 |
| `scope` | 安裝範圍：`user` 或 `project` |
| `features` | 啟用的功能列表，或 `none` 表示無委派 |
| `review-chain` | Review agent 鏈，格式 `agent=model, agent` |
| `apply-chain` | Apply agent 鏈，格式 `agent=model, agent` |

## 技能包結構

安裝時會在對應的技能目錄下建立 `task-relay-delegation/` 技能包：

```
{skill_root}/task-relay-delegation/
├── SKILL.md              # 技能描述與委派鏈設定
├── agents/
│   ├── claude.yaml        # Claude agent 設定
│   ├── openai.yaml        # OpenAI / Codex agent 設定
│   └── deepseek.yaml      # DeepSeek agent 設定
└── templates/
    ├── implementation-draft.md  # 實作草案範本
    ├── test-draft.md            # 測試草案範本
    ├── review.md                # 審查發現範本
    ├── diagnosis.md             # 診斷報告範本
    └── review-proposal.md       # 審查提案範本
```

**注意**：`codex` 的 agent 設定檔命名為 `openai.yaml`（因為 Codex CLI 使用 OpenAI 協定），其餘 agent 使用實際名稱。

### 輸出模式

技能包定義了以下輸出模式，委派 agent 應根據收到的 prompt packet 類型產生對應輸出：

| 範本 | 用途 |
|------|------|
| `review-proposal` | 審查提案的清晰度、正確性與完整性 |
| `implementation-draft` | 逐檔編輯計畫或 patch |
| `test-draft` | 要新增的測試及執行指令 |
| `review` | 針對 diff 或 spec 的審查發現（含嚴重性） |
| `diagnosis` | 失敗命令的根因分析與修復建議 |

## 安裝路徑對照表

| Primary | Scope   | Guidance File         | Skill Root              |
|---------|---------|-----------------------|-------------------------|
| claude  | user    | `~/.claude/CLAUDE.md`  | `~/.claude/skills/`     |
| claude  | project | `./CLAUDE.md`          | `./.claude/skills/`     |
| codex   | user    | `~/.codex/AGENTS.md`   | `~/.codex/skills/`      |
| codex   | project | `./AGENTS.md`           | `./.codex/skills/`      |

## 解除安裝

```bash
# 移除所有偵測到的 managed block
trly uninstall

# 僅移除 user scope
trly uninstall --scope user

# 僅移除 project scope
trly uninstall --scope project
```

`trly uninstall` 會：
1. 掃描 user 與 project scope 的指引檔案
2. 移除 `<!-- task-relay:start -->` ... `<!-- task-relay:end -->` 區塊
3. 刪除對應的 `task-relay-delegation` 技能目錄
4. 同時清理舊版 `openspec-deepseek-delegation` 技能目錄（若存在）

## 模型型錄

互動式精靈中的模型選擇來自內建型錄。各 agent 的可用模型：

### Claude

| Model ID | 名稱 | 層級 |
|----------|------|------|
| `claude-opus-4-8` | Opus 4.8 | high |
| `claude-sonnet-4-6` | Sonnet 4.6 | medium |
| `claude-haiku-4-5-20251001` | Haiku 4.5 | fast |
| `claude-fable-5` | Fable 5 | high |

### Codex (OpenAI)

| Model ID | 名稱 | 層級 |
|----------|------|------|
| `gpt-5.5-high` | GPT-5.5 High | high |
| `gpt-5.5-medium` | GPT-5.5 Medium | medium |
| `gpt-5.4` | GPT-5.4 | fast |

### DeepSeek

| Model ID | 名稱 | 層級 |
|----------|------|------|
| `deepseek-v4-pro[1m]` | DeepSeek V4 Pro | high |
| `deepseek-v4-flash` | DeepSeek V4 Flash | fast |

各 agent 的預設模型：Claude 使用 `claude-sonnet-4-6`、Codex 使用 `gpt-5.5-medium`、DeepSeek 使用 `deepseek-v4-pro[1m]`。

## 相依套件

互動式精靈需要 `questionary` 套件。若使用非互動式旗標則不需要。

```bash
# 安裝時一併安裝 questionary
pip install task-relay[interactive]

# 或單獨安裝
pip install questionary
```

若在 TTY 環境中缺少 `questionary`，精靈會顯示錯誤訊息並提示安裝方式。

## 使用情境

### 情境 1：本機開發專案，啟用 review + apply

```bash
trly install
# 互動式選擇：
#   targets: codex
#   scope: project
#   features: review, apply
#   review chain: claude (claude-opus-4-8), fallback: deepseek
#   apply chain: deepseek (deepseek-v4-pro[1m])
```

### 情境 2：CI 腳本，僅啟用 apply

```bash
trly install \
  --targets codex \
  --scope project \
  --feature apply \
  --apply-chain deepseek=deepseek-v4-pro[1m],codex=gpt-5.5-medium
```

### 情境 3：清除委派，只用 primary agent

```bash
trly install --targets claude --scope user --feature none
```

### 情境 4：全域設定，所有專案套用

```bash
trly install
# 互動式選擇：
#   targets: claude, codex
#   scope: user
#   features: apply
#   apply chain: deepseek
```

## 內部實作參考

| 模組 | 檔案 | 職責 |
|------|------|------|
| CLI 入口 | `task_relay/cli/__init__.py` | `handle_install()` — 旗標解析、精靈啟動、非互動式分支 |
| 互動式精靈 | `task_relay/wizard.py` | `run_wizard()` — 六步驟互動流程、`WizardState` 狀態管理 |
| 委派邏輯 | `task_relay/delegation.py` | `install()` / `clear()` / `uninstall()` — managed block 讀寫、技能包管理 |
| 模型型錄 | `task_relay/models.py` | 內建模型清單與預設值 |
