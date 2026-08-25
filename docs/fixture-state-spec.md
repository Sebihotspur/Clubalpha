# Fixture State v1

## Purpose

Fixture State is the first minimal handoff from Clubalpha's three intelligence
foundations into a future goal model:

```text
Player Quality + Club Form + Historical Context
                         ↓
                  Fixture State
                         ↓
       Walk-forward home/away xG calibration
```

It does not produce probabilities, prices, recommendations, or stakes. Its job
is to preserve one dated, explainable input for each side of a fixture without
counting the same evidence twice.

## Component layout

For each side:

```text
fixture_signal_z =
    0.60 × normalized_released_club_form_matchup_z
  + 0.30 × normalized_projected_lineup_quality_edge_z
  + 0.10 × normalized_historical_residual_z
```

Weak or missing evidence pulls only its own component toward neutral. Weight is
never reassigned to another foundation.

The competition home and away xG means remain outside this 60/30/10 mix. They
are the starting scoring environment, not another team-quality opinion.

Before the weights activate, every confidence-adjusted component must be divided
by a frozen standard deviation fitted from strictly earlier Fixture State
snapshots. The current snapshot does not invent these scales from its own slate.
Without that artifact, raw components remain visible while normalized values,
weighted contributions, and the final fixture signal remain `null`.

## Club Form: 60%

The home scoring matchup is:

```text
home_attack_form_z − away_defence_form_z
```

The away calculation mirrors it. Club Form v1 has already standardized the
target-club universe and reliability-shrunk each released attack and defence
score. Fixture State records the source confidence for evidence review but
does not multiply it again. Doing so would penalize the same uncertainty twice.

The accepted process-versus-finishing Club Form v2 formula remains a validation
hypothesis. Fixture State v1 consumes the implemented and tested v1 output.

## Player Quality lineup delta: 30%

The locked position-aware Alpha Ability formulas remain unchanged. Fixture
State computes each club's expected-minute-weighted Alpha quality:

```text
baseline_quality_z =
    sum(baseline_expected_minutes × alpha_ability_z) / 990

projected_quality_z =
    sum(availability_adjusted_minutes × alpha_ability_z) / 990

availability_delta_z = projected_quality_z − baseline_quality_z
```

An ungraded player's Alpha contribution is neutral zero on the common scale;
their minutes reduce coverage rather than inflating the average of covered
players. Alpha never selects the XI.

The projected quality—not only the availability delta—enters the model. For
home scoring:

```text
lineup_quality_edge_z =
    confidence_adjusted_home_projected_quality_z
  − confidence_adjusted_away_projected_quality_z
```

Each team delta receives its own confidence before subtraction. Confidence is
Alpha-minute coverage multiplied by the maturity of recent and previous-season
selection evidence:

```text
selection_evidence =
    coverage_adjusted_recent_matches + historical_prior_strength

evidence_maturity = selection_evidence / (selection_evidence + 2)

lineup_confidence = alpha_minute_coverage × evidence_maturity
```

The current selection prior is dated and availability-aware but not
fixture-specific or confirmed. Those limitations remain flags on every output.
If either club lacks a usable lineup prior, the entire Player Quality matchup is
neutral; the model does not construct half an edge from only one club.

The v1 edge is an overall projected team-strength comparison. It does not claim
that losing a forward and losing a centre-back have the same effect on totals.
Attack/defence lineup channels require validated role-specific player profiles
and remain a later goal-model extension.

## Frozen component scaling

The 60/30/10 weights act only on comparable historical units:

```text
normalized_component =
    confidence_adjusted_component / past_only_training_sd
```

The scale artifact records a version, method, training cutoff, snapshot and
fixture-side sample counts, and one positive scale for each component. Its
`trained_through` date must be strictly earlier than the Fixture State `as_of`
date. Scale fitting uses no match outcomes, but the past-only rule keeps the
entire walk-forward pipeline reproducible.

## Historical residual: 10%

Historical Context supplies only what is not already represented by general
team performance:

```text
venue_residual_z =
    venue_matchup_z − all_venue_matchup_z

direct_residual_z =
    direct_matchup_z − venue_matchup_z

h2h_share = min(direct_confidence, 0.15)

historical_residual_z =
    (1 − h2h_share) × confidence_adjusted_venue_residual_z
  + h2h_share × direct_residual_z
```

The direct-history share already expresses its confidence, so the same direct
sample is not shrunk again. Because Historical Context is 10% of the complete
signal, direct meetings can contribute at most 1.5% of the full adjustment.

## Goal-engine boundary

The later calibrated goal engine will use:

```text
expected_goals =
    competition_xg_baseline
  × exp(calibration_coefficient × fixture_signal_z)
```

Fixture State never accepts or applies this coefficient. A separate versioned
goal-model artifact must record its training cutoff and validation evidence.
Choosing a number in configuration can never make Fixture State call itself
calibrated.

## Outputs

Run:

```bash
python3 scripts/build_fixture_state.py
```

The ignored dated data and tracked audit are:

```text
data/processed/fixture_state/
├── fixture_states.jsonl
└── manifest.json

reports/fixture-state-v1-audit.json
```

Every fixture preserves:

```text
Fixture State
├── Fixture and as-of identity
├── Home side
│   ├── Club Form matchup and confidence
│   ├── both lineup-quality deltas and confidence
│   ├── venue/general/direct historical residual
│   └── weighted contributions and fixture signal
├── Away side — mirrored structure
├── Competition home/away xG baseline
├── optional past-only component-scale artifact
├── uncalibrated goal-model handoff
└── decision boundaries and quality flags
```

## First real-data audit

The frozen 2026-08-18 build contains:

- 31 upcoming fixtures: 20 Premier League and 11 Champions League qualifiers;
- complete Club Form, historical residual, and competition xG inputs for all 31;
- complete projected-XI Player Quality inputs for 27 fixtures;
- four fixtures carrying an explicit neutral lineup contribution where a club
  has no usable FotMob squad-selection prior;
- projected-XI Player Quality edges from −0.6799 to +0.6799 z before scaling;
- historical residuals from −0.2768 to +0.1779 z before their 10% weight;
- zero normalized composites because no past-only scale artifact exists;
- zero calibrated goal outputs, probabilities, markets, or wagers.

All 31 selection priors remain non-fixture-specific. Twenty-seven fixtures are
ready to enter a past-only component-scale training sample; the four incomplete
lineup matchups remain neutral and are never used to estimate the Player Quality
scale.

## Deliberately deferred

- fitting the goal-engine coefficient;
- calibrated home, away, and total-goal probabilities;
- fixture-specific lineups, rotation scenarios, and confirmed teams;
- validated tactical style interactions;
- player scorer and assist allocation;
- prices, no-vig edge, risk gates, and capital deployment.
