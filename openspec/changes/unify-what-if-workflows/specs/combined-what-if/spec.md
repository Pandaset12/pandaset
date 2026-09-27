## ADDED Requirements

### Requirement: Fast allocation comparison remains available
The What-if page SHALL retain its current allocation editor, presets, add/remove-symbol controls, modeled comparison chart, and explicit action to apply a proposed allocation. A quick comparison SHALL calculate current and proposed allocations over the same aligned adjusted-price window without invoking event research or AI providers. Calculating a comparison MUST NOT change the saved portfolio.

#### Scenario: Compare without event vendors
- **WHEN** a user changes proposed weights and requests a quick comparison while event research is unavailable
- **THEN** the page shows a modeled current-versus-proposed comparison without starting web search or changing the saved portfolio

#### Scenario: Apply proposed allocation
- **WHEN** a user explicitly selects "Use this allocation" after a successful comparison
- **THEN** the selected owned portfolio is updated to the proposed allocation

### Requirement: Optional researched event path shares the allocation
The same What-if page SHALL offer an optional event path that starts from the selected portfolio and the current proposed allocation. Research SHALL begin only after the user explicitly starts an event draft. The path SHALL show sourced facts, missing evidence, shock assumptions and units for review, and require confirmation before computing a durable event run. It SHALL display current-versus-proposed one- and three-month outcomes with visible modeled-result and data-provenance labels.

#### Scenario: Start from edited allocation
- **WHEN** a user edits the proposed allocation and explicitly starts an event draft
- **THEN** the draft uses that proposed allocation and the selected portfolio as its baseline

#### Scenario: Evidence is incomplete
- **WHEN** research cannot verify a material event fact
- **THEN** the review identifies the missing evidence and does not present the fact as verified

#### Scenario: Confirm event assumptions
- **WHEN** a user reviews and confirms the event shocks
- **THEN** the run calculates and saves the event result using those confirmed shocks and shows the one- and three-month comparisons

### Requirement: Allocation coverage is validated before event research
The event path SHALL support symbols present only in the proposed allocation by aligning history for the union of current and proposed symbols and treating an absent holding as zero weight. It SHALL enforce the existing eight-symbol combined limit and required price and factor coverage before queuing research. Issuer-specific templates SHALL accept only an eligible stock in that union.

#### Scenario: Newly added proposed symbol
- **WHEN** a proposed allocation adds a supported symbol absent from the current portfolio and the union has complete history
- **THEN** the event baseline and proposed case include that symbol with zero current weight

#### Scenario: Missing history
- **WHEN** a symbol in the union lacks required aligned price history
- **THEN** no research is queued and the user sees the missing symbol and coverage reason

#### Scenario: Symbol limit exceeded
- **WHEN** the union of current and proposed symbols exceeds eight
- **THEN** the event path rejects the draft with a clear symbol-limit message

### Requirement: Drafts remain tied to reviewed inputs
An event draft SHALL retain the allocation and portfolio revision with which it was created. Later editor or portfolio changes MUST NOT silently alter that draft; the page SHALL identify stale drafts and require a new draft for changed inputs. The page SHALL offer saved runs without exposing raw analysis identifiers or a separate event portfolio or analysis refresh control.

#### Scenario: Edit after research begins
- **WHEN** the proposed allocation changes after a draft was created
- **THEN** the existing draft remains tied to its original allocation and the page requires a new draft for the changed allocation

#### Scenario: Open a saved run
- **WHEN** an owner opens a saved event run after changing the portfolio
- **THEN** the run shows its original portfolio label, allocations, evidence, assumptions, and modeled results
