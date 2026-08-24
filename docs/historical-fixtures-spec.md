# Historical Fixtures

## Purpose

Historical Fixtures answers one narrow question:

> What does past competitive match evidence say about this specific fixture?

It is the opponent-specific historical foundation. It does not change Player
Quality or Club Form, and it does not produce a result, totals, or market
probability.

## Snapshot boundary

The builder accepts an inclusive `as_of` date. Historical observations after
that date are rejected. It emits only unplayed Premier League and active
Champions League qualifying fixtures inside the next 14 days, so a dated
snapshot is not silently presented as current intelligence months later.

Preseason does not enter this layer. Preseason already has a controlled role in
Club Form; Historical Fixtures is competitive evidence only.

## Historical venue context

For each target fixture, v1 selects:

- every available home match for the upcoming home team;
- every available away match for the upcoming away team.

The four performance characteristics remain aligned with Club Form:

1. goals;
2. expected goals;
3. shots on target;
4. big chances.

Each characteristic is standardized against match-team peers from the same
competition. Missing values leave the mean; they never become zero.

The resulting attack and defence match scores receive the locked additive
league-quality offset from Player Quality v2. This is essential for promoted
clubs and cross-league Champions League fixtures: above-average performance in
the Championship is not treated as equivalent to above-average Premier League
performance.

```text
metric_z = (value - competition_mean) / competition_sample_sd

attack_match_z  = mean(available attacking metric_z values) + league_offset
defence_match_z = mean(inverted opponent metric_z values) + league_offset
```

Scores are capped at ±3 z.

## Recency and confidence

Competitive history uses a 180-day half-life:

```text
recency_weight = 0.5 ** (age_days / 180)
```

Metric coverage multiplies match weight. Venue-history confidence uses a
five-weighted-match neutral prior:

```text
confidence = weighted_evidence / (weighted_evidence + 5)
```

The home scoring context combines the home team's home attack with the inverse
of the away team's away defence. The away context mirrors it. Inputs are
weighted by their own evidence confidence and shrunk before release.

## Direct head-to-head evidence

Direct history contains only matches between the two named clubs. A meeting at
the same venue orientation receives a 1.25 multiplier. Direct confidence uses
a three-weighted-match prior.

```text
direct_confidence = weighted_evidence / (weighted_evidence + 3)
direct_signal_share = min(direct_confidence, 0.25)
```

The hard 25% cap is a decision boundary, not a fitted coefficient. It prevents
one or two meetings—often under different managers and squads—from dominating
broader venue history. When no direct meeting exists, the share is exactly
zero and the gap remains explicit.

## Outputs

Every fixture record contains:

```text
Fixture
├── Venue history
│   ├── Home team at home
│   └── Away team away
├── Direct history
│   ├── Evidence and confidence
│   ├── Capped signal share
│   └── Recent meeting records
├── Historical signals
│   ├── Home attack z
│   ├── Away attack z
│   ├── Historical home edge z
│   ├── Total-goal environment z
│   ├── Descriptive xG baseline
│   └── Empirical over-2.5 and BTTS rates
└── Quality flags and decision boundaries
```

The descriptive xG baseline averages the relevant venue attack and opposing
venue defence records, then allows the capped direct-history share. Unlike the
dimensionless attack and defence signals, raw xG is not league-strength
adjusted. Mixed-competition use therefore receives an explicit quality flag.

Empirical over-2.5 and both-teams-to-score rates describe the historical sample
only. They are not calibrated probabilities.

## First real-data audit

The frozen 2026-08-18 build produced:

- 31 target fixtures inside the 14-day horizon;
- 20 Premier League fixtures and 11 Champions League qualifying fixtures;
- 3,932 unique historical team-match observations;
- complete attack signals for all 31 fixtures;
- descriptive xG baselines for 27 fixtures;
- direct meeting history for 19 fixtures;
- 12 fixtures correctly marked with no direct history.

Sixteen fixtures had two direct meetings, three had one, and none could exceed
the 25% direct influence cap.

## Deliberately deferred

- opponent-specific tactical style interaction;
- fixture-specific expected lineups and minutes;
- World Cup workload and recovery;
- calibrated goals, totals, scorer, or assist probabilities;
- market prices, edges, staking, or capital deployment.

Those layers may consume Historical Fixtures after walk-forward validation.

## v2 deep-history extension

v1 remains frozen as the one-season comparison point. v2 expands Premier
League and Champions League history to five complete seasons, from 2021/22
through 2025/26, while keeping the same four team-performance characteristics.
The archive deliberately contains team-match detail only; Player Quality owns
historical player evidence.

The three uses of history now have separate policies:

| Use | Maximum history | Half-life | Safeguard |
| --- | ---: | ---: | --- |
| Competition scoring environment | Five seasons | 730 days | 50-match confidence prior |
| Team and venue context | Three seasons | 180 days | 5-match confidence prior |
| Direct matchup context | Three seasons | 270 days | 5-match prior and 15% signal cap |

The longer direct half-life acknowledges that matchups are sparse, while the
three-season cutoff and lower cap prevent old managers and squads from taking
over the signal. Team strength still decays quickly. Older matches primarily
teach the simulation layer how the competitions distribute scores.

### Competition-season normalization

v2 fits peer scales separately for every competition-season. A high-xG season
or competition-format change therefore cannot silently inflate the apparent
strength of every team in that period. When a group lacks 20 peer values, the
metric uses the explicit global fallback already present in v1.

### Competition baseline

Each target fixture receives one slow-moving Premier League or Champions
League environment record. Only the canonical home row is used once per match.
It contains:

- home, away, and total goal means;
- home advantage;
- total-goal variance and home-away goal covariance;
- home, away, and total xG means plus total-xG variance;
- home-win, draw, away-win, over-2.5, and BTTS historical rates.

An active Champions League qualifier uses the full Champions League environment
as a clearly flagged proxy. None of these empirical rates is yet a fixture
probability.

## v2 coverage audit

The frozen 2026-08-18 deep archive contains:

- five Premier League seasons: 1,900 matches;
- five Champions League seasons: 753 matches;
- 2,653 matches and 5,306 team-match rows in total;
- team detail for all 2,653 matches;
- complete goals, xG, shots-on-target, big-chance, and total-shot coverage.

After joining the domestic and current inputs and removing overlap, v2 scores
8,100 unique team-match observations. All 31 target fixtures have complete
attack signals and a competition baseline; 29 have descriptive fixture xG and
20 have direct history.

## First walk-forward smoke test

The snapshot was frozen on 2026-08-18 before the nine completed Premier League
fixtures evaluated on 21–23 August. Their outcomes were already known from the
v1 review when v2 was designed, so this is a regression smoke test rather than
a clean out-of-sample comparison. No coefficient was optimized against these
nine results.

| Metric | v1 | v2 |
| --- | ---: | ---: |
| xG-edge direction | 8/9 | 8/9 |
| xG-edge direction at `abs(edge) >= 0.10` | 5/5 | 5/5 |
| edge vs observed xG edge Pearson | 0.439 | 0.446 |
| goal-environment vs observed total xG Pearson | 0.112 | 0.306 |
| descriptive total-xG MAE | 0.895 | 0.856 |
| descriptive side-xG MAE | 0.780 | 0.775 |

This is encouraging regression evidence, not validation. Nine fixtures are too
few to estimate calibration, market edge, or staking risk, and the weights must
not be tuned to this sample. The reproducible comparison lives in
`reports/historical-fixtures-v2-backtest.json`.
