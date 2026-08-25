# Composite Model v1

## Status

This document records the accepted working architecture as of 2026-08-24.
Player Quality v2 is locked. The composite weights and proposed Club Form v2
category weights are explicit starting hypotheses for walk-forward validation;
they are not fitted coefficients or capital-ready probabilities.

## Principle

Clubalpha exposes three intelligence foundations to one fixture engine:

```text
Player Quality + Club Form + Historical Context
                         ↓
                  Fixture State
                         ↓
             Home xG and Away xG
                         ↓
                    Simulation
                         ↓
               Market and Risk Gate
```

The model does not create another overall club grade. Player metrics remain
inside the locked position-aware profiles; the fixture engine receives only
the confidence-adjusted signals required to estimate goals.

## Fixture adjustment

```text
fixture_signal =
    0.60 × normalized_club_form_matchup
  + 0.30 × normalized_projected_lineup_quality_edge
  + 0.10 × normalized_historical_residual
```

Missing or weak evidence shrinks its own contribution toward neutral. Its
weight is not redistributed to another layer.

Each confidence-adjusted component is divided by a frozen standard deviation
learned only from earlier dated snapshots before these weights activate. This
makes 60/30/10 comparable sensitivities rather than multipliers on three
different numerical scales. The weights do not promise the same realized share
in every fixture; a genuinely neutral component should remain neutral.

The competition home and away scoring environments are not part of the
60/30/10 mix. They establish the starting expected-goal baselines.

## Player Quality: 30%

The locked Player Quality formulas and every metric-level contribution remain
unchanged. The fixture model uses them through expected minutes:

```text
projected_lineup_quality =
    sum(expected_minutes × alpha_ability_z) / 990

projected_lineup_quality_edge =
    confidence_adjusted_own_projected_quality
  − confidence_adjusted_opponent_projected_quality
```

Availability changes expected minutes and lineup scenarios. It does not create
a separate form penalty. The projected-minus-baseline quality delta remains a
diagnostic for availability impact, but it is not the complete Player Quality
component. Direct line-breaking passes remain unavailable from FotMob and are
never imputed as zero or fabricated from another statistic.

## Club Form: 60%

The current Club Form v1 flat metric mix remains the implemented baseline. The
accepted v2 hypothesis separates repeatable process from noisy conversion:

```text
chance_creation =
    0.50 × expected_goals_z
  + 0.30 × big_chances_z
  + 0.20 × shots_on_target_z

attack_form =
    0.85 × chance_creation
  + 0.15 × finishing_above_xg
```

```text
chance_prevention =
    0.50 × expected_goals_against_z_inverted
  + 0.30 × big_chances_against_z_inverted
  + 0.20 × shots_on_target_against_z_inverted

defence_form =
    0.85 × chance_prevention
  + 0.15 × goal_prevention_above_xg
```

Competition normalization, leave-one-match-out opponent adjustment, the
60-day half-life, 0.25 preseason source weight, 20% preseason cap, coverage,
and reliability shrinkage remain in force.

## Historical Context: 10%

Historical Fixtures supplies a residual rather than another complete team
strength score:

```text
venue_residual =
    venue-specific historical performance
  − general historical team performance

h2h_residual =
    direct-matchup performance
  − expected venue-matchup performance

h2h_share = min(h2h_confidence, 0.15)

historical_residual =
    (1 − h2h_share) × venue_residual
  + h2h_share × h2h_residual
```

Direct history can therefore contribute at most 1.5% of the complete fixture
signal. The five-season competition baseline supplies home advantage, goal/xG
means, variance, covariance, and empirical scoring rates for calibration.

## Club Dynamics boundary

Club Dynamics has zero direct composite weight in v1. Style, manager changes,
transfers, and integration remain explanation and confidence context. A named
tactical interaction enters the scoring model only after a walk-forward
ablation demonstrates improvement on fresh fixtures.

## Goal engine

For each side:

```text
expected_goals =
    competition_goal_baseline
  × exp(calibration_coefficient × fixture_signal)
```

The calibration coefficient must be learned with dated walk-forward samples in
a separate versioned goal-model layer. Fixture State never fits or applies it.
Its first output contains competition baseline xG, raw home and away components,
evidence confidence, and uncertainty. The weighted fixture signal also remains
null until a past-only component-scale artifact exists.

## Player events

Player outcomes reconcile to the team goal environment:

```text
player_goal_expectation =
    team_goal_expectation
  × expected_minutes_share
  × normalized_locked_scoring_profile
  + explicit_penalty_component
```

```text
player_assist_expectation =
    expected_assisted_team_goals
  × expected_minutes_share
  × normalized_locked_creation_profile
  + explicit_set_piece_component
```

The scorer head uses the locked scoring characteristics; the assist head uses
the locked creation characteristics, including xA, chances created, key passes,
and covered progression evidence. Similar overall Alpha Ability Grades may
therefore produce different scorer and assist probabilities.

## Market order

1. Match and team totals.
2. Anytime goalscorers.
3. Anytime assist makers.

The market layer converts prices to no-vig probabilities and releases a wager
only when model edge exceeds calibration error and uncertainty. No bet is the
default. Fractional Kelly, daily exposure, fixture correlation, and drawdown
controls remain disabled until the probability layer passes shadow-ledger and
walk-forward gates.

## Deliberately excluded

- another overall club grade;
- a standalone Club Dynamics score;
- transfer-fee or manager-narrative modifiers;
- a major direct-head-to-head weight;
- player props without expected minutes;
- capital deployment before calibration and price tracking.

## Implementation status and order

1. **Complete:** materialize dated raw Fixture State components.
2. **Shadow v0 complete:** fit an August 11 component-scale artifact.
3. **Shadow v0 complete:** fit a conservative 10-match xG coefficient and
   freeze the first 50,000-simulation Premier League slate.
4. **Next:** expand strictly dated scale samples to 200 fixture sides and goal
   calibration to at least 100 matches.
5. Validate totals and team totals on fresh fixtures.
6. Add fixture-specific lineup scenarios and expected minutes.
7. Allocate team goal mass to scorers and assist makers.
8. Add no-vig market prices and a shadow ledger.
9. Enable risk sizing only after calibration gates pass.

The implemented handoff, confidence policy, coverage audit, and remaining
decision boundaries are documented in [Fixture State v1](fixture-state-spec.md).
