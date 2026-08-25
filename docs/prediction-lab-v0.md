# Prediction Lab v0

## Purpose

Prediction Lab v0 is Clubalpha's first chronological probability experiment.
It converts the accepted Fixture State intelligence into home and away expected
goals, then runs 50,000 match simulations. Every output is shadow-only.

```text
August 11 Fixture States
        ↓ outcome-free component SDs
August 18 frozen Fixture States
        ↓ observed August 21–24 FotMob xG
August 24 goal-model artifact
        ↓
August 28–31 predictions
```

No later result is allowed to alter an earlier snapshot, scale, coefficient, or
prediction. The frozen artifacts record their dates and training match IDs.
The August 11 squad state is reconstructed by reversing 50 later
effective-dated transfer records from the foundation roster and clearing the
later injury snapshot. That reconstruction uses no post-cutoff match row or
outcome and remains explicitly flagged in the artifact; it is suitable for this
shadow experiment, not a substitute for a natively archived dated roster.

## Component scaling

The three confidence-adjusted Fixture State components use different numerical
scales. Prediction Lab fits one sample standard deviation for each component
from the earlier August 11 snapshot:

```text
normalized_component = raw_effective_component / historical_sample_sd

fixture_signal =
    0.60 × normalized_club_form
  + 0.30 × normalized_player_quality
  + 0.10 × normalized_historical_residual
```

The first artifact contains 17 fixtures and 34 fixture sides. The minimum
shadow gate is 30 sides; validation requires 200. Outcomes are never used to
fit component scales.

## Goal calibration

The goal layer remains separate from Fixture State:

```text
predicted_xg =
    competition_xg_baseline
  × exp(goal_coefficient × fixture_signal)
```

The first coefficient uses the 10 opening Premier League matches, or 20 team-xG
observations. The regression target is observed FotMob xG rather than goals,
and the competition baseline is an offset. A fixed ridge penalty of 2.0 shrinks
the coefficient toward no adjustment.

Because 10 matches cannot validate a probability model, simulations do not use
the central coefficient. They use the bootstrap 95% bound closest to zero. If
the interval crosses zero, the applied coefficient is zero. This conservative
policy remains active until the chronological calibration sample reaches 100
matches.

The 2026-08-24 artifact records:

- raw coefficient: 0.5131;
- ridge point estimate: 0.4457;
- match-bootstrap 95% interval: 0.1464 to 0.7957;
- applied shadow coefficient: 0.1464;
- baseline in-sample xG MAE: 0.8051;
- applied conservative in-sample xG MAE: 0.7140.

Those MAE values describe the same tiny training sample. They are not an
out-of-sample performance claim.

## Simulation

Each fixture receives 50,000 deterministic independent-Poisson simulations.
The output contains:

- home, draw, and away probabilities;
- Over and Under 2.5;
- Over and Under 3.5;
- both teams to score;
- predicted home, away, and total xG;
- five most frequent scorelines;
- the exact random seed and model artifacts.

Independent Poisson is the transparent v0 baseline. A Dixon-Coles or correlated
goal model requires evidence that it improves fresh chronological predictions.

## First frozen slate

The August 28–31 slate contains 10 Premier League fixtures. Every fixture has a
complete dated lineup prior. The largest shadow probabilities are Manchester
United home to Ipswich at 52.0%, Arsenal away to Aston Villa at
51.1%, and Coventry home to Hull at 50.2%. These are outcome probabilities,
not market edges; no odds have been ingested.

The frozen files live under:

```text
artifacts/prediction_lab/2026-08-24/
├── component-scales.json
├── goal-model.json
├── predictions.jsonl
└── report.json
```

The one-off builder used for this frozen snapshot is:

```bash
python3 research/aug24_shadow_test.py
```

The tracked artifacts are the immutable record. FotMob team pages are live
rather than historical endpoints, so a later cache refresh is a new snapshot,
not a guaranteed byte-for-byte rebuild of August 24.

## Decision boundaries

- Component scaling is shadow-ready but not validated: 34 of 200 required sides.
- Goal calibration is shadow-ready but not validated: 10 of 100 required matches.
- Fixture-specific and confirmed lineups remain unavailable.
- Probabilities are not market prices or betting edges.
- Market readiness and capital deployment remain false.
- Player scorer and assist probabilities remain deferred until the team goal
  model is stable on fresh fixtures.

## Data-boundary correction

The live refresh exposed that FotMob's `excludeFromRanking` marker means a
player is excluded from current rankings, not from the club roster. The
foundation parser now retains those players in squad and continuity snapshots.
Coach rows remain excluded.
