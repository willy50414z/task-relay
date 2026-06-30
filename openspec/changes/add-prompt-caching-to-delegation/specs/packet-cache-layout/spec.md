## ADDED Requirements

### Requirement: Packet builder SHALL support cache-aware content ordering
The packet builder (`build_packet`) SHALL, when cache layout is enabled, reorder output sections so that all change-scoped static content appears before a cache breakpoint marker and all task-scoped dynamic content appears after it.

#### Scenario: Cache layout enabled with spec and design sections
- **WHEN** cache layout is enabled and the packet includes template, spec sections, design sections, task block, scope note, budget note, and repo references
- **THEN** the output SHALL place template, `<!-- trly:template_end -->`, spec sections, and design sections before the `<!-- trly:cache_break -->` marker, and task block, scope note, budget note, repo references, and extra reads after the marker

#### Scenario: Cache layout enabled without design section
- **WHEN** cache layout is enabled and the change has no design.md
- **THEN** the output SHALL place template, `<!-- trly:template_end -->`, and spec sections before the cache breakpoint marker and all other content after it

#### Scenario: Cache layout disabled
- **WHEN** cache layout is not enabled
- **THEN** the output SHALL be identical to the current flat layout with no cache breakpoint marker present

### Requirement: Template boundary marker MUST define system prompt extraction
When cache layout is enabled, the packet builder SHALL emit a deterministic template boundary marker so SDK runners can split template instructions from spec/design content without heuristic parsing.

#### Scenario: Template boundary is present
- **WHEN** cache layout is enabled
- **THEN** the packet SHALL contain exactly one instance of `<!-- trly:template_end -->` as a standalone line before `<!-- trly:cache_break -->`

#### Scenario: Template boundary separates template from static user content
- **WHEN** an SDK runner parses a cache-layout packet
- **THEN** content before `<!-- trly:template_end -->` SHALL be treated as template/system instructions
- **AND** content after `<!-- trly:template_end -->` and before `<!-- trly:cache_break -->` SHALL be treated as static user content

### Requirement: Cache breakpoint marker MUST be machine-parseable
The cache breakpoint marker SHALL be a unique string that a downstream runner can reliably detect and split on, without being affected by normal packet content.

#### Scenario: Marker is present and unique
- **WHEN** cache layout is enabled
- **THEN** the packet SHALL contain exactly one instance of `<!-- trly:cache_break -->` as a standalone line

#### Scenario: Packet content coincidentally contains the marker string
- **WHEN** any section content contains the literal string `<!-- trly:cache_break -->`
- **THEN** the packet builder SHALL escape or replace that occurrence with a representation that does not contain the substring `trly:cache_break`
- **AND** the escaped content SHALL NOT be interpreted as a cache breakpoint by any runner

#### Scenario: Runner marker matching is exact
- **WHEN** a runner parses a packet for cache markers
- **THEN** it SHALL match only the complete standalone marker line `<!-- trly:cache_break -->`
- **AND** it SHALL NOT treat partial strings such as `trly:cache_break` or escaped marker text as a breakpoint

### Requirement: Static content MUST be identical across delegations for the same change and mode
When producing packets for the same change and mode (but different tasks), the portion before the cache breakpoint marker SHALL be byte-for-byte identical.

#### Scenario: Same change, different tasks
- **WHEN** two packets are built for the same change and mode but different task IDs
- **THEN** the content before `<!-- trly:cache_break -->` SHALL be identical in both packets

#### Scenario: Different changes
- **WHEN** two packets are built for different changes
- **THEN** the content before `<!-- trly:cache_break -->` MAY differ (specs and design sections are change-specific)

#### Scenario: Different modes
- **WHEN** two packets are built for the same change but different modes
- **THEN** the content before `<!-- trly:cache_break -->` MAY differ (templates are mode-specific)

### Requirement: Template instructions SHALL be moved to cacheable position
When cache layout is enabled, the mode template (containing delegation instructions, output format, non-goals, timeout) SHALL be placed in the static portion before the cache breakpoint.

#### Scenario: Template is in static portion
- **WHEN** cache layout is enabled
- **THEN** the template content SHALL appear before the `<!-- trly:template_end -->` marker and before the cache breakpoint marker
