# Review / Apply 功能文件

本文整理 `task-relay` 專案中與 delegated `review` / `apply` 相關的功能定位、CLI 入口、執行流程、輸出產物，以及主要程式碼位置，作為專案層級功能文件。

## 功能定位

`task-relay` 的 `review` 與 `apply` 是兩條不同階段的 delegation workflow：

- `review`：用在 OpenSpec 的 propose phase，目的是先審查 proposal / design / specs / tasks 是否清楚、方向正確、是否適合進入實作。
- `apply`：用在 OpenSpec 的 implementation phase，目的是針對單一 bounded task 打包 context、委派實作或測試草案，並在隔離 worktree 中產生可檢查的分支差異。

兩者的共同原則：

- primary agent 負責 orchestration、整合與最終驗證。
- delegated agent 不可修改 OpenSpec state、不可勾選 `tasks.md`、不可自行做架構 / 安全 / migration 決策。
- 所有委派都依賴 install 寫入的 managed block 與 skill bundle。

## CLI 入口

### Review

```bash
trly review --change <change>
trly review-gate --change <change>
```

- `trly review`
  - 輕量 wrapper。
  - 讀取 managed block 的 review 設定，必要時接受 `--target` / `--model` override。
  - 內部仍導向完整 review gate。
- `trly review-gate`
  - 正式 propose-phase review workflow。
  - 支援 reviewers、arbiter、global timeout、revision readiness verification。

常用旗標：

- `--change <change>`
- `--reviewers ...`
- `--arbiter ...`
- `--global-timeout <seconds>`
- `--review-profile lite|standard|qa|security|strict`
- `--arbiter-profile engineering|product|strict`
- `--verify-revision`
- `--json`

### Apply

```bash
trly apply --change <change> --task <task-id>
```

- 高階 apply orchestration。
- 會根據已安裝的 `apply-chain` 或明確傳入的 `--target/--targets` 決定委派目標。
- 內部整合 packet generation、isolated run、empty-branch fail-loud、diff summary 與可選 verification hook。

常用旗標：

- `--change <change>`
- `--task <task-id>`
- `--mode implementation-draft|test-draft`
- `--read <path>`
- `--diff-file <file>`
- `--diff-from <ref>`
- `--verify-cmd "<command>"`
- `--base <ref>`
- `--json`

### Supporting Commands

```bash
trly doctor
trly pack --mode review-proposal --change <change>
trly pack --mode implementation-draft --change <change> --task <task-id>
```

- `trly doctor`：安裝後 preflight / cheap validation，確認 token、CLI、model、managed block、scope、writable path 是否正常。
- `trly pack`：低階 packet 工具，讓 review/apply workflow 可以在 bounded context 下委派，而不是讓 delegate 冷啟動全 repo 探索。

`context-packer` 的設計評估與目前 contract，另見：[docs/context-packer-review.md](/home/willy/code/task-relay/docs/context-packer-review.md)。

## Review 流程

### 1. 載入設定

從 `AGENTS.md` 或 `CLAUDE.md` 的 managed block 讀取：

- reviewers：review execution fallback candidates；profile-based review 會先選一個有效 agent/model，再用它跑所有選中的 personas。
- arbiters：arbitration execution fallback candidates；只有 reducer 判斷需要 arbitration 時才會執行。
- global timeout
- legacy review-chain 相容設定

Reviewer profile 選 personas，不選 agent/model：

- `lite`：`/review`
- `standard`：`/review`, `/devils-advocate`
- `qa`：`/review`, `/devils-advocate`, `/qa-only`
- `security`：`/review`, `/devils-advocate`, `/cso`
- `strict`：`/review`, `/devils-advocate`, `/qa-only`, `/cso`

Arbiter profile 獨立選 arbitration personas：

- `engineering`：`/plan-eng-review`
- `product`：`/plan-ceo-review`
- `strict`：`/plan-eng-review`, `/plan-ceo-review`

### 2. 打包 review packet

每個 reviewer 會收到 `review-proposal` packet，內容來自 OpenSpec change artifacts，通常包含：

- `proposal.md`
- `design.md`
- 相關 `specs/**/*.md`
- `tasks.md`

### 3. 平行 reviewer persona 執行

profile-based review 會從 configured reviewers 選一個有效 review agent/model，並用同一個 agent/model 平行執行 profile 展開後的每個 reviewer persona。explicit `--reviewers` 仍是 manual override，會直接使用傳入的 concrete reviewer entries。

每個 persona 各自輸出 JSON artifact 到該 change 的 `review/` 目錄，例如：

- `openspec/changes/<change>/review/delegation_review_<reviewer-id>.json`

每份 reviewer artifact 至少需包含：

- `reviewer`
- `verdict`：`PASS`、`CONCERNS`、或 `BLOCKED`
- `summary`
- `findings`

一致性規則：`PASS` 必須是空 findings；`CONCERNS` / `BLOCKED` 必須有 finding 或 persona-specific concern fields；`/devils-advocate` 另需 `fatal_flaw`、`simpler_alternative`、`reverse_case`。delegates 可使用 `task_relay.review_artifacts.write_reviewer_artifact()` 產出穩定 JSON，但 gate 仍會自行驗證。

invalid reviewer artifact 會被 retry 一次。retry prompt 會包含 validation errors、required output path、schema rules、valid JSON example，且會透過正常 delegate job 執行，因此 correction request 會出現在 delegate log。第二次仍 invalid 時，該 reviewer persona 會被標記為 abandoned。

### 4. deterministic reducer 與 conditional arbiter

review gate 不再無條件執行 arbiter。它先用 mechanical reducer 判斷：

- 所有 required reviewer personas 都產出 valid `PASS`：直接 `APPROVE`，skip arbitration。
- 任一 valid reviewer 是 `CONCERNS` 或 `BLOCKED`：執行 selected arbiter profile。
- 有 abandoned reviewer 且仍有 valid reviewer：執行 selected arbiter profile，並把 abandoned metadata 傳給 arbiter。
- 所有 reviewers 都 abandoned：gate 失敗，不 approve、不 arbitrate。

arbiter 依序讀取 reviewer artifacts、abandoned metadata、prior arbiter JSON，輸出 decision JSON，例如：

- `openspec/changes/<change>/review/delegation_arbiter_<stage-id>.json`

decision 類型：

- `APPROVE`
- `REVISE`
- `REJECT`

### 5. gate 結果輸出

review gate 會產生：

- 人類可讀摘要：`openspec/changes/<change>/review/delegation_review.md`
- machine-readable 結果：review result JSON

`trly review-gate` 的 exit semantics：

- `APPROVE`：可進入 apply
- `REVISE`：primary agent 先依 arbiter contract 修 proposal / design / tasks
- `REJECT`：停止後續 apply

## Apply 流程

### 1. 解析 apply target

`trly apply` 會依優先順序選擇 apply target：

1. `--target` / `--targets`
2. managed block 中的 `apply-chain`

若完全沒有可用 target，命令會直接失敗。

### 2. 打包 bounded task packet

`trly apply` 透過 packer 產生：

- `implementation-draft`
- 或 `test-draft`

packet 會盡量只帶：

- 目標 task block
- 關聯 spec
- `design.md` 的關鍵段落
- 額外指定的 repo files
- 可選的 diff-based dynamic context

目前 `trly pack` / `plan_packet()` 也會提供：

- semantic model fallback，可實際補上 design sections、task dependencies、extra reads
- byte-based hard budget
- deterministic trimming diagnostics
- machine-readable budget violation / model selection rejection

### 3. isolated delegation

委派透過 `run_isolated` 執行：

- 在臨時 git worktree 中建立 throwaway branch
- delegate 只修改隔離 worktree
- 空分支視為失敗
- 主工作樹不直接被 delegate 汙染

### 4. diff summary

執行完成後，primary 會對 delegated branch 與 base 做 `git diff --stat`，提供摘要輸出，方便決定是否接受整合。

### 5. optional verification

若指定 `--verify-cmd`，會再從 delegated branch 建立驗證 worktree，執行指令並回報：

- `ok`
- `returncode`
- `detail`

### 6. OpenSpec state 仍由 primary 控制

`trly apply` 本身不會修改 OpenSpec `tasks.md` checkbox。任務是否完成，必須由 primary agent 在整合與驗證後再更新。

## 產物與檔案輸出

### Review 產物

- `openspec/changes/<change>/review/delegation_review.md`
- `openspec/changes/<change>/review/delegation_review_<reviewer-id>.json`
- `openspec/changes/<change>/review/delegation_arbiter_<stage-id>.json`
- review result JSON，包含 reviewer profile、arbiter profile、selected personas、selected review agent、reducer decision、retry attempts、abandoned reviewers、arbiter invocation state、skip reason

### Apply 產物

- delegated throwaway branch
- branch diff summary
- optional verification result JSON payload
- `trly pack --dry-run --json` / `pack-benchmark` / `pack-lint` 的 machine-readable diagnostics

### Install / Preflight 關聯產物

- `AGENTS.md` / `CLAUDE.md` managed block
- skill bundle：`.codex/skills/task-relay-delegation/` 或 `.claude/skills/task-relay-delegation/`

## 主要程式碼位置

### CLI 入口

- `task_relay/cli/__init__.py`
  - 定義 `review`、`review-gate`、`apply`、`doctor`、`pack` 等子命令
- `task_relay/cli/apply.py`
  - `trly apply` 主入口
- `task_relay/cli/doctor.py`
  - `trly doctor` 主入口

### Review orchestration

- `task_relay/workflow/review_gate.py`
  - review gate 主流程
  - reviewer / arbiter subprocess orchestration
  - artifact validation
  - summary / result 輸出
- `task_relay/workflow/run_review.py`
  - `trly review` 的簡化 wrapper

### Apply orchestration

- `task_relay/cli/apply.py`
  - apply target 解析
  - `run_isolated` 呼叫
  - diff summary
  - verification hook
- `task_relay/worktree.py`
  - isolated worktree lifecycle
- `task_relay/core.py`
  - agent run 與 isolated execution primitive

### Packet 與模板

- `task_relay/packer.py`
  - packet 組裝與 bounded context selection
- `task_relay/assets/task-relay-delegation/templates/review-proposal.md`
  - reviewer packet template
- `task_relay/assets/task-relay-delegation/templates/review-arbiter.md`
  - arbiter packet template
- `task_relay/assets/task-relay-delegation/templates/implementation-draft.md`
  - implementation apply template
- `task_relay/assets/task-relay-delegation/templates/test-draft.md`
  - test drafting template

### 設定與安裝

- `task_relay/delegation.py`
  - managed block 解析 / 生成
  - skill bundle 安裝
  - generated guidance text
- `task_relay/review_config.py`
  - reviewers / arbiters 設定模型
- `task_relay/doctor.py`
  - install 後 preflight checks

### Benchmark 與評估

- `task_relay/packer_eval.py`
  - pack metrics
  - packed vs full context benchmark

## 主要測試位置

- `tests/test_review_gate.py`
  - review gate orchestration、timeout、artifact handling
- `tests/test_run_review_wrapper.py`
  - `trly review` wrapper 路徑
- `tests/test_apply.py`
  - `trly apply` target resolution、diff summary、verification
- `tests/test_doctor.py`
  - preflight / validation 行為
- `tests/test_packer.py`
  - packet selection 與 benchmark report

## 建議閱讀順序

如果要快速理解功能，建議依序閱讀：

1. `docs/install.md`
2. `task_relay/cli/__init__.py`
3. `task_relay/workflow/review_gate.py`
4. `task_relay/cli/apply.py`
5. `task_relay/packer.py`
6. `task_relay/delegation.py`

## 相關文件

- [安裝與設定指南](./install.md)
- [Context Packer Review](./context-packer-review.md)
- [review/apply 工程審查紀錄（2026-06-29）](./review-apply-eng-review-2026-06-29.md)
