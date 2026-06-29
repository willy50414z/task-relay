# Delegation Review — `add-parallel-review-arbiter` 提案審查

- 模式：`review-proposal`
- 審查目標：需求清晰度、方向正確性、實作計畫完整度（客觀視角）
- 審查範圍：`proposal.md` / `design.md` / `tasks.md` / `specs/parallel-review-arbitration/spec.md` + 既有實作（`task_relay/cli/__init__.py`、`core.py`、`delegation.py`、`wizard.py`、`packer.py`、現有 review-proposal 模板）
- 結論摘要：**方向合理、值得做，可在收斂下列 major 後進入實作。沒有發現會否決方向的 blocker，但有 4 個 major（其中「無 arbiter 時決策來源」與「reviewer 失敗策略」若不先定義會在核心 contract 留下未定義行為）需動工前澄清。** 多處 Impact / flag 與既有程式碼對不上，需更正以免實作者找錯檔案。

---

## 整體評價（正面）

- **核心動機成立**：現有 review path 確實只有單一 `review_chain`（`delegation.py:162` 起），語義是「primary reviewer 先跑、fallback」，且只驗證單一 `spec/delegation_review.md` 是否非空（`core.py:119 verify_expected_output`）。提案指出的「無法平行取得多觀點、單一輸出檔不利平行寫入、缺獨立仲裁節點」三點，與既有碼一致，問題描述屬實。
- **邊界拆分正確**：Decision 1 不重用 `run(targets=[...])` 而新增 review gate API 是對的——`--targets` 在現碼確實是 ordered fallback（`add_target_args` help 字面寫 "ordered fallback"，`core._run_with_fallback`），若疊上 parallel 會讓同一旗標兩義。
- **JSON 為流程 contract、Markdown 為人類摘要（Decision 4）方向正確**，且「決策邏輯寫在 CLI 而非 arbiter prompt（Decision 5）」符合既有「不信任 stdout、以 artifact 驗證」的設計哲學。
- **Non-goals 清楚**：明確不改 apply-chain fallback、不讓 arbiter 改文件、不建完整 outcome-resolution engine，範圍收斂得當。

---

## Findings

### [major] 無 arbiter 設定時，最終決策無來源
- **問題描述**：最終 gate 決策（spec「Programmatic gate decision」、Decision 3 聚合規則）**只**從 arbiter JSON 的 `decision` 欄位推導。但 `--arbiter` 是新增設定，未說明是否為必填。若使用者只設 `--reviewers` 而未設 `--arbiter`（或 arbiter chain 為空），gate 沒有任何 `decision` 來源，APPROVE/REVISE/REJECT 三態皆無法產生。
- **影響範圍**：核心 contract（`run_review_gate` 回傳值）、CLI exit code、DAG gate 解鎖條件；task 1.1（config 模型）、4.3（聚合）、5.2（gate node）。
- **建議方向（請使用者裁示）**：擇一並寫入 spec — (a) arbiter 為必填，空 arbiter 直接 named failure；或 (b) 定義「無 arbiter」的退化策略（例如以 reviewer verdict 聚合）。建議 (a) 較單純且符合 Decision 4 的嚴格性，但會改變部分使用者的最小設定習慣，故交由使用者決定。

### [major] `--review-chain` 自動轉成 `--reviewers` 會靜默改變執行語義
- **問題描述**：Decision 6 / Risks 提出「沒有 `--reviewers` 時把 `--review-chain` 轉成 reviewer list」。但 review-chain 在現碼是**有序 fallback**（只有 `review_chain[0]` 是 primary，其餘為備援，正常情況只跑一個）；轉成 reviewer list 後會變成**全部平行 fan-out 同時執行**。對一個原意是「3 選 1 fallback」的 3-agent chain，遷移後變成 3 個都跑，成本約 3 倍且行為語義不同。
- **影響範圍**：`delegation.py`、`wizard.py` 既有 review-chain 解析；既有安裝者的成本與 review 行為；task 1.3、6.1。
- **建議方向**：不要靜默等價轉換。建議僅取 `review_chain[0]`（原 primary）轉為單一 reviewer，或只發 deprecation warning 並要求顯式改用 `--reviewers`，避免把 fallback 數量誤當平行度。最終策略請使用者決定。

### [major] reviewer 失敗 / invalid JSON / 部分缺漏的 gate 策略未定義
- **問題描述**：spec 只定義了 timeout 要 fail loudly，以及「缺漏或格式錯誤是 infrastructure failure」。但未定義**單一 reviewer**失敗時整個 gate 的行為：是 fail-all（任一 reviewer 壞掉就整個 gate fail），還是 proceed-with-available（用已成功的 reviewer 報告餵給 arbiter）？平行 fan-out 中單一 agent flaky 是常見情況，這會直接決定 gate 的健壯度。
- **影響範圍**：`run_parallel_review` 回傳契約、arbiter packet 組裝（缺報告時 arbiter 看到什麼）；task 3.1、3.4、4.1、6.5。
- **建議方向**：明確寫出 reviewer 失敗政策與「arbiter 至少需要幾份有效 reviewer 報告才可裁決」。建議預設 fail-loudly 但允許設定「最低成功 reviewer 數」門檻；請使用者裁示嚴格度。

### [major] Impact 檔案清單與既有結構不符，會誤導實作
- **問題描述**：Impact 與 tasks 多處引用 `task_relay/assets/task-relay-delegation/SKILL.md`，但該檔在來源樹**不存在**（`task-relay-delegation/` 下只有 `agents/` 與 `templates/`）。managed guidance 實際是由 `delegation.py` 以程式動態產生（`_features_policy` 等），寫進 `AGENTS.md` / `CLAUDE.md` 的 managed block（`MANAGED_BLOCK_START`）。因此「更新 SKILL.md」其實是「改 `delegation.py` 的 policy 生成函式」。
- **影響範圍**：task 1.5、2.x 的落點；實作者依 Impact 會找不到檔案。
- **建議方向**：更正 Impact／tasks，把「managed AGENTS/SKILL guidance」對應到 `delegation.py` 的 policy 生成，而非不存在的 SKILL.md 資產。（提醒：此為審查意見，請由 Primary 決定是否修訂提案，本審查不直接改文件。）

### [minor] `--global-timeout` 有實作任務但無設定入口
- **問題描述**：Risks 與 task 3.4 都提到 global timeout，但 What Changes 與 task 1.2 的 install flag 清單（`--reviewers`、`--arbiter`）未包含它，現碼亦無 `global-timeout`（grep 無結果）。設定來源未定（install flag？gate command flag？config 模型預設值？）。
- **影響範圍**：task 1.1、1.2、3.4；CLI 介面一致性。
- **建議方向**：在 config 模型與 CLI flag 明確定義 timeout 的設定路徑與預設值。

### [minor] reviewer `verdict` 與 arbiter `confidence` 蒐集但未使用
- **問題描述**：reviewer JSON 的 `verdict`（PASS/CONCERNS/BLOCKED）與 arbiter JSON 的 `confidence` 在最終聚合（Decision 3 只用 arbiter `decision`）中沒有任何作用。reviewer BLOCKED 不會擋 gate，只有 arbiter REJECT 會。
- **影響範圍**：schema 設計、task 4.1/4.2；使用者對「BLOCKED 卻 APPROVE」的預期落差。
- **建議方向**：要嘛定義這些欄位的實際用途（例如 confidence 低於門檻時降級為 REVISE），要嘛標為 advisory/optional 並在模板註明不影響決策。

### [minor] reviewer 唯一 id / 輸出檔命名規則未定死，存在碰撞缺口
- **問題描述**：spec 的 isolation 範例用 persona slug 命名（`delegation_review_review.json`、`_cso.json`、`_qa-only.json`），且「same agent 多次」場景靠不同 persona 區分。但**相同 persona、不同 agent**（如 `claude:/review` 與 `deepseek:/review`）在純 persona-slug 命名下會碰撞到同一檔。Risk 雖提到「必要時加序號」，但唯一 id 推導規則未在 spec 釘死。
- **影響範圍**：task 3.3、6.3；artifact isolation 正確性。
- **建議方向**：在 spec 明確定義 id 由 agent + persona（必要時序號）組成，並補一個「不同 agent 相同 persona」的 scenario。

### [minor] 並行機制與既有同步架構的落差未說明
- **問題描述**：design 說用 `asyncio.gather()` 啟動多個 `trly run` 子行程，但整個 codebase 無任何 async（grep `asyncio/async def/await` 皆無），`core.run` 是同步函式。到底是 asyncio 子行程、threadpool 包同步 `run`、還是 shell 出去呼叫 `trly` CLI，未指定；這會影響 trace/session 記錄、cwd 與 worktree 隔離行為。
- **影響範圍**：task 3.1、3.2；`trace.py` session 記錄、`core.run` 重用與否。
- **建議方向**：在 design 釘住並行實作策略（建議 threadpool 包既有同步 `core.run` 以重用 trace/verify 路徑，或明確改走 subprocess 並說明 trace 如何彙整）。

### [minor] 既有 review-proposal 模板與新 reviewer JSON schema 詞彙不一致
- **問題描述**：現有 `templates/review-proposal.md` 要求 reviewer 輸出 Markdown，severity 用 `blocker/major/minor/suggestion`，輸出到單一 `spec/delegation_review.md`。新 reviewer schema 改用 `verdict: PASS/CONCERNS/BLOCKED` + `findings[].severity: critical/high/medium/low` + 唯一 JSON 路徑。task 2.3 雖要重寫，但需注意三套詞彙（reviewer severity、reviewer verdict、arbiter decision）並存易混淆。
- **影響範圍**：task 2.1/2.2/2.3；模板一致性與 schema 驗證。
- **建議方向**：統一並文件化 severity / verdict / decision 三組 enum 的關係，避免 reviewer 與 arbiter 詞彙互相污染。

### [suggestion] gate command 名稱與 exit code 表未列舉
- **問題描述**：task 5.1「新增或擴充 CLI command」未指定指令名（`trly review-gate`？）與各決策對應的穩定 exit code。Primary 程式化決策依賴穩定 exit code，但 spec 未列舉碼表。
- **建議方向**：補一張 decision → exit code 對照（APPROVE/REVISE/REJECT/infra-failure/timeout 各自的碼），並固定指令名。

### [suggestion]「DAG gate / Apply Wave」屬概念模型，易被誤讀為要建排程器
- **問題描述**：proposal/design 反覆用「DAG apply gate」「Apply Wave」「gate node」，但 codebase 並無 scheduler/wave 引擎；review/apply workflow 目前僅是 `delegation.py` 產生的 managed guidance 文字 + `--isolate` worktree 機制。Non-goal 已說不建 outcome-resolution engine，但用詞仍可能讓實作者以為要做 orchestrator。
- **建議方向**：在 design 註明 gate 實際以「CLI exit code + managed guidance + Primary 程式化判讀」實現，非新增排程引擎，與 Non-goal 對齊。

### [suggestion] persona 來源為外部 gstack skills，存在 snapshot drift
- **問題描述**：reviewer/arbiter persona 由 gstack 的 `/review`、`/cso`、`/qa-only`、`/plan-ceo-review`、`/plan-eng-review` 萃取。萃取為靜態模板後，gstack 更新時模板會 drift；且假設 delegate agent 能在無 gstack 環境下依模板扮演該角色。
- **建議方向**：記錄萃取來源與版本，並定義模板更新策略（或在模板註明來源 commit）。

### [suggestion] REVISE 後的重送審範圍未定義
- **問題描述**：Open Question 已合理決定「第一版不自動重跑」。但未定義 Primary 改完文件後重跑 gate 時，是否需重跑**全部** reviewer + arbiter，或可只重跑受影響者。同時缺少防無限 REVISE 迴圈的上限。
- **建議方向**：在 spec 補「REVISE 重送審需全量重跑」與（可選）最大 revision 輪數，避免迴圈。

---

## 待使用者裁示的問題（不自行決定）

1. `--arbiter` 是否必填？無 arbiter 時 gate 決策來源為何？（對應 major #1）
2. `--review-chain` 遷移：取 primary 單一 reviewer、全量平行、或僅警告不轉換？（對應 major #2）
3. reviewer 部分失敗策略：fail-all 還是 proceed-with-available？arbiter 最低有效 reviewer 數門檻？（對應 major #3）
4. `verdict` / `confidence` 是否要進入決策邏輯，或維持純 advisory？（對應 minor）
5. 並行實作走 threadpool（重用同步 `core.run`）還是 subprocess？（對應 minor）

---

## 建議的先決順序（僅建議，不修改 tasks.md）

1. 先收斂 major #1（無 arbiter 決策來源）與 major #3（reviewer 失敗策略）——這兩者定義 gate 核心 contract，會影響 task 1.1/3.x/4.3 的型別與回傳值。
2. 再更正 major #4（Impact/SKILL.md 落點）——避免實作者一開始就找錯檔。
3. 接著定 major #2（遷移語義）與 `--global-timeout` 設定入口，再進入 persona 模板與 runner 實作。
