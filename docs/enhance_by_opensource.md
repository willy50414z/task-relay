# task-relay 開源借鏡改進方案

本文基於對 11 個功能相似開源專案的深入分析，歸納 task-relay 的獨特優勢、關鍵弱點，以及從各專案借鏡的具體改進方案。

## 研究範圍

| # | 專案 | 類型 | 最相關的點 |
|---|------|------|-----------|
| 1 | [Quest](https://github.com/KjellKod/quest) | Planner → Reviewers → Arbiter → Builder | 雙模型並行審查 + Arbiter 噪音過濾 |
| 2 | [agent-orchestrator-kit](https://www.npmjs.com/package/agent-orchestrator-kit) | 5-role OpenSpec pipeline | 完整 explore→propose→review→apply→verify→archive |
| 3 | [delegate-skills](https://github.com/amElnagdy/delegate-skills) | brief→dispatch→review→commit | Orchestrator 保留 commit 權 |
| 4 | [Cascade AI](https://www.npmjs.com/package/cascade-ai) | T1/T2/T3 分層路由 | 即時 benchmark + 定價自動路由 |
| 5 | [opencode-hive](https://github.com/rretsiem/opencode-hive) | 成本優化多 agent | 訂閱模型組合策略、並行 fan-out |
| 6 | [Maestro](https://github.com/Xateh/maestro) | LangGraph plan→execute→review | Graph-based state machine、TUI |
| 7 | [Delegate](https://github.com/nikhilgarg28/delegate) | AI Engineering Manager | 六層沙箱、多 agent 並行、持久記憶 |
| 8 | [Ferrus](https://github.com/RomanEmreis/ferrus) | 確定性狀態機 | 外部狀態機強制執行、crash 恢復 |
| 9 | [Agent Orchestrator](https://github.com/ComposioHQ/agent-orchestrator) | 平行 agent fleet | Reactions 自動修復、Plugin 架構 |
| 10 | [ai-plugins-cc](https://github.com/dysfunc/ai-plugins-cc) | Claude Code 插件 | `/ai:compare` 並行多 provider |
| 11 | [Crewly](https://www.npmjs.com/package/crewly) | Web Dashboard 團隊管理 | 視覺化多 agent 管理 |

---

## task-relay 的不可替代優勢

對比全部 11 個專案後，task-relay 有三個真正獨特的能力，是其他專案沒有同時具備的：

### 1. Packer（`trly pack`）— 智能上下文裁剪

`trly pack` 是 task-relay 最獨特的殺手級功能：

- **自動 Spec 評分**：用 token 分數對 `openspec/changes/<name>/specs/` 做相關性評分，自動選擇最相關的 delta spec
- **Task 精準提取**：根據 task ID 從 `tasks.md` 中精準提取對應 task block 和依賴 task
- **Sidecar 支援**：透過 `packer.yml` 做 explicit capability mapping、design section 指定、repo file 引用
- **動態 Diff**：`--diff-from` 注入 changed files context（test-draft 模式）
- **LLM Resolver**：可選用 DeepSeek 做 model-based spec selection，處理關鍵字匹配無法解決的歧義
- **Context 預算控制**：`byte_estimate` 讓 primary agent 知道 packet 大小，避免超出 context window

其他專案的 delegate 都是「把整個 proposal 貼過去」或「讓 agent 自己讀 repo」。task-relay 是唯一做到**精準上下文裁剪**的，直接影響 token 成本、delegate 品質和 cold start 效率。

### 2. 純 CLI 工具 — 零基礎設施依賴

task-relay 是一個純 CLI 工具，`trly run` 執行完就結束。不需要：

- 背景 daemon（Delegate 的 `delegate start`）
- 資料庫（Maestro 的 SQLite、Delegate 的 SQLite）
- Web server（Crewly 的 Express + WebSocket）
- 持久 process（Delegate 的 agent team）

這確保 task-relay 可以放入任何 script、CI pipeline、cron job，不需要管理服務生命週期。

### 3. Agent-agnostic 成本優先序列 Fallback

task-relay 的 chain 設計是先試便宜、失敗才升級：

```bash
--review-chain claude=claude-haiku,deepseek=deepseek-v4-pro[1m]
```

| 專案 | 模式 | 成本策略 |
|------|------|----------|
| **task-relay** | 序列 fallback（成本優先） | 便宜的先試，失敗才升級 |
| Quest | 並行雙 review + Arbiter | 每次都跑兩個 |
| agent-orchestrator-kit | 單一 role 單一 agent | 無 fallback |
| Delegate | 平行多 agent | 同時跑多個 |
| Cascade AI | 動態路由到最優 | 依 benchmark 選 |

task-relay 是唯一做到「先試便宜、不行再升級」的序列成本優化鏈。Cascade AI 的路由更智能，但它需要即時 benchmark 數據和定價 API。

---

## task-relay 的關鍵弱點

| 弱點 | 嚴重程度 | 說明 | 對應 Candidate Requirement |
|------|----------|------|---------------------------|
| Prompt-only enforcement | 🔴 嚴重 | 靠 agent 讀 Markdown 自行遵守規則，無 runtime 強制 | C3: Enforced delegation trust boundary |
| 無平行執行 | 🟡 中等 | Review/apply 都是序列，不能同時發給多個 agent | — |
| 無 crash recovery | 🟡 中等 | Delegate 掛了就沒了，chain fallback 是唯一防線 | — |
| 無持久狀態 | 🟡 中等 | 無跨 session 記憶 | — |
| 委派輸出驗證不足 | 🟡 中等 | `run` 繞過 `evaluate`/`resolver` 的結構化驗證 | C1: Verifiable delegation output contract |
| Quota 處理可觀測性低 | 🟡 中等 | Retry 可能長時間卡住，fallback 訊號不明確 | C2: Observable, bounded, fast-fallback quota handling |

---

## 借鏡改進方案

### 短期（本月可執行）

#### 改進 1：引入 Quest 的 Arbiter 模式（平行雙審查 + 仲裁）

**現狀**：review chain 是序列 fallback（先 Claude，失敗才 DeepSeek）。

**目標**：增加平行 review 模式，同時發給兩個 agent，由 Arbiter 過濾噪音。

**參考專案**：[Quest](https://github.com/KjellKod/quest)

Quest 的設計：
```
Reviewer A (Claude) ──→ Arbiter ──→ approve/iterate
Reviewer B (GPT)    ──→
```

- 兩個不同模型獨立 review，捕捉不同盲點
- Arbiter 過濾 nitpicks，只保留有共識的 findings
- 支援 Solo mode（簡單任務單 reviewer）和 Full mode（複雜任務雙 reviewer + Arbiter）

**建議實作**：

```bash
# 平行雙審查模式
trly run --target claude,deepseek --review-mode parallel --arbiter claude \
  --prompt-file /tmp/review.md --expect-output spec/delegation_review.md

# 現有序列 fallback 保持不變（成本優先）
trly run --target claude=claude-haiku,deepseek --review-mode sequential \
  --prompt-file /tmp/review.md --expect-output spec/delegation_review.md
```

**實作要點**：
- 新增 `--review-mode` 旗標：`sequential`（預設，現有行為）和 `parallel`
- `parallel` 模式下同時啟動多個 agent process，收集各自的輸出
- Arbiter 讀取兩個 reviewer 的 findings，合併、去重、過濾 noise
- 引入複雜度自適應路由：簡單 change（<3 tasks、無 design.md）自動走 solo，複雜走 parallel

**需要新增的模組**：
- `task_relay/arbiter.py`：Arbiter 合併與過濾邏輯
- `task_relay/cli/run.py`：新增 `--review-mode` 和 `--arbiter` 旗標
- `task_relay/core.py`：`_run_parallel_review()` 函數

---

#### 改進 2：引入 Ferrus 的狀態機（Runtime Trust Boundary Enforcement）

**現狀**：Delegate 的安全邊界完全靠 prompt 文字描述（"Apply agent non-goals: do not modify OpenSpec state..."），沒有任何 runtime 強制。

**目標**：引入輕量 on-disk 狀態機，在 `trly run` 執行前後驗證 delegate 沒有越權。

**參考專案**：[Ferrus](https://github.com/RomanEmreis/ferrus)

Ferrus 的核心設計：
- 狀態存於 `.ferrus/*.md`，agent 之間無狀態
- 外部狀態機控制轉換：`Idle → Executing → Reviewing → Complete/Failed`
- Crash 可恢復，agent 從中斷點繼續
- 每個 phase 有明確的允許操作和禁止操作

**建議實作**：

在 task-relay 的工作目錄中引入輕量狀態檔：

```
.task_relay/
├── state.json    # 當前委派狀態
└── history.jsonl # 委派歷史記錄
```

`state.json` 結構：
```json
{
  "version": 1,
  "session": "a1b2c3d4",
  "change": "redesign-task-relay-architecture",
  "phase": "apply",
  "delegate": {
    "agent": "deepseek",
    "model": "deepseek-v4-pro[1m]",
    "branch": "tr/a1b2c3d4",
    "started_at": "2026-06-27T10:00:00+08:00"
  },
  "constraints": {
    "allow_write_paths": ["src/", "tests/", "docs/"],
    "deny_write_paths": ["openspec/", ".task_relay/", ".git/"],
    "deny_commands": ["git push", "rm -rf", "chmod 777"],
    "max_runtime_seconds": 1800
  }
}
```

**實作要點**：
- `trly run` 執行前寫入 state.json，設定 constraints
- `trly run` 執行後檢查 worktree diff，驗證沒有修改 deny_write_paths
- 若偵測到越權，自動 reject 該 branch，不回整合併
- Crash 恢復：`trly run --resume` 從上次中斷的 state.json 繼續
- 這是 candidate requirement C3 的具體實現

**需要新增的模組**：
- `task_relay/state.py`：狀態讀寫與驗證
- `task_relay/constraints.py`：越權檢查邏輯
- `task_relay/cli/run.py`：整合 state machine 到 run 流程

---

#### 改進 3：引入 Delegate 的平行 Apply 模式

**現狀**：apply chain 是序列的，一次只能委派一個 task。

**目標**：對於多 task change，支援平行 apply，每個 task 獨立 worktree。

**參考專案**：[Delegate](https://github.com/nikhilgarg28/delegate)

Delegate 的平行設計：
- 多個 engineer agent 同時在不同 worktree 工作
- 每個 agent 獨立 branch、獨立 PR
- Reviewer agent 審查每個 diff
- 全部通過後才合併

**建議實作**：

```bash
# 平行 apply 多個 tasks
trly run --targets deepseek,codex --parallel \
  --tasks 1.1,1.2,1.3 \
  --base chg/redesign-task-relay-architecture \
  --isolate
```

**實作要點**：
- `--parallel` 模式下為每個 task 建立獨立 worktree（`tr/<task-id>-<job-id>`）
- 所有 task 完成後，逐一審查 branch diff
- 接受後合併回 `chg/<change-name>` 整合分支
- 任一 task 失敗不影響其他 task（獨立的 worktree）
- Primary agent 仍保留最終審查和合併權

**需要修改的模組**：
- `task_relay/core.py`：`run_isolated_parallel()` 函數
- `task_relay/cli/run.py`：新增 `--parallel` 和 `--tasks` 旗標
- `task_relay/worktree.py`：支援多 worktree 並行管理

---

### 中期（下一季評估）

#### 改進 4：參考 Maestro 評估 LangGraph 遷移

**現狀**：task-relay 的執行流程是純 Python 序列邏輯（`_run_with_fallback` 的 for loop）。

**目標**：評估是否引入 LangGraph 做 graph-based workflow，獲得狀態機強制、typed handoff、可視化等能力。

**參考專案**：[Maestro](https://github.com/Xateh/maestro)

Maestro 的架構：
- LangGraph 作為底層 graph 引擎
- Roles 是 nodes，transitions 是 edges
- Typed handoff：`{ role, provider, payload, log_path }`
- 支援 conditional routing、retry loops、approval gates
- 同樣使用 CLI as subprocess 模式（與 task-relay 一致）

**評估要點**：
- LangGraph 引入的複雜度 vs. 獲得的強制性
- 是否可以用輕量狀態機（改進 2）達到相同效果而不引入 LangGraph
- 如果引入，task-relay 的 agent adapter 是否可以直接作為 LangGraph node
- Maestro 證明了 CLI-as-subprocess + LangGraph 的組合是可行的

**注意**：此改進應在短期 1-3 完成後再評估。如果輕量狀態機（改進 2）已足夠解決 enforcement 問題，可能不需要 LangGraph 的完整複雜度。

---

#### 改進 5：參考 Cascade AI 引入成本追蹤與動態路由

**現狀**：task-relay 的 chain 是靜態設定的（`claude=claude-haiku,deepseek=deepseek-v4-pro[1m]`），不隨 task complexity 動態調整。

**目標**：引入 task complexity 評估，自動選擇 model tier，並追蹤成本節省。

**參考專案**：[Cascade AI](https://www.npmjs.com/package/cascade-ai)

Cascade AI 的核心能力：
- 即時 benchmark + 定價自動選擇最優模型
- 即時顯示委派節省金額（"saved $5.63 — 90% vs. all-T1"）
- Boardroom 模式：T1 生成計畫後暫停供審查

**建議方向**：
- 在 `trly pack` 階段評估 task complexity（task 數量、spec 數量、design complexity）
- 根據 complexity 自動選擇 chain 中的起始 tier
- 在 `trly trace` 中顯示成本摘要（token 用量、預估費用、節省金額）
- 利用現有的 token usage 追蹤（`AgentRunResult.usage`）計算成本

---

#### 改進 6：參考 ai-plugins-cc 引入並行多 Provider 比較

**現狀**：review 和 apply 都是單一 provider chain，無並行比較能力。

**目標**：支援 `/ai:compare` 風格的並行多 provider 輸出比較。

**參考專案**：[ai-plugins-cc](https://github.com/dysfunc/ai-plugins-cc)

ai-plugins-cc 的 `/ai:compare`：
- 將同一個 review 並行發給多個 provider
- 返回 side-by-side 報告
- 支援 `--providers=A,B,C` 指定參與比較的 provider

**建議方向**：
```bash
# 並行比較多個 agent 的 review 品質
trly run --targets claude,deepseek,codex --compare \
  --prompt-file /tmp/review.md --expect-output spec/delegation_review.md
```

---

## 不建議引入的方向

以下參考專案的能力雖然有吸引力，但**不建議在現階段引入**：

| 能力 | 來源專案 | 不建議原因 |
|------|----------|-----------|
| Web Dashboard | Crewly、Delegate | 與 task-relay 的輕量 CLI 定位衝突，增加基礎設施依賴 |
| 持久 Agent Team | Delegate | 需要 daemon + 資料庫，違反「零基礎設施依賴」的核心優勢 |
| Docker/K8s Runtime | Agent Orchestrator | 過度隔離，worktree 已足夠應對「不可靠但非惡意」的威脅模型 |
| Slack/Linear 整合 | Delegate、Agent Orchestrator | 超出 task-relay 的範圍，應由外部 script 組合 |
| 完整 5-Role Pipeline | agent-orchestrator-kit | task-relay 聚焦 review + apply 兩個委派點，完整 pipeline 可與 agent-orchestrator-kit 組合使用 |

---

## 優先級總結

| 優先級 | 改進 | 參考專案 | 預計工作量 | 影響範圍 |
|--------|------|----------|-----------|----------|
| P0 | Arbiter 平行雙審查 | Quest | 3-5 天 | `core.py`、`arbiter.py`、CLI |
| P0 | 狀態機 Trust Boundary | Ferrus | 5-7 天 | `state.py`、`constraints.py`、CLI |
| P1 | 平行 Apply | Delegate | 3-5 天 | `core.py`、`worktree.py`、CLI |
| P2 | LangGraph 評估 | Maestro | 調研 3 天 | 架構評估，不立即實作 |
| P2 | 成本追蹤與動態路由 | Cascade AI | 5-7 天 | `packer.py`、`trace.py` |
| P3 | 多 Provider 比較 | ai-plugins-cc | 3-5 天 | `core.py`、CLI |

---

## 策略定位

task-relay 的正確定位不是「多 agent 編排平台」，而是 **OpenSpec 的輕量委派執行層**：

```
agent-orchestrator-kit  → 定義流程（what to do）
task-relay              → 執行委派（how to delegate）
```

兩者是互補關係，不是競爭關係。task-relay 應保持：

1. **零基礎設施依賴**：純 CLI，無 daemon、無資料庫、無 Web server
2. **Packer 核心優勢**：持續強化智能上下文裁剪
3. **成本優先**：序列 fallback + 未來動態路由
4. **可組合**：可被 agent-orchestrator-kit、Quest 等流程工具呼叫

在此定位下，上述改進方案旨在補強 enforcement 和 parallelism 短板，而非將 task-relay 變成另一個 Delegate 或 Crewly。
