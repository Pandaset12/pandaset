## ADDED Requirements

### Requirement: Automatic ticker logo lookup
The application SHALL request a logo for each displayed stock or fund asset mark from a ticker-based provider when a publishable logo token is configured. Adding a valid holding SHALL NOT require a per-symbol logo file or mapping.

#### Scenario: Known ticker has a logo
- **WHEN** an asset mark for a valid ticker is shown and the provider returns an image
- **THEN** the mark displays that image while the ticker and asset name remain available as text in the surrounding interface

#### Scenario: User adds a ticker
- **WHEN** a user selects or adds a valid ticker that is absent from the application's built-in asset list
- **THEN** the application attempts the same automatic logo lookup for that ticker

### Requirement: Consistent asset identity
The application SHALL use the same logo and fallback behavior for asset marks in onboarding and the standard and event-aware portfolio workflows, including overview, risk, research, and scenario views.

#### Scenario: Asset appears in multiple views
- **WHEN** the same ticker is displayed in onboarding and a saved portfolio view
- **THEN** both views use the shared asset mark behavior for that ticker

### Requirement: Reliable fallback
The application SHALL display a legible local ticker mark when a logo is unavailable, fails to load, or logo lookup is not configured. A missing logo SHALL NOT block ticker selection or any portfolio workflow.

#### Scenario: Provider has no logo
- **WHEN** the provider reports that no image exists for a ticker
- **THEN** the application shows the local ticker mark rather than a broken image or provider-generated placeholder

#### Scenario: Logo is loading
- **WHEN** a logo request has started but its image has not loaded
- **THEN** the application shows the local ticker mark at the final mark size

#### Scenario: Provider request fails
- **WHEN** a logo request fails because of network, authentication, or rate limits
- **THEN** the application shows the local ticker mark and the rest of the page remains usable

#### Scenario: No publishable token is configured
- **WHEN** the application has no logo-provider token
- **THEN** asset marks show local ticker marks without making provider image requests

#### Scenario: Asset changes after a failed lookup
- **WHEN** an asset mark is reused for a different ticker after the previous ticker's image failed
- **THEN** the application attempts the new ticker's image rather than retaining the previous failure state

### Requirement: Safe provider configuration and attribution
The application SHALL use only a publishable logo token in browser image requests and SHALL show provider attribution wherever provider logos are displayed when required by the selected plan.

#### Scenario: Logo request is constructed
- **WHEN** the application requests a logo
- **THEN** the request contains the normalized ticker and publishable token but no user identifier, portfolio allocation, or backend credential

#### Scenario: Commercial free-plan display
- **WHEN** provider logos are displayed under a plan requiring attribution
- **THEN** a visible provider attribution link is available on that screen
