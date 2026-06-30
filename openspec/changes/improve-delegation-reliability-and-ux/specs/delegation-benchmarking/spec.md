## ADDED Requirements

### Requirement: Benchmark compares packed context against full context
The system SHALL provide a benchmark workflow that compares packed delegation context against full-change context for the same tasks.

#### Scenario: Benchmark runs both context modes
- **WHEN** the operator runs the delegation benchmark on a task set
- **THEN** the workflow SHALL evaluate both packed-context and full-context modes for each benchmark case

### Requirement: Benchmark records cost and quality indicators
The benchmark workflow SHALL record both cost-oriented and quality-oriented metrics for each run.

#### Scenario: Benchmark records token and duration metrics
- **WHEN** a benchmark run completes
- **THEN** the report SHALL include available token counts, packet size or context size, and elapsed duration for each compared mode

#### Scenario: Benchmark records downstream workflow outcomes
- **WHEN** a benchmark run completes
- **THEN** the report SHALL include downstream outcome indicators such as review finding adoption, apply acceptance, or verification pass/fail data when those signals are available

### Requirement: Benchmark outputs reusable reports
The benchmark workflow SHALL write structured output that can be re-run, diffed, and shared as evidence for token-versus-quality claims.

#### Scenario: Benchmark writes machine-readable report artifacts
- **WHEN** the benchmark workflow completes
- **THEN** it SHALL emit a machine-readable report artifact that preserves the compared cases and metrics

#### Scenario: Benchmark preserves sample coverage
- **WHEN** the benchmark workflow is configured
- **THEN** it SHALL allow multiple changes and task categories to be represented in the evaluated sample set
