## Context

task-relay 已經具備平行 reviewer、串行 arbiter、review artifact 驗證、`trly review` wrapper、`--save/--no-save` 與 managed block persistence。缺口不在 review gate engine，而是在 `$trly-review` skill 觸發後 Primary agent 應如何與使用者協調設定。

目前設定儲存格式是 `agent:/persona=model`，例如 `codex:/review=gpt-5.5-high`。這個格式足以表達 reviewer/arbiter routing，但不直接分離 `model` 與 Codex `effort`。互動 UX 需要展示 `Role / Agent / Model / Effort / Personas` 表格，同時避免引入新的 managed block schema。

## Goals / Non-Goals

**Goals:**

- 讓 `$trly-review` 有明確的使用者互動 contract。
- 優先使用既有 saved review config，並在執行前以表格確認。
- 在沒有 saved config 或使用者拒絕時，逐步建立 reviewer 與 arbiter 設定。
- 將使用者輸入的 persona alias 正規化為現有 slash persona。
- 保留既有 `ReviewRoleEntry` 與 managed block 格式。
- 明確規範 `REVISE` 時 Primary 如何套用 arbiter `actionable_items` 並驗證 revision readiness。

**Non-Goals:**

- 不重新設計 review gate runner、arbiter JSON schema 或 delegate execution model。
- 不新增獨立 `effort` storage 欄位。
- 不在 propose 階段執行 reviewer 或 arbiter delegate。
- 不讓 `$trly-review` 採納未經 arbiter adjudicate 的 reviewer 建議。
- 不讓 arbiter 或 reviewer 修改 OpenSpec artifacts。

## Decisions

### 1. `$trly-review` 是 skill-level orchestrator，`trly review` 仍是 stable CLI entry point

`$trly-review` 負責互動流程、確認與後續 artifact handling。實際 review execution 仍透過：

```bash
trly review --change <change>
```

或在 one-time override 時透過：

```bash
trly review --change <change> --reviewers <entries> --arbiter <entry>
```

這讓第一版不需要改動 review gate 核心。若實作需要降低 agent prompt 的自由度，可以新增 read-only helper 或 CLI JSON output 來列出 resolved config；但 execution contract 仍維持 `trly review`。

替代方案是新增完整 interactive CLI mode，例如 `trly review --interactive`。這能減少 skill prompt 邏輯，但會把 agent UI 與 terminal UI 綁在一起；目前需求是定義 skill 觸發行為，所以第一版以 skill contract 為主，CLI helper 為輔。

### 2. Saved config 表格由現有 role entries 派生

Saved config 來源維持現狀：

1. repo-local `AGENTS.md`
2. repo-local `CLAUDE.md`
3. user-level managed block

Skill 展示時將每個 reviewer 與 arbiter 轉成表格：

| Role | Agent | Model | Effort | Personas |
| --- | --- | --- | --- | --- |
| reviewer | codex | gpt-5.5 | high | review |
| arbiter | deepseek | deepseek-v4-pro | n/a | cso |

`Model` 與 `Effort` 的 display rule：

- 對 Codex model id `gpt-5.5-high`、`gpt-5.5-medium` 等，顯示為 `Model=gpt-5.5` 與 `Effort=high/medium`。
- 對非 Codex agent，`Effort=n/a`，model 直接顯示完整 id 或 `default`。
- 回寫時仍使用完整 model id，例如 `codex:/review=gpt-5.5-high`。

### 3. 沒有 saved config 時使用固定 wizard sequence

Reviewer sequence：

```text
reviewer-agent
  > reviewer-model
  > reviewer-effort only if agent == codex
  > reviewer-personas
  > add next reviewer?
```

Arbiter sequence：

```text
arbiter-agent
  > arbiter-model
  > arbiter-effort only if agent == codex
  > arbiter-personas
  > add next arbiter?
```

至少需要一個 reviewer 與一個 arbiter。若使用者想跳過 arbiter，skill 應解釋 review gate 需要 arbiter 作為獨立決策來源，並要求選擇或取消 review。

### 4. Persona alias 是 UX 層正規化，不是新 persona registry

互動輸入可接受短名：

| Alias | Stored persona |
| --- | --- |
| review | `/review` |
| cso | `/cso` |
| qa | `/qa-only` |
| qa-only | `/qa-only` |
| ceo | `/plan-ceo-review` |
| engineer | `/plan-eng-review` |
| plan-ceo-review | `/plan-ceo-review` |
| plan-eng-review | `/plan-eng-review` |

若使用者輸入已含 `/` 的 persona，skill 或 helper 只做 trim 與合法性檢查。未知 persona 可以被接受為 slash persona，但需在表格中顯示原值，讓使用者確認。

### 5. `REVISE` 是 Primary artifact update workflow

`trly review` 完成後，Primary 依 final decision 執行：

- `APPROVE`：不修改 OpenSpec artifacts，回報 reviewer/arbiter 摘要。
- `REJECT`：不修改 OpenSpec artifacts，停止 apply。
- `REVISE`：讀取 `delegation_review_result.json` 與 arbiter artifacts，只套用 `actionable_items` 指名的 target artifacts。

Primary 不得重新仲裁 reviewer 衝突、不得直接採納 reviewer finding、不得刪改 arbiter required changes。套用後必須執行：

```bash
trly review-gate --change <change> --verify-revision
```

只有 verification 回報 `apply_ready: true` 時，skill 才能把 review 視為完成。

## Risks / Trade-offs

- [Risk] 表格中的 `Model`/`Effort` 與底層 model id 不完全一對一。→ Mitigation：只有 Codex known suffix 做 split；其他 model id 原樣顯示。
- [Risk] Skill prompt 互動邏輯可能與 CLI helper 演進不同步。→ Mitigation：把 formatting/alias normalization 實作成可測試 helper，skill 文件只引用 contract。
- [Risk] 沒有 saved config 時，agent 逐項詢問會增加 review 啟動時間。→ Mitigation：一旦使用者選擇儲存，後續 `$trly-review` 直接展示並確認。
- [Risk] `REVISE` verification 只檢查 target artifact 是否改變，不能證明 acceptance criteria 完全滿足。→ Mitigation：Primary 仍需依 arbiter contract 判讀內容，verification 只作為最低 gate。

## Migration Plan

1. 更新 generated `trly-review/SKILL.md`，加入 saved config display、confirmation、wizard sequence、persona alias 與 decision handling。
2. 視需要新增 review config formatting helper，輸出表格資料與 normalized entries。
3. 更新 tests，覆蓋 saved config display、Codex model/effort split、persona alias 與 `REVISE` instructions。
4. 重新產生或安裝 skill bundle，確保 project/user scope 的 `$trly-review` 取得新 contract。

## Open Questions

- 是否要把 interactive selection 做成 CLI `trly review --interactive`，或維持由 skill agent 逐項詢問並組出 CLI flags？
- Unknown persona 是否應允許，只要求 slash normalized，或必須限制在已安裝 persona templates？
