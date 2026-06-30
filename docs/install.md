# trly install — 安裝與設定指南

`trly install` 用於在 agent 指引檔案中寫入 task-relay 委派設定區塊（managed block），並安裝對應的技能包（skill bundle）。支援互動式精靈（interactive wizard）與非互動式 CLI 旗標兩種使用方式。

若你想先理解 review / apply 功能本身，再回來看安裝流程，請先閱讀 [review-apply.md](./review-apply.md)。

## 快速開始

```bash
# 互動式精靈（在 TTY 環境中執行，不需任何旗標）
trly install

# 非互動式安裝（適用於 CI / 腳本 / 無 TTY 環境）
trly install --targets codex,claude --scope project --feature review,apply \
  --review-chain claude=claude-opus-4-8,deepseek=deepseek-v4-pro[1m] \
  --apply-chain deepseek=deepseek-v4-pro[1m]

# 安裝後先做 cheap validation / preflight
trly doctor

# 以高階 apply 命令執行單一 OpenSpec task
trly apply --change <change> --task <task-id>

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
| `review` | Review — 在 propose phase 委派審查 agent 檢查需求清晰度、方向正確性與實作計畫完整性，產出 `openspec/changes/<change>/review/delegation_review.md` |
| `apply` | Apply — 在 implementation phase 委派實作 / 測試 agent 產出 patch 或實作報告；primary agent 仍負責整合、驗證與 OpenSpec 狀態變更 |

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

寫入完成後，CLI 會額外輸出：

- 已設定的 targets / features 摘要
- 建議下一步命令（例如 `trly doctor`、`trly review-gate --change <change>`、`trly apply --change <change> --task <task-id>`）
- cheap validation 結果摘要，提早暴露 token、CLI、model、scope 或 writable path 問題

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

When a proposal is ready for review, the primary agent packages the proposal context with the `review-proposal` template, delegates to the review chain, requires output at `openspec/changes/<change>/review/delegation_review.md`, reads that artifact, and updates proposal artifacts as needed.

Review agents evaluate requirement clarity, direction correctness, and implementation plan completeness. They must ask the user when ambiguity requires a product / architecture decision. They must not modify OpenSpec state, mark tasks, perform destructive operations, or make architecture decisions.

## Apply Workflow (implementation phase)

When implementation is ready, the primary agent packages the apply request with `implementation-draft` or `test-draft`, delegates bounded tasks to the apply chain, reviews the resulting branch diff or report, runs verification, and only then marks tasks complete.

Apply agents may draft or implement focused changes, but they must not modify OpenSpec state, mark `tasks.md` checkboxes, or make architecture / security / migration decisions.

## Task Tags

- `[delegate:review]` — route proposal review to review chain.
- `[delegate:<apply-agent>]` — route implementation to apply chain.
- `[delegate:test]` — route test authoring.
- `[<primary-agent>-only]` — keep in primary agent.

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

## Review / Apply 工作流細節

`trly install` 只負責把委派政策寫進 agent guidance；實際委派仍由 primary agent 明確打包 context、呼叫 delegate、驗證輸出並整合結果。Primary agent 永遠保留以下責任：

- 架構、安全、資料遷移、破壞性操作與 credentials 決策。
- OpenSpec artifact interpretation、scope 判斷與狀態變更。
- 讀取 delegate 產物、整合變更、執行最終驗證。

### Review 功能

Review 用於 propose phase，不是實作流程。典型流程：

1. Primary agent 使用 `review-proposal` template 打包提案 context。
2. 呼叫 review chain 的 primary agent；若失敗可依 chain 順序 fallback。
3. Review agent 檢查 requirement clarity、direction correctness、implementation plan completeness。
4. Review agent 將 findings 寫到 `openspec/changes/<change>/review/delegation_review.md`。
5. 執行時應使用 `--expect-output openspec/changes/<change>/review/delegation_review.md`，讓缺檔或空檔直接失敗。
6. Primary agent 必須實際讀取 `openspec/changes/<change>/review/delegation_review.md`；非空檔只代表 gate 通過，不代表內容正確。
7. 若 review 需要產品、架構或 scope 決策，review agent 應提出問題，由使用者或 primary agent 決定，而不是自行定義解法。

建議命令形狀：

```bash
trly pack --mode review-proposal --change <change> --out /tmp/<change>-review.md
trly run --target <review-agent> --prompt-file /tmp/<change>-review.md \
  --expect-output openspec/changes/<change>/review/delegation_review.md
```

Review agent 的 non-goals：不得修改 OpenSpec state、不得勾選 tasks、不得執行破壞性操作、不得替 primary 做架構 / 安全 / migration 決策。

### Apply 功能

Apply 用於 implementation phase。Delegate 可以產出 patch、修改建議、實作報告或測試草案，但完成定義仍由 primary agent 控制。典型流程：

1. Primary agent 使用 `implementation-draft` 或 `test-draft` template 打包單一 task 的 bounded context。
2. 對於多 task 變更，先建立 `chg/<change-name>` 這類整合分支 / worktree 作為累積基準；單一小任務可直接從目前 base 委派。
3. 每個實作或測試 task 用 `trly run --isolate --base <ref>` 執行，delegate 在臨時 worktree 的 `tr/<id>` 分支上工作，`git push` 會被停用。
4. Primary agent 檢查 delegate branch diff 或報告，決定是否接受、修改或丟棄。
5. 接受後才合併回整合分支 / 主工作樹，並執行測試。
6. Primary agent 驗證通過後才更新 OpenSpec `tasks.md` checkbox。空分支會失敗，不視為成功。

若只是執行單一 bounded task，建議直接使用高階命令：

```bash
trly apply --change <change> --task <task-id>
```

`trly apply` 會整合 packet generation、configured apply chain、`run_isolated`、empty-branch fail-loud、branch summary，以及可選的 `--verify-cmd` 驗證 hook。

建議命令形狀：

```bash
trly pack --mode implementation-draft --change <change> --task <task-id> \
  --out /tmp/<change>-<task-id>-apply.md
trly run --target <apply-agent> --prompt-file /tmp/<change>-<task-id>-apply.md \
  --isolate --base <base-ref>
```

測試委派可改用 `test-draft`，並在需要時加入動態 diff context：

```bash
trly pack --mode test-draft --change <change> --task <task-id> \
  --diff-from <base-ref> --out /tmp/<change>-<task-id>-test.md
```

Apply agent 的 non-goals：不得修改 OpenSpec scope、不得勾選 tasks、不得執行破壞性操作、不得做 architecture / security / credential / migration 決策。

## 安裝後驗證與診斷

`trly doctor` 會做一組 cheap preflight checks，協助在第一次正式委派前先找出設定問題。檢查範圍包含：

- agent CLI 與 token 是否可用
- configured model 是否存在於 catalog
- git repo / managed block / writable path 是否正常
- review/apply feature 是否缺少必要 chain 設定
- user / project scope 是否衝突

範例：

```bash
trly doctor
trly doctor --json
trly doctor --targets codex,claude --scope project
```

若要量測 packed context 相對 full context 的大小與時間差，可使用：

```bash
trly pack-benchmark --eval-set tests/fixtures/pack_benchmark.json --json
```

目前 context-packer 的實際 contract 已包含：

- semantic model fallback，可補上 spec / design section / task dependency / extra reads
- byte-based hard budget 與 deterministic trimming
- `pack-lint` 對 fallback、budget 與 JSON-only sidecar 的早期診斷
- benchmark 報告中的 `selection_accuracy`、`context_cost`、`quality_outcome`

## 技能包結構

安裝時會在對應的技能目錄下建立 `task-relay-delegation/` 技能包。`SKILL.md` 會寫入 review/apply chain、primary agent 的 `trly pack` / `trly run` 執行方式，以及 delegate 的輸出模式與 non-goals：

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
| `review-proposal` | Propose phase 審查 packet；輸出 findings 到 `openspec/changes/<change>/review/delegation_review.md`，供 primary agent 讀取後修正 proposal/design/tasks |
| `implementation-draft` | Implementation phase 實作 packet；輸出 patch、分支變更或逐檔編輯計畫，供 primary agent review / integrate |
| `test-draft` | 測試委派 packet；輸出要新增的測試、驗證指令或 focused validation plan |
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

## 委派執行的強化行為（runtime）

安裝的 managed block 會引導 primary agent 使用以下強化過的委派流程：

- **Review 產出驗證**：review 委派以 `trly run ... --expect-output openspec/changes/<change>/review/delegation_review.md`
  執行，若審查檔未產生或為空會大聲失敗，而非僅憑 delegate 的 stdout 宣稱成功。primary 仍必須實際閱讀審查內容；非空只代表通過 gate，不代表內容正確。
  （審查檔已由舊名 `delegent_review.md` 更名為 `delegation_review.md`。）
- **Apply 隔離**：apply 委派以 `trly run ... --isolate` 執行，delegate 在臨時 git worktree
  的丟棄分支 `tr/<id>` 中工作、`git push` 被停用，變更不會碰到真實工作樹；primary 檢視並合併
  該分支後才標記任務完成。空分支會大聲失敗。
- **Quota 韌性**：額度/限流錯誤改為有上限、會記 log 的重試（預設硬性耗盡 30 分鐘上限），
  不再靜默卡住約 24 小時。可透過 `LLM_QUOTA_*` 環境變數調整；`LLM_FAST_FALLBACK=1` 可在
  硬性耗盡時改為立即切換 chain 中的下一個 agent（預設關閉，維持「等待較便宜 agent」的成本優勢）。

威脅模型為「delegate 不可靠但非惡意」：worktree + 停用 push 保護真實工作樹與遠端；完整的
讀取/網路關押（OS 沙箱）為後續工作，不在此版本範圍。

## 升級既有安裝

managed block 的工作流文字會隨套件更新而改變（worktree/隔離流程、產出驗證、檔名更名）。
**既有安裝不會自動遷移**——升級套件後請重新執行 `trly install`（沿用原本的 targets/scope/features）
以將最新的工作流文字寫入指引檔案。

## 內部實作參考

| 模組 | 檔案 | 職責 |
|------|------|------|
| CLI 入口 | `task_relay/cli/__init__.py` | `handle_install()` — 旗標解析、精靈啟動、非互動式分支 |
| 互動式精靈 | `task_relay/wizard.py` | `run_wizard()` — 六步驟互動流程、`WizardState` 狀態管理 |
| 委派邏輯 | `task_relay/delegation.py` | `install()` / `clear()` / `uninstall()` — managed block 讀寫、技能包管理 |
| 模型型錄 | `task_relay/models.py` | 內建模型清單與預設值 |
