# Data-Source Bakeoff

## Decision

Decision date: 2026-08-18

```text
Primary source: FotMob public web data
Verification: Premier League and UEFA official pages
Fallback source: None in v0.1
Historical depth: Previous PL and UCL seasons first
Preseason coverage: Fixture registry broad; player detail varies by match
Known metric gaps: SCA, progressive carries, pace, and versatility
Estimated monthly cost: $0
Decision: Proceed with a cached, source-aware FotMob collector
```

Clubalpha must remain a zero-license-cost project. The original paid-provider
bakeoff is closed. The evaluation questions below remain as ongoing source
health checks because FotMob's web feeds are undocumented.

## Goal

Maintain the smallest data stack that supports Clubalpha's three intelligence outputs:

1. Player Quality
2. Squad Form
3. Historical Fixtures

This document now acts as the ongoing source-health contract for the FotMob ingestion pipeline.

## Sources

- Primary: FotMob
- Verification: official competition and club sources

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

## Reconsideration trigger

Reopen the source decision only if FotMob becomes inaccessible, loses a metric
required by the Alpha formula, or a genuinely free and more stable source
becomes available.
