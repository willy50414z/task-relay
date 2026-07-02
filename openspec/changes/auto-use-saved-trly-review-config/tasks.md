## 1. Skill Contract

- [x] 1.1 [delegate:deepseek] Update `task_relay/delegation.py::_build_review_skill_md()` so saved review config is announced with `我將根據以下 review config 進行 review` and then auto-used.
- [x] 1.2 [delegate:deepseek] Remove generated skill wording that asks whether to apply an existing saved review setting.
- [x] 1.3 [delegate:deepseek] Preserve the existing saved-config table columns and display rules for Role, Agent, Model, Effort, and Personas.

## 2. Reconfiguration Flow

- [x] 2.1 [delegate:deepseek] Document explicit reconfiguration triggers in the generated skill, including Chinese and English wording for resetting or changing review config.
- [x] 2.2 [delegate:deepseek] Document routing override triggers in the generated skill, including `--reviewers`, `--arbiter`, `--save`, and `--no-save`.
- [x] 2.3 [delegate:deepseek] Ensure the generated skill still starts the reviewer and arbiter selection workflow when no saved config exists.

## 3. Config Source Guardrails

- [x] 3.1 [codex-only] Confirm the implementation does not add a Python command panel or CLI interactive setup expansion for review config.
- [x] 3.2 [delegate:deepseek] Keep generated skill guidance aligned with managed guidance as the saved config source of truth.
- [x] 3.3 [delegate:deepseek] Ensure no generated skill instruction introduces `.task_relay` as durable review config storage.

## 4. Tests

- [x] 4.1 [delegate:test] Update `tests/test_delegation.py::test_trly_review_skill_documents_interactive_workflow` to assert saved config auto-use wording.
- [x] 4.2 [delegate:test] Add or update assertions proving the generated skill no longer asks whether to apply the saved setting.
- [x] 4.3 [delegate:test] Add assertions for explicit reconfiguration and routing override trigger wording.
- [x] 4.4 [delegate:test] Add assertions that `.task_relay` is not described as durable review config storage.

## 5. Verification

- [x] 5.1 [codex-only] Run `python3 -m unittest tests.test_delegation -v`.
- [x] 5.2 [codex-only] Run `python3 -m unittest discover -s tests -v`.
- [x] 5.3 [codex-only] Run `openspec status --change auto-use-saved-trly-review-config`.
