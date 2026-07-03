# Implementation Notes

Last updated: 2026-07-03

## Current State

Most implementation and focused test coverage for `enhance-review-profile-arbitration` is in place, but final verification is not complete. Task `7.2` is intentionally left unchecked because the final focused test rerun after the last small code/test edits was interrupted by the user.

Implemented areas:

- `task_relay/review_config.py`
  - Added reviewer profiles: `lite`, `standard`, `qa`, `security`, `strict`.
  - Added arbiter profiles: `engineering`, `product`, `strict`.
  - Added `/devils-advocate` persona aliases.
  - Added profile normalization and persona expansion helpers.
  - Added `ReviewGateConfig.review_profile`, `arbiter_profile`, `profile_source`, and `arbiter_source`.

- `task_relay/review_artifacts.py`
  - Added canonical JSON load, validate, and stable writer helpers.
  - Enforces `PASS` empty findings, `CONCERNS` / `BLOCKED` finding or persona concern fields, and `/devils-advocate` fields: `fatal_flaw`, `simpler_alternative`, `reverse_case`.
  - Enforces arbiter schema and `REVISE` actionable item requirements.

- `task_relay/workflow/review_gate.py`
  - Expands reviewer profiles into persona-specific jobs using one selected reviewer fallback agent/model.
  - Runs reviewer jobs in parallel via existing `asyncio.gather` path.
  - Retries invalid reviewer artifacts once with validation errors, output path, schema rules, and a valid JSON example in the retry prompt.
  - Marks reviewer personas abandoned after failed retry.
  - Fails the gate if all reviewer personas are abandoned.
  - Uses a deterministic reducer: all valid PASS with no abandoned reviewers approves and skips arbitration; `CONCERNS`, `BLOCKED`, or abandoned metadata triggers arbitration.
  - Passes abandoned reviewer metadata into arbiter packets.
  - Expands arbiter profiles only when arbitration is required, preserving serial arbiter behavior.
  - Writes review result and summary metadata for profiles, selected personas, selected review agent, reducer decision, arbiter invocation/skip reason, retry attempts, and abandoned reviewers.
  - Added guard: `arbiter_source == "manual_override"` requires at least one arbiter entry.

- `task_relay/cli/__init__.py`
  - Added `--review-profile` and `--arbiter-profile` to `trly review` and `trly review-gate`.
  - Preserves explicit `--reviewers` as manual reviewer override.
  - Preserves explicit `--arbiter` as conditional manual arbiter override.

- Assets, docs, and guidance
  - Added `task_relay/assets/task-relay-delegation/personas/reviewer-devils-advocate.md`.
  - Updated review proposal and arbiter packet templates.
  - Updated arbiter persona guidance for `CONCERNS`, `BLOCKED`, abandoned reviewer metadata, and risk-weighted arbitration.
  - Updated `docs/review-apply.md` for profiles, fallback review agents, PASS-only reducer, conditional arbitration, invalid artifact retry, and helper-based artifact output.
  - Updated generated review skill guidance in `task_relay/delegation.py`.

- Tests
  - Added `tests/test_review_profiles.py` for profile expansion and canonical artifact validation/writing.
  - Added `tests/test_review_gate_profiles.py` for profile expansion, selected review agent fallback, CLI flags, deterministic reducer, conditional arbitration, invalid retry/abandon behavior, retry prompt contents, metadata output, and explicit override compatibility.

## Verification Already Run

Passed after the current code shape except where noted:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m py_compile task_relay\review_config.py task_relay\review_artifacts.py task_relay\cli\__init__.py task_relay\workflow\review_gate.py task_relay\delegation.py
```

Result: passed.

```powershell
git diff --check
```

Result: passed, with only Git line-ending warnings about LF being converted to CRLF next time Git touches those files.

Focused tests previously passed before the last small edit that added explicit retry schema-rule text and the manual-arbiter guard:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest tests\test_review_profiles.py tests\test_review_gate_profiles.py -q --basetemp .pytest-tmp
```

Result at that point: `21 passed in 0.12s`.

After the final small edit, the focused test rerun was started but interrupted by the user before completion. Rerun it next and only then mark task `7.2` complete.

## Full Suite Status

Full suite was attempted with:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest-tmp
```

It failed during collection on `tests/test_wizard.py` because the test imports old wizard symbols such as `VALID_MODES`, while current `task_relay/wizard.py` uses the newer features/reviewers/apply_chain state model.

A second run excluding wizard:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest tests -q --ignore tests\test_wizard.py --basetemp .pytest-tmp
```

Result: `64 passed`, `18 failed`. The failures are concentrated in legacy install/delegation tests expecting old `mode`, `sub-agent`, and `models` APIs/signatures. This appears pre-existing relative to the review-profile change, but task `7.3` should stay unchecked until the project decides whether to update those legacy tests or treat them as out of scope for this change.

## Next Session Checklist

1. Rerun focused tests after the final small edit:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m pytest tests\test_review_profiles.py tests\test_review_gate_profiles.py -q --basetemp .pytest-tmp
```

Use escalated execution if Windows sandbox blocks pytest tmp directory creation.

2. If focused tests pass, mark task `7.2` complete.

3. Review the diff for architecture/backward compatibility and mark `7.1` only after checking:
   - profile-based runs with configured reviewers,
   - explicit `--reviewers` bypass behavior,
   - explicit `--arbiter` conditional behavior,
   - review result metadata shape,
   - retry/abandoned semantics.

4. Decide the full-suite strategy for legacy wizard/install/delegation test failures. Do not mark `7.3` complete until either the full suite passes or the change explicitly documents why those legacy failures are out of scope.

5. Clean generated local artifacts before finalizing if desired:
   - `.pytest-tmp/`
   - `task_relay/**/__pycache__/`

Do not touch `docs/enhance_review_arbiter_personas.md` unless the user asks; it was already modified before this implementation work.
