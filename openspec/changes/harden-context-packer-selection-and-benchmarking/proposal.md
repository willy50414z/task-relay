## Why

`context-packer` 已經能把 OpenSpec change 壓縮成 bounded packet，但目前還不能可信地證明「實際 token 成本下降且 downstream quality 不退化」。此外，model fallback 的對外 contract、packet 預算控制與 benchmark 指標之間仍有落差，會讓 packer 在 repo 變大或需求變模糊時重新失控。

## What Changes

- 讓 context-packer 的 model fallback contract 與實際 packet assembly 行為一致，避免只挑 spec 卻假裝支援更完整的 semantic assembly。
- 為 packet assembly 新增可檢查的預算控制與 deterministic trimming，避免 `extra_reads`、dynamic diff 與 full fallback 導致 packet 無上限膨脹。
- 擴充 benchmark / eval 報告，加入實際 token、成本與 downstream quality proxy，讓 packed-vs-full 比較不再只停在 byte estimate。
- 強化 pack-lint / diagnostics，讓高風險 fallback、sidecar 格式陷阱與 context gap 更早暴露。

## Capabilities

### New Capabilities
- `context-packer-semantic-assembly`: 定義既有 model fallback 行為如何從「只影響 spec selection」修正為一致地組裝 task dependencies、design sections 與 repo context 進 packet。
- `context-packer-budgeting`: 定義 packet 預算、trimming 順序與超限時的可觀測輸出。
- `context-packer-benchmarking`: 定義 packed-vs-full benchmark 的 token、成本與品質代理指標。

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `task_relay/packer.py`
  - `task_relay/packer_eval.py`
  - `task_relay/cli/pack.py`
  - `tests/test_packer.py`
- 影響 `trly pack`、`trly pack-lint`、`trly pack-metrics`、`trly pack-benchmark` 的輸出契約。
- 影響未來對 context-packer「降低 token 且不傷品質」的產品敘述與驗證方式。
