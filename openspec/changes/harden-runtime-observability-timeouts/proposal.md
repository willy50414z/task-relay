## Why

近幾輪 Task Relay 自動化執行顯示，delegate 本身能完成高價值工作，但 orchestration 失敗難以診斷：DeepSeek error 高度集中在過短 timeout 批次，Codex parent usage limit 會中斷整個 flow，而部分 delegate process 成功退出卻輸出互動式提問，對 pipeline 語義上不可用。

現在需要把「能不能跑」升級成「能看懂為什麼跑、何時該停、停之前知道 process 是否仍有進展」。否則下一輪 autopilot 仍會把 timeout、context-packer 範圍、semantic output contract、quota interruption 混成同一種失敗。

## What Changes

- 新增 runtime 可觀測性契約，讓 apply/review/autopilot 相關執行都能回溯 context-packer 是否正常選取上下文、delegate job 使用了哪些 timeout、最後輸出活動何時發生、失敗是否可恢復。
- 新增 context-packer diagnostics artifact，將 `selection_mode`、byte budget、trim result、missing signals、repo context gaps、cache layout byte counts、selected sections/references 寫入可機器讀取和人可讀的 debug summary。
- 新增 timeout handler 行為，區分 hard timeout、idle/stall timeout、graceful terminate、force kill；在終止前記錄 process liveness、last output、expected output activity、timeout reason。
- 讓 foreground delegate timeout 不再只是「時間到就殺」的黑盒；若仍有近期輸出，系統可在 hard cap 內延長 soft deadline，並把延長原因寫入 job metadata/log。
- 讓 Codex parent usage limit / quota 類 failure 產生 resumable failure metadata，而不是只讓 parent flow 中斷。
- 強化 review/apply output contract 可觀測性：process exit 0 但缺少 expected output、JSON schema 不符、輸出互動式提問時，應在 diagnostics 中標記為 semantic failure。

## Capabilities

### New Capabilities

- `delegation-runtime-observability`: delegate runtime、context-packer、quota、semantic output、resume state 的統一診斷與 trace 能力。
- `delegation-timeout-handling`: hard timeout、idle/stall timeout、process liveness check、soft extension、graceful/force termination 的可預期 timeout 行為。

### Modified Capabilities

無。此 repo 目前沒有已歸檔的 `openspec/specs/` capability；本 change 以新的 delta specs 定義下一階段契約。

## Impact

- Affected code:
  - `task_relay/jobs.py`: job metadata、last-output tracking、timeout loop、terminate/kill event recording。
  - `task_relay/core.py`: trace outcome、quota/usage-limit classification、resumable parent failure metadata。
  - `task_relay/cli/apply.py`: apply debug summary、context-packer observation、delegate job context。
  - `task_relay/workflow/review_gate.py`: review/arbiter expected-output diagnostics、semantic artifact validation reporting。
  - `task_relay/packer.py`: `PacketPlan.to_report()` fields consumed by runtime diagnostics。
  - `task_relay/trace.py` and `task_relay/cli/trace.py`: optional enrichment with timeout reason, job id, packer report path, resumability fields.
- Affected artifacts:
  - `.task_relay/jobs/<job-id>/meta.json`
  - `.task_relay/jobs/<job-id>/combined.log`
  - `.task_relay/trace.jsonl`
  - `openspec/changes/<change>/apply/task-<task-id>-debug-summary.md`
  - optional machine-readable debug JSON next to the markdown summary.
- No breaking CLI change is intended. Existing `trly run`, `trly apply`, `trly review`, `trly jobs`, and `trly trace` commands should keep their current entry points while gaining clearer diagnostics.
