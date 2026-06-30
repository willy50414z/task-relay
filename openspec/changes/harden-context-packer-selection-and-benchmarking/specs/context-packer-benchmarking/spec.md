## ADDED Requirements

### Requirement: Packed-vs-full benchmark MUST report context cost beyond bytes
The system SHALL report packed and full context cost using bytes plus any available token and cost metrics.

#### Scenario: Trace-backed metrics are available
- **WHEN** benchmark execution can resolve delegate trace usage data
- **THEN** the benchmark report SHALL include actual token and cost metrics for packed and full modes

#### Scenario: Trace-backed metrics are unavailable
- **WHEN** benchmark execution cannot resolve actual token or cost data
- **THEN** the benchmark report SHALL explicitly mark those metrics as unavailable instead of implying they were measured

### Requirement: Benchmarking MUST include downstream quality proxies
The system SHALL record downstream quality proxies so packed-vs-full comparisons are not limited to packet size alone.

#### Scenario: Quality proxy is captured
- **WHEN** review, apply, or verification outcome data is available for a benchmark sample
- **THEN** the benchmark report SHALL include machine-readable quality proxy fields for that sample

#### Scenario: Quality proxy is missing
- **WHEN** no downstream quality proxy is available for a benchmark sample
- **THEN** the benchmark report SHALL explicitly represent the proxy as missing instead of substituting fixture-only assumptions

### Requirement: Benchmark quality proxies MUST use a concrete machine-readable schema
The system SHALL emit named downstream quality-proxy fields so benchmark consumers can compare packed and full runs without inferring field semantics from free-form text.

#### Scenario: Review and apply quality proxies are reported
- **WHEN** benchmark reporting includes downstream quality data
- **THEN** each sample SHALL use named fields for `review_artifact_sections_present`, `verification_passed`, `apply_exit_code`, and `retry_count`, with unavailable values explicitly marked as missing
