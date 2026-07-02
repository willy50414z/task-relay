## 1. Diagnostics Schema And Runtime Wiring

- [ ] 1.1 [codex-only] Define the runtime diagnostics schema and ownership boundary. Context: `openspec/changes/harden-runtime-observability-timeouts/design.md`, `specs/delegation-runtime-observability/spec.md`, `task_relay/jobs.py`, `task_relay/types.py`. Output: schema constants/dataclasses or helper functions for diagnostics path, schema version, timeout policy summary, activity summary, semantic contract summary, and resume summary.
- [ ] 1.2 [delegate:deepseek] Implement per-job diagnostics artifact creation for managed jobs. Context: `task_relay/jobs.py`, `tests/test_jobs.py`. Required behavior: create/link `diagnostics.json`, keep `meta.json` lightweight, record diagnostics write failures without masking the underlying job status.
- [ ] 1.3 [delegate:test] Add job diagnostics tests. Context: `tests/test_jobs.py`, `specs/delegation-runtime-observability/spec.md`. Cover blocking success, expected-output failure, timeout, and `trly jobs status` exposing diagnostics path.

## 2. Context-Packer Observability

- [ ] 2.1 [delegate:deepseek] Complete apply-time context-packer report persistence. Context: `task_relay/cli/apply.py`, `task_relay/packer.py`, `tests/test_apply.py`, `tests/test_packer.py`. Required behavior: write machine-readable packer report before delegate start, include packet hash, link report path from apply debug summary and job diagnostics.
- [ ] 2.2 [delegate:deepseek] Add review-gate context-packer report persistence. Context: `task_relay/workflow/review_gate.py`, `task_relay/packer.py`, `tests/test_review_gate.py`. Required behavior: reviewer and arbiter packet builds write per-stage packer report artifacts and link them to job diagnostics.
- [ ] 2.3 [delegate:test] Add context-packer observability tests. Context: `tests/test_apply.py`, `tests/test_review_gate.py`, `tests/test_packer.py`. Cover normal report fields, missing signals warning, repo context gap warning, trimmed sections warning/failure, cache-layout byte counts, and packet hash stability.

## 3. Timeout Handler State Machine

- [ ] 3.1 [codex-only] Introduce timeout policy data model without breaking current CLI semantics. Context: `task_relay/jobs.py`, `task_relay/types.py`, `task_relay/cli/__init__.py`, `specs/delegation-timeout-handling/spec.md`. Decision: existing `timeout` remains hard cap; soft deadline fields are optional internal policy first.
- [ ] 3.2 [delegate:deepseek] Track stdout, stderr, expected-output, and aggregate activity timestamps separately. Context: `task_relay/jobs.py`, `tests/test_jobs.py`. Required behavior: diagnostics can distinguish last stdout, last stderr, last expected-output, and last activity source.
- [ ] 3.3 [delegate:deepseek] Implement foreground soft deadline handling inside hard timeout. Context: `task_relay/jobs.py`, `tests/test_jobs.py`. Required behavior: soft deadline can extend when recent activity exists, extension is bounded by hard timeout and max extension policy, hard timeout is never extended.
- [ ] 3.4 [delegate:deepseek] Record observable termination events. Context: `task_relay/jobs.py`, `tests/test_jobs.py`. Required behavior: pre-kill liveness, pid/pgid, timeout reason, SIGTERM timestamp, grace wait, SIGKILL timestamp when needed, and final liveness are recorded for timeout and explicit stop.
- [ ] 3.5 [delegate:deepseek] Add role-aware timeout policy selection. Context: `task_relay/core.py`, `task_relay/cli/apply.py`, `task_relay/workflow/review_gate.py`, `task_relay/review_config.py`. Required behavior: DeepSeek apply defaults to hard timeout >=1800s, DeepSeek review subprocesses default to hard timeout >=900s, review gate global default is >=2400s, user override is honored and marked.
- [ ] 3.6 [delegate:test] Add timeout state-machine tests. Context: `tests/test_jobs.py`, `tests/test_apply.py`, `tests/test_review_gate.py`. Cover no kill when process already exited, extension with recent activity, no extension at hard cap, stalled-but-not-killed by default, graceful then forceful termination events, and user override metadata.

## 4. Semantic Contract Status

- [ ] 4.1 [codex-only] Define process status vs contract status mapping. Context: `task_relay/jobs.py`, `task_relay/errors.py`, `task_relay/workflow/review_gate.py`, `specs/delegation-runtime-observability/spec.md`. Output: final status rules for process exit, expected-output validation, JSON/schema validation, interactive-output detection, timeout, killed, and quota.
- [ ] 4.2 [delegate:deepseek] Persist semantic contract status in job diagnostics and trace records. Context: `task_relay/jobs.py`, `task_relay/core.py`, `task_relay/trace.py`, `tests/test_output_verification.py`, `tests/test_trace.py`. Required behavior: process exit 0 with missing/empty output is failed with contract reason, not succeeded.
- [ ] 4.3 [delegate:deepseek] Improve review-gate semantic failure reporting. Context: `task_relay/workflow/review_gate.py`, `tests/test_review_gate.py`. Required behavior: invalid reviewer/arbiter JSON and schema failures include artifact path, validation reason, job id, log path, and expected output path.
- [ ] 4.4 [delegate:test] Add semantic contract tests. Context: `tests/test_output_verification.py`, `tests/test_review_gate.py`, `tests/test_trace.py`. Cover missing expected output, empty output, invalid JSON, schema-invalid JSON, and interactive stdout with no artifact.

## 5. Parent Quota Resumability

- [ ] 5.1 [codex-only] Define resumable parent failure contract. Context: `task_relay/agents/common.py`, `task_relay/core.py`, `task_relay/trace.py`, `tests/test_quota.py`, `specs/delegation-runtime-observability/spec.md`. Output: failure kinds, resume metadata path, retry-after parsing semantics, and parent-vs-delegate attribution rules.
- [ ] 5.2 [delegate:deepseek] Implement parent quota resume metadata. Context: `task_relay/agents/common.py`, `task_relay/core.py`, `task_relay/jobs.py`, `tests/test_quota.py`. Required behavior: Codex/OpenAI usage-limit failures are classified as `parent_quota_exhausted` when in parent orchestration context and write target/model/job/log/workflow context plus suggested resume action.
- [ ] 5.3 [delegate:test] Add quota resumability tests. Context: `tests/test_quota.py`, `tests/test_trace.py`. Cover hard quota classification, usage-limit text with next-available hint, resume metadata write, trace failure kind, and ensuring DeepSeek delegate failures are not mislabeled as parent quota.

## 6. CLI, Trace, And Documentation Surface

- [ ] 6.1 [delegate:deepseek] Surface diagnostics in `trly jobs status` and `trly trace --summary`. Context: `task_relay/cli/jobs.py`, `task_relay/cli/trace.py`, `task_relay/jobs.py`, `task_relay/trace.py`. Required behavior: status shows diagnostics path, hard timeout, soft deadline when configured, stall window, last activity, timeout source; trace summary groups timeout/semantic/quota failure kinds.
- [ ] 6.2 [delegate:deepseek] Update user-facing docs and delegation templates. Context: `README.md`, `docs/`, `task_relay/assets/task-relay-delegation/templates/*.md`. Required behavior: document how to inspect context-packer reports, timeout decisions, semantic failures, and resume metadata; review packets must say do not ask interactive questions when an output artifact is required.
- [ ] 6.3 [delegate:test] Add end-to-end CLI tests for observability surfaces. Context: `tests/test_jobs.py`, `tests/test_trace.py`, `tests/test_apply.py`, `tests/test_review_gate.py`. Cover `jobs status`, debug summary path, packer report path, trace failure kind summary, and review expected-output diagnostics.

## 7. Integration Verification

- [ ] 7.1 [codex-only] Run focused unit tests: `python3 -m unittest tests.test_jobs tests.test_apply tests.test_review_gate tests.test_output_verification tests.test_quota tests.test_trace -v`.
- [ ] 7.2 [codex-only] Run full test suite: `python3 -m unittest discover -s tests -v`.
- [ ] 7.3 [codex-only] Run an offline smoke test with fake delegate commands or mocked runners proving diagnostics are written before timeout/semantic failure handling.
- [ ] 7.4 [codex-only] Manually inspect one generated `diagnostics.json`, one context-packer report JSON, one apply debug summary, and one trace record to confirm job id/log/report links line up.
