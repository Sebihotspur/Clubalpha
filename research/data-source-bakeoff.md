# Data-Source Bakeoff

## Goal

Choose the smallest reliable data stack that supports Clubalpha's three intelligence outputs:

1. Player Quality
2. Squad Form
3. Historical Fixtures

This is a source evaluation, not an ingestion implementation.

## Candidates

- Primary-provider candidate: Sportmonks
- Primary/fallback candidate: API-Football
- Enrichment and cross-check: FotMob
- Verification: official competition and club sources

Candidates may be added or removed as access, licensing, and coverage are confirmed.

## Required coverage

### Identity and fixtures

- Stable player, team, competition, season, and match identifiers
- Premier League and Champions League fixtures
- Domestic fixtures for Champions League participants
- Club friendlies and preseason matches

### Player Quality

- Minutes and appearances
- Position
- Goals, penalties, xG, and preferably non-penalty xG
- Assists and xA
- Chances created/key passes
- Shots on target and box touches
- Dribbles and progressive actions
- Defensive duels, interceptions, errors, clearances, and blocks

### Squad Form

- Starting lineups and substitutes
- Player minutes
- Injuries and suspensions
- Transfers and team assignment
- Formation or observed position where available
- Preseason match and player statistics

### Historical Fixtures

- At least the previous two competitive seasons
- Match results and timestamps
- Lineups, substitutions, and events
- Team and player match statistics
- Home, away, and neutral venue

## Evaluation sample

Use approximately twelve recent preseason matches:

- Premier League clubs against strong opponents
- Premier League clubs against lower-level or mixed-strength opponents
- Champions League participants from outside England
- Matches with heavy substitutions or incomplete reporting

The sample should expose both the strongest and weakest parts of each provider.

## Pass/fail questions

1. Can the source identify the same player consistently across seasons and clubs?
2. Does it cover preseason lineups, minutes, and player statistics?
3. Can it populate the WCALPHA attacker and defender formulas?
4. Are chances created, key passes, xG, and xA clearly defined?
5. Is historical data available at the required depth?
6. Can raw responses be stored and reproduced legally?
7. Are rate limits, pricing, and update timing suitable for regular use?
8. How does the source behave when data is missing or corrected?

## Deliverable

The bakeoff ends with one decision record:

```text
Primary source:
FotMob role:
Fallback source:
Historical depth:
Preseason coverage:
Known metric gaps:
Estimated monthly cost:
Decision:
```

No production data pipeline should be built until this decision is recorded.
