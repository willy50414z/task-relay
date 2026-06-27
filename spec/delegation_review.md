# Delegation Review — `enhance-context-packer` 提案審查

- 模式：`review-proposal`
- 審查目標：需求清晰度、方向正確性、實作計畫完整度（客觀視角）
- 審查範圍：`proposal.md` / `design.md` / `tasks.md` + 既有實作 `task_relay/packer.py`、`task_relay/trace.py`、baseline `harden-delegation-runtime`
- 結論摘要：**方向合理、可批准進入實作，但需先收斂數個會卡住 P0/P1/P3 的開放問題與兩處方向性張力。** 沒有發現 blocker，但有數個 major 需在動工前澄清。

---

## 整體評價（正面）

- **P0 先行（measurement-gates-work）的排序是正確且有紀律的**，沿用 observability「沒有量測就沒有宣稱」的原則，避免後續 P1–P3 自說自話。
- **方向與來源文件一致**：`context-packer-enhance.md` 的五點建議被忠實拆成 P0–P3，且保留「模型只做受限 scope resolver、不產生最終 packet」的核心約束。
- **依賴宣告正確**：已確認 `openspec/specs/` 為空（提案宣稱「無 base spec 可改」屬實），baseline 的 `delegation-observability` 能力確實存在，DeepSeek 透過 claude CLI `--output-format json` 執行（`agents/deepseek.py:41`），`trace.py` 已能彙整 token/cost，因此 P3「以 observability trace 量測 resolver 成本」在技術上可行。
- **point-to 預設（D3）方向正確**：delegate 跑在含完整 repo 的 worktree，預設引用而非 inline 可避免重蹈 C4 修掉的 packet 膨脹。

---

## Findings

### [major] F1 — P3 cross-check 規則可能抵銷模型本身的價值
- **問題描述**：design D4 / spec `packer-model-resolution` 規定模型結果要「cross-check against the token-overlap top candidates」才接受，且「untrustworthy → 退回保守 all-specs」。但若驗收規則是「模型選擇必須落在 deterministic top candidates 內」，那麼在 deterministic 本來就無法唯一決定（正是觸發模型的前提）的情境下，模型只能在 deterministic 已並列的候選中二選一；一旦模型選了 deterministic 排名外但實際正確的 spec，反而會被拒絕。換言之 cross-check 可能讓模型「只能確認、無法補正」，使 P3 的淨價值趨近於零。
- **影響範圍**：P3 全部（tasks 4.2–4.4、spec「Cross-check against deterministic candidates」場景），直接決定 P3 是否值得做。
- **建議方向**：明確定義 cross-check 是「硬性過濾（must be in top-N）」還是「軟性加權 / 平手裁決」。建議改為：模型可從**完整候選集合**（而非僅 deterministic top-N）中選，cross-check 僅用於偵測明顯離群（例如選了 token overlap 為 0 的 spec 才拒絕），保留模型補正空間。請使用者裁示驗收語意。

### [major] F2 — 「target fallback-rate ceiling」把量測指標與強制機制混為一談
- **問題描述**：proposal/design 多次稱「a target fallback rate bounds how often the model fires」，task 4.5 要求「enforce a target fallback-rate ceiling」。但 fallback rate 是**輸入（artifact 品質）決定的觀測量**，不是可由程式直接「enforce」的旋鈕——你無法在不改 artifact 的前提下強制 deterministic 少失敗。task 4.5 的「enforce」缺乏可操作定義（是超標就報警？是禁止模型在超過比例時被呼叫？是 CI gate？）。
- **影響範圍**：task 4.5、P3 驗收標準、close-out 5.1。
- **建議方向**：拆成兩件事——(a) fallback rate 作為 P0 指標**監測並回報**；(b) 若要對模型呼叫頻率設上限，需另定義具體 enforcement（例如「單次 apply session 內 model resolver 呼叫數上限」或「超過比例時 dry-run 標記 warning 但不阻擋」）。請使用者選定語意。

### [major] F3 — 顯式訊號落點（OQ2）未決，卻是 ecosystem 級慣例變更
- **問題描述**：design Open Question 2（訊號放 `tasks.md` inline vs sidecar、`openspec validate` 如何對待）被 task 2.1 直接延後到實作期決定。但這是會影響所有 OpenSpec 作者的**撰寫慣例變更**（proposal「Impact」自承為 ecosystem-level convention change），落點選擇會反向決定 packer 的解析實作、pack-lint 的驗證面、以及與 `openspec validate` 的整合方式。在此未決前，P1 的 2.2/2.4 難以給出穩定設計。
- **影響範圍**：P1 全部（2.1–2.5）、pack-lint 介面、與既有 OpenSpec 工具鏈的相容性。
- **建議方向**：在動工 P1 前先收斂落點。建議優先評估 sidecar（例如 `packer.yml` / `signals.md`）以免污染人類可讀的 `tasks.md` 並避開 `openspec validate` schema 衝突，但此屬慣例決策，**應由使用者裁定**而非實作者自行決定。

### [major] F4 — 評估集的客觀性與循環性風險未處理
- **問題描述**：P0 的可信度完全建立在 labeled eval set 上，但 task 1.2 僅說「start with the existing changes' tasks」。由同一群人、針對自家既有 change 標註「expected scope」，且標註者與選擇規則設計者重疊時，存在**過擬合 / 循環論證**風險：指標可能只是反映規則作者的直覺，而非客觀準確率。design 也未說明 ground-truth「expected scope」由誰、依何準則標註，以及樣本量是否足以支撐 precision/recall 宣稱。
- **影響範圍**：P0（1.1–1.4）、以及所有「P1–P3 提升準確率」宣稱（close-out 5.1）的可信度。
- **建議方向**：明確定義 (a) 誰標註 ground-truth、依據什麼準則；(b) 最小樣本量與多樣性要求；(c) 是否需與規則設計者分離以避免循環。至少在 design 補一段標註方法論。

### [minor] F5 — 指標的「section 級」precision/recall 標註主觀性高
- **問題描述**：指標要求計算「selected specs **and sections**」的 precision/recall。spec 與 task block 的相關性相對客觀，但「哪些 `design.md` section 算相關」高度主觀，難以產生穩定 ground-truth，會讓 section 級指標噪音大。
- **影響範圍**：task 1.1、1.5。
- **建議方向**：考慮先以 spec/task-block 級指標為主指標，section 級降為輔助觀測或先不納入準確率分數；或明確定義 section 相關性的標註規則。

### [minor] F6 — cache key `(task, artifact-hash)` 的 artifact 範圍未界定
- **問題描述**：P3 以 `(task, artifact-hash)` 快取以求可重現，但「artifact-hash」涵蓋哪些檔案未定義。若僅含 OpenSpec artifact，而 P2 的動態 change-branch diff（repo 檔案）變動時，repo-file 候選會與快取不一致而 stale。
- **影響範圍**：task 4.4，與 P2（3.3 動態 diff scope）的交互。
- **建議方向**：明確列出 hash 涵蓋集合；若 resolver 結果含 repo-file 候選，hash 應納入相關 repo 檔案 / diff 指紋。

### [minor] F7 — pack-lint 的執行點與「是否 gating」未定義
- **問題描述**：pack-lint 定位為「post-propose 診斷檢查」，task 2.4 說「CLI + module」，但未定義它在委派流程中的觸發點（獨立 `trly pack-lint`？併入某既有指令？），以及它是純諮詢還是會在委派前阻擋。spec 已明確「diagnostic only、不改 artifact」，但「不阻擋委派」與「diagnostic only」不是同一件事，建議分清。
- **影響範圍**：task 2.4、與委派主流程（`delegation.py` managed-block workflow）的銜接。
- **建議方向**：在 design 補一句 pack-lint 的呼叫點與 advisory/gating 定位。

### [minor] F8 — 動態 test-mode scope 與 baseline worktree/change-branch 模型的依賴未顯式化
- **問題描述**：P2 的「change-branch diff」直接依賴 baseline `harden-delegation-runtime` 的 task 7（change-level integration worktree、`tr/<task-id>` / `chg/<change>` 分支模型）。design Open Question 4（diff 由 `--base` 參數傳入 vs 讀取 active change branch）未決，且未說明如何取得「本次 apply session 在 change branch 上產生的 diff」。
- **影響範圍**：task 3.3、與 baseline task 7 的耦合。
- **建議方向**：在 design 明確指出依賴 baseline 的哪個分支模型來界定「change-branch diff」，並先收斂 OQ4 的取得方式。

### [minor] F9 — baseline 尚未 archive，前置條件需實際驗證
- **問題描述**：`harden-delegation-runtime` 仍在 `openspec/changes/`（無 `archive/`），其 tasks 仍有 8.6a、8.8 未勾選（雖標示為 deferred / 另案）。實作所依賴的 `packer.py`、`trace.py` 已存在於工作樹，故依賴**實質可滿足**，但 task 0.1 的「confirm harden has landed」應落實為明確驗證（依賴的是 C4 packer + observability trace，而非 8.6a/8.8）。
- **影響範圍**：prerequisite 0.1。
- **建議方向**：把 0.1 的「landed」明確界定為「C4（4.x）+ observability（8.1–8.7）已完成」，與 deferred 項目脫鉤。

---

## 待使用者裁示的問題（不自行決定）

1. **F1**：P3 cross-check 是硬性過濾還是軟性裁決？這決定 P3 是否具備淨價值。
2. **F2**：fallback-rate「enforce」的具體語意（報警 / 阻擋 / 呼叫上限）？
3. **F3**：顯式訊號落點（inline vs sidecar）——屬撰寫慣例決策。
4. **F4**：eval set 的 ground-truth 標註方法與是否需與規則設計者分離。

## 建議的先決順序（不修改 tasks.md，僅建議）

- 動工前先回答 F3、F4（影響 P0/P1 的可驗證性與慣例面），再開 P0。
- F1、F2 可在進入 P3 前收斂，不阻擋 P0–P2。

---

> 本報告僅為診斷輸出，未修改 `proposal.md` / `design.md` / `tasks.md`、未變更 OpenSpec 狀態、未勾選任何 checkbox。
