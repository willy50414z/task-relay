## ADDED Requirements

### Requirement: System SHALL provide an Anthropic SDK-based agent runner
The system SHALL provide a new agent runner (`AnthropicSDKRunner`) that sends delegation prompts directly to the Anthropic Messages API using the `anthropic` Python SDK, supporting `cache_control` breakpoints.

#### Scenario: Runner is registered and selectable
- **WHEN** a user runs `trly apply --target claude-sdk`
- **THEN** the delegation SHALL be dispatched through `AnthropicSDKRunner` instead of the CLI-based `ClaudeRunner`

#### Scenario: SDK runner requires API key
- **WHEN** `ANTHROPIC_API_KEY` environment variable is not set
- **THEN** `AnthropicSDKRunner.check()` SHALL report `ok: false` with a clear reason about the missing key

### Requirement: SDK runner SHALL parse cache breakpoint markers
When the prompt contains `<!-- trly:cache_break -->`, the SDK runner SHALL split the prompt at that marker and attach `cache_control: {"type": "ephemeral"}` to the content block(s) before the breakpoint.

#### Scenario: Prompt with cache marker
- **WHEN** the prompt contains the cache breakpoint marker
- **THEN** the SDK runner SHALL split the prompt into static and dynamic portions
- **AND** the static user portion SHALL be sent as one content block with `cache_control: {"type": "ephemeral"}`
- **AND** the dynamic portion SHALL be sent without `cache_control`

#### Scenario: Prompt without cache marker
- **WHEN** the prompt does not contain the cache breakpoint marker
- **THEN** the SDK runner SHALL send the entire prompt as a single content block without `cache_control`
- **AND** the request SHALL still succeed (backward compatible)

#### Scenario: Multiple cache markers
- **WHEN** the prompt contains more than one complete standalone `<!-- trly:cache_break -->` marker
- **THEN** the SDK runner SHALL reject the prompt with a clear validation error instead of guessing which marker is authoritative

#### Scenario: Marker matching is exact
- **WHEN** the prompt contains text such as `trly:cache_break` or an escaped representation of `<!-- trly:cache_break -->`
- **THEN** the SDK runner SHALL NOT treat that text as a breakpoint unless it exactly matches the complete standalone marker line `<!-- trly:cache_break -->`

### Requirement: Template content SHALL be placed in system prompt
When cache layout is enabled, the SDK runner SHALL extract the template portion from the static content and place it in the `system` parameter of the Messages API request with `cache_control`.

#### Scenario: System prompt with cache
- **WHEN** cache layout is enabled and `<!-- trly:template_end -->` is present before `<!-- trly:cache_break -->`
- **THEN** the template SHALL be sent as a `system` message with `cache_control: {"type": "ephemeral"}`
- **AND** the spec/design content after `<!-- trly:template_end -->` and before `<!-- trly:cache_break -->` SHALL remain in the user message as the static user content block

#### Scenario: No cache layout
- **WHEN** the prompt has no cache breakpoint marker
- **THEN** the entire prompt SHALL be sent as a single user message without system prompt separation

#### Scenario: Template boundary missing
- **WHEN** the prompt has a cache breakpoint marker but no `<!-- trly:template_end -->` marker before it
- **THEN** the SDK runner SHALL NOT use heuristic parsing to infer the template boundary
- **AND** it SHALL keep the full static portion in the user message or fail with a clear validation error

### Requirement: SDK runner SHALL report cache usage metrics
The SDK runner SHALL extract cache-related token counts from the API response and include them in `AgentRunResult.usage`.

#### Scenario: Cache write on first request
- **WHEN** the SDK runner sends a request with `cache_control` and the content is not yet cached server-side
- **THEN** `AgentRunResult.usage` SHALL include `cache_creation_input_tokens` from the API response

#### Scenario: Cache read on subsequent request
- **WHEN** the SDK runner sends a request with `cache_control` and the content is already cached server-side (within TTL)
- **THEN** `AgentRunResult.usage` SHALL include `cache_read_input_tokens` from the API response
- **AND** the reported input token cost SHALL reflect the discounted cache read rate

#### Scenario: Existing runners remain usage-compatible
- **WHEN** existing CLI runners construct `AgentUsage` without cache fields
- **THEN** the cache token fields SHALL default to `None`
- **AND** existing runner code SHALL remain source-compatible

### Requirement: SDK runner SHALL support standard delegation parameters
The SDK runner SHALL accept and apply `model`, `effort`, `timeout`, and `cwd` from `AgentRunRequest`, consistent with the existing runner contract.

#### Scenario: Model parameter override
- **WHEN** `request.model` is set to a valid Anthropic model ID
- **THEN** the SDK runner SHALL use that model in the API call

#### Scenario: Timeout enforcement
- **WHEN** `request.timeout` is set
- **THEN** the SDK runner SHALL enforce that timeout on the API call
