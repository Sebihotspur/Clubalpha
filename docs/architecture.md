# Clubalpha Architecture v0.1

## Principle

Simple is beautiful. Clubalpha begins with four foundations and adds new layers only when the foundation requires them.

```text
Data Sources
    ├── Player Quality
    ├── Squad Form
    └── Historical Fixtures

Player Quality + Squad Form + Historical Fixtures
    → Football Intelligence
```

## 1. Data Sources

Purpose: supply trustworthy and traceable football data.

Initial source roles:

- A primary data provider for repeatable historical and current statistics.
- FotMob for enrichment and cross-checking.
- Official competition and club information when verification is needed.

Every stored observation must identify its source, retrieval time, match, player, team, competition, and season. Raw source data must remain separate from calculated grades.

## 2. Player Quality

Question: **How good is this player?**

Player Quality is a slow-moving, position-aware Alpha Ability Grade. The initial attacker and defender formulas come from WCALPHA and remain versioned.

Inputs include:

- per-90 player metrics;
- positional peer comparisons;
- competition quality;
- minutes and sample reliability;
- metric coverage and confidence.

Player Quality does not include the next opponent or whether the player is expected to start the next match.

## 3. Squad Form

Question: **What condition and configuration is the team in now?**

Inputs include:

- previous-season team performance;
- World Cup performance and workload;
- preseason performance;
- transfers, injuries, and availability;
- expected roles and tactical changes.

Preseason can strongly change role, fitness, and tactical assessments. It should only modestly change underlying player ability.

## 4. Historical Fixtures

Question: **What does real match evidence tell us?**

The historical record begins with:

- Premier League fixtures;
- Champions League fixtures;
- domestic matches needed to evaluate Champions League clubs;
- relevant history for newly promoted Premier League clubs.

Each match should preserve the information needed to study lineups, minutes, player statistics, team performance, opponent strength, venue, and result without using information that was unavailable at the time.

## First output

The first useful product is a Football Intelligence Snapshot:

```text
Team
├── Player Quality
├── Squad Form
└── Relevant Historical Evidence
```

Goals, assists, totals, market prices, and capital deployment remain outside v0.1. They will be built later on top of trusted intelligence.
