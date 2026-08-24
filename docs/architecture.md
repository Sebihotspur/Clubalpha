# Clubalpha Architecture v0.1

## Principle

Simple is beautiful. Clubalpha begins with four foundations and adds new layers only when the foundation requires them.

```text
Data Sources
    ├── Player Quality
    ├── Club Form
    └── Historical Fixtures

Player Quality + Club Form + Historical Fixtures
    → Football Intelligence
```

## 1. Data Sources

Purpose: supply trustworthy and traceable football data.

Initial source roles:

- FotMob as the primary free source for repeatable historical and current statistics.
- Official competition and club information when verification is needed.

FotMob is undocumented. Its web and statistics-CDN access live behind one thin,
cached client so an endpoint change has one repair point. Missing coverage is
recorded; it is never interpreted as a zero.

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

## 3. Club Form

Question: **What condition and configuration is the team in now?**

Inputs include:

- previous-season team performance;
- World Cup performance and workload;
- preseason performance;
- transfers, injuries, and availability;
- expected roles and tactical changes.

Preseason can strongly change role, fitness, and tactical assessments. It should only modestly change underlying player ability.

Club Form v1 begins with recency-weighted attack and defence, low-weight
preseason evidence, and a separate availability snapshot. Projected roles and
World Cup workload remain explicit later inputs. Tactical changes are surfaced
by Club Dynamics rather than hidden inside the performance score.

Club Dynamics v1 now sits inside Club Form as a separate explanatory profile:

```text
Club Form
├── Performance Form — how well the club is playing
├── Club Dynamics
│   ├── Style — how the club plays
│   ├── Strengths and weaknesses — where performance is created or conceded
│   └── Change state — manager, transfers, integration, and continuity
├── Availability — who may be available
└── Squad Selection Prior — current hierarchy, baseline XI, and minute shares
```

Club Dynamics has no composite score and does not modify Performance Form.
Its first role is to make club condition explainable; its later role is to
support opponent-specific style matchups after validation.

The Squad Selection Prior is the bridge between Player Quality and Club Form.
It uses official recent lineup evidence and workload to estimate opportunity;
Alpha Ability remains an attached quality measure and never predicts the
manager's selection. Alpha grading position remains separate from tactical
selection role, player minutes are capped at 90, and incomplete lineup or
historical coverage reduces evidence strength. The joined Club Form Snapshot
materializes every component in one dated team record without creating another
rating formula.

## 4. Historical Fixtures

Question: **What does real match evidence tell us?**

The historical record begins with:

- Premier League fixtures;
- Champions League fixtures;
- domestic matches needed to evaluate Champions League clubs;
- relevant history for newly promoted Premier League clubs.

Each match should preserve the information needed to study lineups, minutes, player statistics, team performance, opponent strength, venue, and result without using information that was unavailable at the time.

Historical Fixtures v1 converts that archive into a dated fixture record with:

- the home team's recency-weighted home history;
- the away team's recency-weighted away history;
- competition-normalized attack and defence context;
- the locked league-strength ladder shared with Player Quality;
- direct meetings with extra same-venue weight and a hard 25% influence cap;
- descriptive xG, over-2.5, and both-teams-to-score history;
- explicit evidence confidence and missing-data flags.

The layer does not modify Club Form and does not create probabilities. Raw xG
history remains visibly unadjusted across competition environments; the
dimensionless attack and defence signals carry the league-strength adjustment.

Historical Fixtures v2 adds depth without adding another intelligence pillar:

```text
Historical Fixtures
├── Competition environment — five seasons, slow 730-day half-life
├── Team/venue context — maximum three seasons, 180-day half-life
└── Direct matchup context — maximum three seasons, 270-day half-life, 15% cap
```

Competition-season normalization prevents changes in the league scoring
environment from being mistaken for team strength. The competition baseline
also preserves goal/xG means, total-score variance, home-away covariance, home
advantage, draw, over-2.5, and BTTS history for later calibrated simulations.
These remain descriptive inputs until a walk-forward probability layer exists.

## First output

The first useful product is a Football Intelligence Snapshot:

```text
Team
├── Player Quality
├── Club Form Snapshot
│   ├── Performance Form
│   ├── Club Dynamics
│   ├── Availability
│   └── Squad Selection Prior
└── Relevant Historical Evidence
```

Goals, assists, totals, market prices, and capital deployment remain outside v0.1. They will be built later on top of trusted intelligence.

The accepted minimal handoff into that later probability layer is documented
in [Composite Model v1](composite-model-v1.md): 60% Club Form, 30% expected-
lineup Player Quality delta, and 10% residual Historical Context, with the
competition scoring environment establishing the baseline outside that mix.
