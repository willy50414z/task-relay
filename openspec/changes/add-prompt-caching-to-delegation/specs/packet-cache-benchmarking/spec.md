## ADDED Requirements

### Requirement: Benchmark report SHALL include cache metrics
The packed-vs-full benchmark report SHALL include a `cache_metrics` section when the delegation was performed through the SDK runner with caching enabled.

#### Scenario: Cache metrics present after SDK delegation
- **WHEN** a benchmark run uses `claude-sdk` target and the packet has cache layout enabled
- **THEN** the benchmark report SHALL contain a `cache_metrics` object with `static_byte_count`, `dynamic_byte_count`, `cache_write_tokens`, `cache_read_tokens`, and `cache_hit` fields

#### Scenario: Cache metrics absent for CLI runner
- **WHEN** a benchmark run uses the CLI-based `claude` runner
- **THEN** the `cache_metrics` field SHALL be `null` or absent from the report

### Requirement: Benchmark SHALL support multi-task sequential delegation simulation
The benchmark system SHALL support running multiple tasks for the same change in sequence to measure cache hit rates across delegations.

#### Scenario: Sequential task delegation
- **WHEN** a benchmark is configured with a change that has N tasks and cache layout is enabled
- **THEN** the benchmark SHALL run all N tasks in sequence and report cache hits/misses for each task

#### Scenario: First task is always cache miss
- **WHEN** the first task of a change is delegated
- **THEN** the cache SHALL be a miss (write), and `cache_hit` SHALL be `false`

#### Scenario: Subsequent tasks within TTL are cache hits
- **WHEN** a subsequent task for the same change is delegated within 5 minutes of the first
- **THEN** if the static content is identical, `cache_hit` SHALL be `true`

### Requirement: Benchmark SHALL estimate token savings from caching
The benchmark report SHALL compute and include estimated token savings attributable to caching.

#### Scenario: Savings calculation from API usage
- **WHEN** `cache_metrics` is present
- **AND** SDK usage includes `cache_creation_input_tokens` and/or `cache_read_input_tokens`
- **THEN** the report SHALL compute `estimated_savings_tokens` from the API usage cache token fields as the authoritative source
- **AND** the calculation SHALL NOT assume a fixed byte-to-token ratio equals the actual token count

#### Scenario: Byte-based estimate without API usage
- **WHEN** cache layout byte counts are available but SDK usage cache token fields are unavailable
- **THEN** the report MAY include a byte-based rough estimate
- **AND** that estimate SHALL be clearly marked as non-authoritative
- **AND** it SHALL NOT be used as the authoritative savings value
