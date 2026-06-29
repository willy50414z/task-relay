## Context

task-relay 目前已有三個相關基礎：

- `trly run` 可呼叫單一 target，或用 ordered fallback targets 執行 raw prompt。
- `trly install` 會寫入 managed AGENTS/SKILL guidance，其中 review path 目前使用 `review-chain`。
- review delegation output 已開始要求 `--expect-output`，但現有 contract 仍以單一 review artifact 為主。

這次變更的核心不是讓 Primary 多看幾份文字報告，而是把 propose phase 的 review gate 做成可驗證 DAG 節點：

1. 多個 reviewer persona 並行產出隔離 JSON 報告。
2. 多個 arbiter persona 依序讀取完整 packet 與前序裁決。
3. CLI 驗證 arbiter JSON 並以程式化方式決定 DAG 流向。
4. Primary 只在 `REVISE` 時依 Arbiter 的 revision contract 編輯 OpenSpec 文件；arbiter 本身永遠不改文件，但 Arbiter 擁有唯一仲裁權。完成修訂後，Primary 可直接進入 apply。
5. Review gate 另外輸出 machine-readable handoff artifact，讓 apply 前能 deterministic 地檢查 revision contract 對應 artifact 是否已有變更。

## Goals / Non-Goals

**Goals:**

- 將 review 設定從 ordered fallback chain 改為 parallel reviewer list。
- 支援 serial arbiter chain，預設以 CEO/product arbiter 先判斷價值與範圍，再以 engineering arbiter 判斷技術可行性。
- 要求至少一個 arbiter；沒有 arbiter 時 review gate 無獨立決策來源，必須以設定錯誤失敗。
- 允許 reviewer 與 arbiter 指定同一個 agent，只要 persona、prompt packet 與 output artifact 隔離。
- 為每個 reviewer 與 arbiter stage 建立唯一輸出檔，避免平行寫入衝突。
- 以 JSON schema 驗證 reviewer/arbiter 輸出，並讓 CLI 根據 `decision` 做 DAG gate 決策。
- 將 gstack skills 萃取為 persona templates，不直接執行會修改程式碼、互動提問或依賴瀏覽器狀態的完整 skill workflow。

**Non-Goals:**

- 不改變 apply-chain 的 ordered fallback 語義。
- 不讓 arbiter 修改 `proposal.md`、`design.md`、`tasks.md` 或 specs。
- 不讓 Primary 重新仲裁 reviewer 衝突、覆寫 Arbiter 裁決，或把 Arbiter 的 `REJECT` 改寫成 `REVISE`。
- 不把決策邏輯寫進 arbiter prompt；prompt 只要求輸出 JSON，CLI 才是狀態機。
- 不要求 reviewer 與 arbiter 必須使用不同 agent。
- 不在本變更中建立完整 outcome-resolution engine；review gate 使用較輕量但嚴格的 artifact/schema 驗證。

## Decisions

### 1. 新增 review gate API，而不是重用 `run(targets=[...])`

新增 `task_relay.review_gate` 或同等模組，提供：

- `run_parallel_review(config, packet) -> list[ReviewArtifact]`
- `run_arbiter_chain(config, packet, reviews) -> ReviewGateResult`
- `run_review_gate(config, change_dir) -> ReviewGateResult`

`trly run --targets` 保持 ordered fallback，因為該語義已被 apply 與 raw execution 使用。Review gate 的 parallel fan-out 以新的 API/CLI entrypoint 承載，避免讓 `targets` 在不同情境下同時代表 fallback 與 parallel。

替代方案：把 `trly run --targets` 加上 `--parallel`。此方案較短，但會讓 run command 同時承擔 raw execution、fallback、review gate artifact verification 與 DAG decision，邊界不清。

Review gate runner 使用 `asyncio.create_subprocess_exec()` 呼叫既有 `trly run --target <agent> --prompt-file <packet> --expect-output <path>`。這保留既有 CLI 的 adapter、model、cwd、expected-output 與 trace 行為，同時讓 parent review gate 只負責 parallel orchestration、timeout 與 artifact/schema aggregation。第一版不以 threadpool 包同步 `core.run()`，避免在同一 Python process 內混合多個 agent invocation 的 stdout/stderr 與 tracing state。

### 2. Reviewer 設定拆成 agent 與 persona

設定支援簡短格式與完整格式：

- `--reviewers claude,deepseek,codex`
- `--reviewers claude:/review,deepseek:/cso,codex:/qa-only`

簡短格式使用預設 reviewer persona 分配；完整格式可指定 persona。Persona 來自 gstack skill 的角色萃取，例如：

- `/review` -> Pre-Landing Code Reviewer：檢查 diff/計畫意圖、資料安全、LLM trust boundary、scope drift。
- `/cso` -> Security Officer：威脅模型、secret、供應鏈、CI/CD、LLM security、OWASP/STRIDE。
- `/qa-only` -> User-Facing QA：使用者流程、錯誤可重現性、測試覆蓋與可驗收性；若沒有可運行 app，降級為 QA testability review。

同一 agent 可以在 reviewer 與 arbiter 中重複出現，因為每次呼叫使用不同 prompt packet、不同 persona 與不同 output path。Reviewer id 由 agent slug、persona slug 與必要時序號組成，例如 `claude_review`、`deepseek_review`、`claude_review_2`，避免「不同 agent 相同 persona」或「同 agent 同 persona 重複」碰撞。

### 3. Arbiter 為串行 chain，不是平行投票

Arbiter 預設順序為：

1. `plan-ceo-review` persona：先判斷產品價值、範圍、需求完整性與是否值得做。
2. `plan-eng-review` persona：再判斷架構、資料流、風險、測試、效能與部署可行性。

每個 arbiter stage 都讀取：

- 原始 `proposal.md`
- `design.md`
- `tasks.md`
- delta specs
- 所有 reviewer JSON
- 前序 arbiter JSON

Final decision 由 CLI 聚合：

- 任一 arbiter `REJECT` -> final `REJECT`，DAG gate 進入 STOP。
- 無 `REJECT` 但任一 arbiter `REVISE` -> final `REVISE`，Primary 依 Arbiter revision contract 編輯 OpenSpec 文件後可進入 Apply Wave。
- 全部 arbiter `APPROVE` -> final `APPROVE`，解鎖 Apply Wave。

`confidence` 保留為人類判讀與 audit 欄位，第一版不參與 DAG 決策。DAG 決策只讀 `decision` enum，避免隱性閾值造成難以預期的 gate 行為。

替代方案：所有 arbiters 平行執行後投票。此方案較快，但無法表達「先判斷是否值得做，再判斷如何安全做」的依賴順序，也較難解釋 REJECT/REVISE 的優先級。

### 4. JSON 是流程 contract，Markdown 是人類摘要

Reviewer 與 arbiter 均輸出 JSON，CLI 只信任 JSON 欄位。建議檔名：

- `spec/delegation_review_<reviewer_id>.json`
- `spec/delegation_arbiter_<stage_id>.json`
- `spec/delegation_review.md` 作為合併後的人類可讀摘要

Reviewer JSON 建議包含：

```json
{
  "reviewer": "claude:/review",
  "verdict": "PASS | CONCERNS | BLOCKED",
  "summary": "...",
  "findings": [
    {
      "severity": "critical | high | medium | low",
      "area": "architecture | security | qa | scope | tests",
      "description": "...",
      "recommendation": "..."
    }
  ]
}
```

Arbiter JSON 必須包含：

```json
{
  "decision": "APPROVE | REVISE | REJECT",
  "confidence": 0.0,
  "summary": "...",
  "actionable_items": [
    {
      "target_artifact": "proposal.md | design.md | tasks.md | specs/<capability>/spec.md",
      "required_change": "...",
      "acceptance_criteria": "..."
    }
  ],
  "conflict_resolution": "No conflicts"
}
```

CLI 驗證 enum、必填欄位、JSON parseability 與非空 artifact。缺漏或格式錯誤是 infrastructure failure，不得被當作 review 通過。

Reviewer `verdict` 是給 arbiter 的 advisory signal，不直接決定 DAG gate。Reviewer 階段採 fail-all 政策：任何必需 reviewer 逾時、缺 artifact、輸出空檔或 JSON schema invalid，整個 review gate 以 infrastructure failure 結束，不會使用部分 reviewer 報告繼續仲裁。第一版不提供最低成功 reviewer 數門檻，避免 partial review 被誤判為完整 gate。

Arbiter `actionable_items` 在 `REVISE` 時是約束性的 revision contract，不是給 Primary 自由取捨的建議。Primary 的文件修訂角色只包含：

- 將每個 `actionable_items[].required_change` 套用到指定 artifact。
- 保留 Arbiter 的裁決理由與 artifact paths 供 audit。
- 若 required change 不可執行、互相矛盾或 target artifact 不明，回報 clarification-needed infrastructure failure 或重新呼叫 Arbiter 補明確裁決。

這份 revision contract 是 Arbiter 對「原始 proposal/design/tasks/specs 與 reviewer findings 差異」做完仲裁後的唯一修改方向來源。Primary 不得直接採納未被 Arbiter 納入 contract 的 reviewer 建議。

Primary 不得自行合併 reviewer 意見、重判 reviewer 衝突、刪減 Arbiter required changes，或把 Arbiter 的決策升降級。修訂後是否重跑 review gate 由 Primary 自主決定，但第一版 gate 不強制 rerun；只要沒有 `REJECT`，Primary 在完成 revision contract 後即可進入 apply。

### 5. Packet generation 以 mode 擴充

新增 `review-arbiter` packet/template，用於把原始 OpenSpec 文件與 reviewer outputs 組成單一 packet。Template 需明確寫入：

「注意：Arbiter 本身也是一個模型呼叫，但它不負責修改程式碼或 OpenSpec 文件，只負責給出決策 JSON 與約束性 revision contract。trly CLI 必須根據 decision 欄位程式化地決定下一步。Primary 只能按 revision contract 修訂文件，不得重新仲裁 reviewer 衝突或覆寫 Arbiter 裁決。不要把 DAG 狀態轉移邏輯寫在 Arbiter 的 Prompt 裡，狀態轉移邏輯必須寫在 CLI 的程式碼中。」

Reviewer templates 則只提供 persona 與輸出 schema，不允許 reviewer 直接修改 proposal/design/tasks/specs。

### 6. Install guidance 遷移策略

`trly install` 新增：

- `--reviewers <entries>`：逗號分隔 reviewer entries。
- `--arbiter <entry>`：可重複或逗號分隔，表示 serial arbiter chain。
- `--global-timeout <seconds>`：完整 review gate 的最大等待秒數。

`--review-chain` 保留為 migration window 的 deprecated flag。若使用者仍傳入 `--review-chain`：

- CLI 顯示 deprecation warning。
- 只在沒有 `--reviewers` 時取原 chain 的 primary entry 轉成單一 reviewer，避免把原本的 fallback entries 靜默變成平行執行成本。
- 不再在 managed guidance 中描述成 fallback chain。

### 7. Gate CLI 與 exit code

新增 review gate command，例如 `trly review-gate --change <change> ...`。它不是排程器，只是可由 Primary 或 managed guidance 呼叫的 gate command；所謂 DAG gate 以「CLI exit code + JSON result + Primary 程式化判讀」實作。

建議 exit code：

- `0`：final decision `APPROVE`
- `10`：final decision `REVISE`
- `20`：final decision `REJECT` / STOP
- `1`：runtime 或 agent execution failure
- `2`：argument/configuration failure
- `124`：timeout

`REVISE` 仍保留為獨立 decision 與 exit code，讓 Primary 能在進入 apply 前明確處理 revision contract；但第一版不強制 rerun review gate。

### 8. Review-to-Apply handoff artifact

Review gate 除了 `spec/delegation_review.md` 外，還會輸出 machine-readable result artifact，例如：

- `spec/delegation_review_result.json`

其中至少包含：

- final `decision`
- `apply_allowed`
- `requires_primary_revision`
- reviewer / arbiter artifact paths
- aggregated `actionable_items`
- `target_artifacts` 與執行 review gate 時的 baseline digest

對 `REVISE` 而言，這個 result artifact 是 apply 前 handoff 的主要程式化輸入。Primary 或後續 DAG 節點可以透過 revision verification 檢查：

- Arbiter contract 指向的 artifacts 是否至少已被修改
- 哪些 target artifacts 仍未變更，因此還不該進 apply

第一版 verification 只檢查 target artifact 是否相對 baseline 發生變更，不自動判斷 acceptance criteria 是否真正滿足；acceptance criteria 仍由 Primary 在 apply 前負責判讀。

## Risks / Trade-offs

- [Risk] 平行 reviewer 會增加成本與等待時間。→ Mitigation：支援 `--global-timeout`，並讓 reviewer 數量由設定控制。
- [Risk] Reviewer artifact 命名若只用 agent name，重複 agent 會衝突。→ Mitigation：以 stage id/persona slug 產生唯一 output path，必要時加序號。
- [Risk] Arbiter JSON 無效會造成 gate 卡住。→ Mitigation：CLI 將 invalid JSON 視為 named failure，輸出明確錯誤與 artifact path。
- [Risk] 直接把 gstack skill 當作執行流程會導致自動修改或互動式等待。→ Mitigation：只萃取 persona prompt，不執行完整 gstack workflow；模板需記錄萃取來源 skill 名稱與日期。
- [Risk] 舊 AGENTS managed block 仍含 `review-chain`。→ Mitigation：reinstall 會更新 managed block；parser 在 migration window 支援 legacy 欄位並提示使用新格式。

## Migration Plan

1. 新增 review gate config model 與 parser，先支援新舊設定同時讀取。
2. 更新 `trly install`、wizard 與 `delegation.py` managed guidance 生成邏輯，輸出 `reviewers`/`arbiter`。
3. 新增 reviewer/arbiter templates 與 packet mode。
4. 實作 parallel reviewer runner 與 serial arbiter runner。
5. 新增 JSON validation 與 final decision mapping。
6. 更新測試覆蓋新設定、舊設定 migration、artifact isolation、timeout、invalid JSON 與 DAG gate decisions。
7. 在下一個 breaking window 移除或硬錯 `--review-chain`。

## Open Questions

- `--arbiter` 的預設值是否應由 install mode 自動填入 `claude:/plan-ceo-review,claude:/plan-eng-review`，或要求使用者顯式選擇；不論預設策略，執行 review gate 時 arbiter list 不得為空。
- `spec/delegation_review.md` 是否應總是保留為合併摘要；建議保留，方便 AGENTS/SKILL guidance 與人類 reviewer 讀取。
