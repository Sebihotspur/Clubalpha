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
- REEP as an optional exact-ID validator where its dated public crosswalk has coverage;
  it never replaces FotMob IDs or becomes required for grading.

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

Style Matchup v0 is now the zero-weight research implementation of that later
role. It compares five named attacking routes with the next opponent's measured
exposure or tactical invitation, then checks the route against the projected
XI's locked scoring, creation, and prevention Alpha components. It remains
outside Fixture State until chronological testing shows incremental value.

The Squad Selection layer is the bridge between Player Quality and Club Form.
Its locked fixture-specific v2 policy is deliberately small:

```text
eligible squad + explicit availability
    → latest five past matches
    → start / appearance frequencies and expected minutes
    → three-lineup formation vote
    → tactical slots + latest-XI persistence within the same competition
    → frozen projected XI and 990-minute allocation
    → attach locked Player Alpha context
```

The latest-XI persistence signal is suppressed after a competition switch;
the remaining evidence is not discarded. Alpha Ability remains completely
outside selection. Alpha grading position also stays separate from tactical
selection role, player minutes are capped at 90, and the team allocation is
capped at 990. The frequencies are not described as calibrated probabilities.

Only after the XI and minutes are frozen does Role-aware Alpha attach the
locked player grades. It exposes scoring threat, chance creation, and defensive
prevention as separate expected-minute-weighted contexts. These are inputs for
later market models, not new player grades or probabilities. The original
non-fixture-specific v1 prior remains the auditable baseline.

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

## Fixture State v1

The first composite remains a handoff rather than another club grade:

```text
Competition xG environment
          +
60% Club Form matchup
30% expected-minute projected-XI Player Quality edge
10% venue/direct Historical residual
          ↓
dated home and away Fixture State signals
```

The competition baseline sits outside the component weights. Club Form's
released reliability shrinkage is applied once. Player Quality compares the
clubs' absolute expected-minute projected-XI quality; the own-baseline
availability delta remains diagnostic. Direct history is capped at 1.5% of the
complete signal.

The three components must use frozen standard-deviation scales fitted only from
earlier dated snapshots before 60/30/10 activates. Fixture State owns neither
goal calibration nor probabilities. Those remain separate versioned layers
after component scaling and walk-forward testing.

## Prediction Lab v0

The first probability experiment preserves those ownership boundaries:

```text
Earlier Fixture States → frozen component scales
Frozen pre-match states + later observed xG → goal-model artifact
Future Fixture State + both artifacts → 50,000 shadow simulations
```

The August 11 scale artifact precedes the August 18 opening-round states. The
goal model then trains through August 24 and predicts only later fixtures.
Small-sample simulations use the bootstrap coefficient bound closest to zero.
The point estimate remains visible for audit, but cannot create false
confidence. The complete contract is documented in
[Prediction Lab v0](prediction-lab-v0.md).

## Contextual Interaction v1

Contextual Interaction sits after the locked 60/30/10 fixture foundation. It
does not replace or reweight Club Form, Projected-XI Player Quality, or the
Historical Fixture residual. Instead, it asks how each attack's continuously
measured routes interact with the opponent's exposures and adjusts the two base
expected-goal values independently:

```text
60/30/10 Fixture Intelligence -> base xG
route expression + opponent exposure + XI execution -> bounded context signal
base xG * exp(max sensitivity * context signal * reliability) -> contextual xG
contextual xG -> 50,000 coherent simulations
```

Archetype names are display labels only. The first implementation is a frozen
shadow sensitivity with zero capital weight because its maximum sensitivity is
a safety rail, not a coefficient learned from chronological residuals. See
[Contextual Interaction v1](contextual-interaction-v1.md) for the exact
calculation, reliability shrinkage, and activation boundary.

## First output

The first useful product is a Football Intelligence Snapshot:

```text
Team
├── Player Quality
├── Club Form Snapshot
│   ├── Performance Form
│   ├── Club Dynamics
│   ├── Availability
│   └── Fixture-specific Squad Selection
│       └── Role-aware Alpha context
└── Relevant Historical Evidence
```

Prediction Lab v0 now emits shadow 1X2, totals, and BTTS probabilities. They
remain outside the trusted deployment product until chronological validation
gates pass; scorer, assist, market-price, and capital layers remain deferred.

The accepted minimal handoff into that later probability layer is documented
in [Composite Model v1](composite-model-v1.md) and implemented in
[Fixture State v1](fixture-state-spec.md).
