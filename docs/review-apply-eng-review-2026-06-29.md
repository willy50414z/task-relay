# task-relay Review / Apply 工程審查報告

日期：2026-06-29

## 結論摘要

這個專案的 `review` 路線已經有明確產品形狀：有 `review-gate`、平行 reviewers、serial arbiters、JSON artifact 驗證、REVISE/REJECT gate、以及 revision readiness 檢查。`apply` 路線則還停在「一組很好的 primitives」：`pack`、`run --isolate`、worktree、empty-branch fail loud，但缺少與 `review-gate` 對稱的高階 orchestrator。

所以，如果問題是：

1. **能不能證明 task-relay 套到 OpenSpec propose/apply 後，token 消耗下降且推理精度不變？**
   目前**不能下這個結論**。可以證明的是「packer 有 scope selection 機制與小型 eval」，不能證明「端到端 reasoning quality 不退化」。
2. **要成為熱門開源工具還缺什麼？**
   最缺的是三件事：`doctor/preflight`、`apply` 高階產品化、以及可公開複製的 benchmark / case study。
3. **install 後的 preflight 與 UX 還能補什麼？**
   空間很大，尤其是 provider 健康檢查、模型可用性檢查、git/worktree 條件、managed block 衝突偵測、以及安裝後 smoke test。

## Findings

### 1. [P1] 目前沒有足夠證據支撐「token 降低且推理精度不變」這個產品主張

- 證據位置：
  - `task_relay/packer_eval.py:34-119`
  - `tests/fixtures/packer_eval.json:1-83`
- 現況：
  - `pack-metrics` 只評估 **packer scope selection**，指標是 `spec_precision`、`spec_recall`、`task_block_precision`、`task_block_recall`、`average_packet_bytes`。
  - fixture 只有 **4 個 example**，而且全部都來自同一個 change：`enhance-context-packer`。
  - 我實跑 `python -m task_relay.cli pack-metrics --eval-set tests/fixtures/packer_eval.json --json`，得到：
    - `sample_count = 4`
    - `spec_precision = 1.0`
    - `spec_recall = 1.0`
    - `task_block_precision = 1.0`
    - `task_block_recall = 1.0`
    - `average_packet_bytes = 10346.0`
- 問題：
  - 這只能證明「這 4 個標註案例中，packet 選得準」。
  - 它**沒有**比較 full-context baseline。
  - 它**沒有**衡量 downstream model 的最終 quality，例如 reviewer finding quality、apply patch 接受率、primary rework 率、最終 test pass rate。
  - 它**沒有**跨多 change、多 repo、多 task 類型做統計。
- 結論：
  - 可以說「這個 packer 很可能降低 token，且在小樣本標註集上 selection precision/recall 很高」。
  - **不能**說「套到 OpenSpec propose/apply 後，推理精度不變」。

### 2. [P1] `apply` 還沒有 productized 成與 `review-gate` 對稱的高階工作流

- 證據位置：
  - `task_relay/cli/__init__.py:141-159`
  - `task_relay/delegation.py:466-509`
- 現況：
  - CLI 有 `review` 與 `review-gate` 子命令。
  - 但沒有 `apply` / `apply-gate` / `apply-plan` 這種對稱入口。
  - 文件與 skill 生成內容目前仍要求 primary agent 手動執行：
    - `trly pack --mode implementation-draft ...`
    - `trly run --target <agent> --prompt-file <packet> --isolate --base <ref>`
- 影響：
  - `review` 是「產品」，`apply` 是「工具箱」。
  - 老手能用，第一次安裝的使用者不容易把整段流程走對。
  - 也因此較難做一致的 telemetry、benchmark、replay、UX 文案與故障恢復。
- 結論：
  - 如果目標是熱門開源工具，`apply` 需要一個對稱的高階入口，不然 adoption 會卡在「概念懂了，但不知道怎麼穩定用」。

### 3. [P1] `trly health` 目前會對 DeepSeek 產生假陽性，無法作為可靠 preflight

- 證據位置：
  - `task_relay/agents/deepseek.py:66-67`
  - `task_relay/cli/health.py:7-13`
- 現況：
  - `DeepSeekRunner.check()` 直接回傳 `TargetStatus(ok=True)`。
  - `trly health` 只是把 `check_target()` / `check_all()` 的結果印出來。
- 影響：
  - 使用者就算沒設 `DEEPSEEK_AUTH_TOKEN`、Claude bridge 不可用、模型不可達，也可能在 `health` 看到成功。
  - 安裝精靈或非互動 install 若依賴這個檢查，會把失敗延後到真正 `run()` 時才爆。
- 結論：
  - 這個問題直接打到你問的第 3 點：目前 preflight 還不夠真。

### 4. [P2] `run_review.py` 有重複定義，前段 zerotoken fallback 邏輯實際上被後段函式覆蓋

- 證據位置：
  - `task_relay/workflow/run_review.py:21-52`
  - `task_relay/workflow/run_review.py:72-93`
- 現況：
  - 同一個檔案中 `run_review()` 被定義了兩次。
  - 第一版包含 `_gateway_reachable()` 與 `_read_fallback_target()` 的 zerotoken fallback 邏輯。
  - 第二版再次定義 `run_review()`，把前面的版本覆蓋掉。
- 影響：
  - 讀碼的人會以為 zerotoken fallback 存在。
  - 實際執行時，那段 fallback 不會生效。
  - 這種「看起來有，實際沒有」的程式碼對 orchestration 專案很傷，因為除錯成本高。

### 5. [P2] 非互動 install 的錯誤提示仍指向舊旗標，會誤導第一次安裝的使用者

- 證據位置：
  - `task_relay/wizard.py:126-130`
  - `task_relay/cli/__init__.py:161-185`
- 現況：
  - wizard 的 `_non_interactive_message()` 仍提示使用 `--mode`、`--sub-agent`。
  - 但目前 install 主路徑已經是 `--feature`、`--reviewers`、`--apply-chain`、`--arbiter`。
- 影響：
  - 使用者一旦在非 TTY 場景踩到錯誤，收到的不是「正確補救方式」，而是半舊半新的 API。
  - 這會降低首次成功率，也會增加 issue / FAQ 負擔。

## 問題 1：這個設計是否能確實達成 token 降低且推理精度不變？

### 我的判定

**部分成立，但目前只成立到 packet selection 層，不成立到端到端質量層。**

### 已有的正面證據

- `trly pack` 不是整包 proposal 丟出去，而是會裁切：
  - task block
  - 相關 spec
  - 指定 design sections
  - 可選 repo references
- `pack-metrics` 已經有可量測框架，不是完全沒評估。
- 我本地跑到的數據，在目前 fixture 上 selection precision / recall 都是 1.0。

### 為什麼這還不夠

真正的產品主張其實是兩句話：

1. packet 變小
2. delegate 品質不變

目前只對第 1 句有間接證據，對第 2 句沒有。

因為 downstream quality 至少要量這些：

- review 流程：
  - reviewer finding precision / recall
  - arbiter 決策穩定度
  - primary 採納率
- apply 流程：
  - patch 接受率
  - primary rework 比例
  - test pass rate
  - empty-branch / invalid-output rate

### 我建議怎麼補成「可證明」

新增一個正式 benchmark matrix，至少包含：

- 對照組：
  - `full_change_context=True`
  - `packed_context`
- 樣本：
  - 至少 50 個 tasks
  - 至少 3 種 task 類型：review、implementation、test-draft
  - 至少 3 個 changes，不要全來自同一個 change
- 指標：
  - input tokens / output tokens
  - wall-clock time
  - review finding 採納率
  - apply branch 接受率
  - primary rework 次數
  - final test pass rate
- 判定標準：
  - token 降幅 >= 30%
  - 最終成功率差異在可接受範圍內，例如 <= 5%

### 這題的最終回答

如果你要我用工程經理口吻只給一句話：

**現在可以宣稱「我們有降低上下文體積的機制，而且 scope selection 小樣本準確」；還不能宣稱「OpenSpec propose/apply 端到端 token 降低且推理精度不變」。**

## 問題 2：如果要成為熱門開源工具，還需要補強什麼？

### 第一優先：把 `apply` 也產品化

目前最需要的是讓使用者從：

```bash
trly pack ...
trly run --isolate ...
```

升級成一個更完整的：

```bash
trly apply --change <change> --task <id>
```

它內部負責：

- packet generation
- isolated worktree
- output contract
- diff summary
- smoke verification
- accept / reject / retry

這會直接降低心智負擔，也更適合做 demo、錄影片、寫教學。

### 第二優先：補 `doctor/preflight`

熱門工具很少只靠 README 成功安裝。它們通常有一個一鍵自檢入口。

你現在最缺的不是更多功能，而是**更少安裝失敗的不確定性**。

### 第三優先：把 benchmark 做成 public artifact

如果你要在這條賽道建立信任，最有說服力的不是「概念上會省 token」，而是：

- benchmark 報告
- 可重跑資料集
- case study
- before / after packet size
- before / after review acceptance rate

這會比再加一個新 feature 更有傳播力。

### 第四優先：補 observability 與 replay 體驗

目前 `review` 已經有 artifact 與 result json，方向是對的。下一步應該是讓使用者更容易看：

- 這次叫了哪些 agent
- 哪裡 fallback
- 哪個 reviewer 提了哪些 finding
- arbiter 怎麼裁決
- apply branch 為什麼被接受 / 拒絕

這是目前同類工具很強的一塊。外部對照可參考：

- Quest：強調 dual-model review、arbiter、human gate  
  來源：<https://github.com/KjellKod/quest>
- Maestro：強調 auditable workflows、typed handoff、dashboard、replay  
  來源：<https://github.com/Xateh/maestro>
- Agent Orchestrator：強調 isolated workspaces、CI feedback loops、desktop/dashboard  
  來源：<https://github.com/AgentWrapper/agent-orchestrator>
- Delegate：強調 persistent teams、parallel tasks、benchmarks、frontend/e2e  
  來源：<https://github.com/nikhilgarg28/delegate>

### 第五優先：把「為什麼比別人好」講得更銳利

這個專案真正有機會打出差異化的不是「multi-agent」本身，而是：

1. **OpenSpec-aware packet packing**
2. **primary retains architectural authority**
3. **review gate + apply isolation**
4. **純 CLI、低基礎設施成本**

換句話說，對外敘事不要講「我們也能多 agent」，而是要講：

**我們把 delegation 做成低風險、低 token、可審計，而且能嵌進既有 CLI workflow。**

## 問題 3：install 完成 agent/model 後，有哪些 preflight 檢測與 UX 提升空間？

### 我會加一個 `trly doctor`

至少檢查這些：

#### Agent / model 層

- `claude` CLI 是否存在且已登入
- `codex` CLI 是否存在且已登入
- `deepseek` 是否有 `DEEPSEEK_AUTH_TOKEN`
- `zerotoken` gateway 是否可達
- 指定 model 是否仍在 catalog 中
- 指定 model 是否能做一次最小 dry-run

#### Repo / filesystem 層

- 是否在 git repo 中
- `git worktree` 是否可用
- project scope 下 `AGENTS.md` / `CLAUDE.md` 是否可寫
- `.codex/skills` / `.claude/skills` 是否可寫
- `openspec/changes/` 是否存在
- `spec/` 目錄是否存在或可建立

#### Config / policy 層

- user scope 與 project scope 是否同時有 managed block，且內容衝突
- `review` 啟用但沒有 reviewers
- `review` 啟用但 arbiters 空缺
- `apply` 啟用但 apply chain 空缺
- legacy block 是否可安全遷移

#### Runtime smoke test

- `trly pack --mode review-proposal --change <sample> --dry-run`
- `trly review-gate --change <sample> --verify-config`
- `trly run --target <agent> --prompt "write OK to file" --expect-output ...`
- `trly run --isolate` 的 noop smoke test

### install UX 可以直接提升的地方

#### 1. 安裝完成後立刻跑 smoke test

不是只說「Configuration written.」，而是：

- guidance block 寫好了
- skill bundle 寫好了
- health / doctor 結果
- 建議下一步命令

#### 2. 提供 profile presets

例如：

- `cheap`：單 reviewer + cheapest stable model
- `balanced`：單 reviewer + arbiter + apply isolate
- `strict`：雙 reviewer + arbiter + revision gate + apply isolate

這比新手自己配 chain 好很多。

#### 3. 顯示預估成本 / 延遲輪廓

在 install summary 直接顯示：

- review 大概會叫幾次模型
- apply 每 task 會開幾個 worktree
- 哪些會平行，哪些會序列

這會讓使用者更容易選擇 chain。

#### 4. 安裝後產生「下一步教學」

例如直接印：

```bash
trly review-gate --change <change>
trly pack --mode implementation-draft --change <change> --task 1.1 --out /tmp/1.1.md
trly run --target deepseek --prompt-file /tmp/1.1.md --isolate --base HEAD
```

#### 5. 更明確處理 managed block 衝突

如果 user scope 和 project scope 都裝了，而且內容不同，應直接警告：

- 哪個會覆蓋哪個
- 實際生效優先序
- 建議保留哪一份

## 我對這個專案的整體判斷

### 已經做對的地方

- review 路線有明確 gate，這很值錢
- apply isolation 用 git worktree，而不是口頭要求 delegate 自律
- packer 有朝「OpenSpec-aware scoped context」前進，方向是對的
- 測試覆蓋不錯，我本地實跑 `pytest -q`，**115 passed**

### 最該優先補的順序

1. `trly doctor` / 真 preflight
2. `apply` 高階 orchestration 命令
3. 端到端 benchmark，正式回答 token / quality 問題
4. observability / replay / summary UX
5. onboarding demo / preset profiles / install smoke test

## 建議的下一步

如果只做一輪最有價值的補強，我建議直接開一個 change，範圍只做三件事：

1. 新增 `trly doctor`
2. 修掉 `DeepSeekRunner.check()` 假陽性與 `run_review.py` 重複定義
3. 設計 `trly apply` 的最小版本，只先包：
   - packet generation
   - isolated run
   - empty-branch fail loud
   - diff summary

這一輪不需要碰太多產品野心，但會明顯提升真實可用性。

