# Next session

Updated: 2026-08-24

Working branch: `codex/fixture-state-v1`

## Current checkpoint

- Player Quality v2 is locked and grades all five positional populations.
- Club Form v1, Club Dynamics v1, and Squad Selection Prior v1 are merged.
- Historical Fixtures v2 and the accepted Composite Model v1 are merged.
- Fixture State v1 now implements the confidence-aware 60/30/10 handoff.
- The frozen 2026-08-18 snapshot contains 31 upcoming fixtures.
- All 31 have Club Form, historical residual, and competition xG inputs.
- Twenty-seven have complete baseline lineup priors; four preserve neutral,
  explicitly flagged selection gaps.
- All 31 lineups remain dated priors rather than fixture-specific or confirmed.
- The complete 107-test suite passes.
- No calibration coefficient, probability, market edge, or staking output exists.

## Start here

1. Review Fixture State v1 and its tracked real-data audit.
2. Merge only if the confidence treatment and residual definitions remain
   accepted.
3. Build dated historical Fixture State snapshots for walk-forward training.
4. Fit and evaluate home and away xG coefficients strictly out of sample.

## Preserve these boundaries

- Do not change the locked Player Quality formulas inside calibration work.
- Do not shrink released Club Form scores a second time.
- Do not replace the competition xG baseline with the 60/30/10 signal.
- Do not allow direct history above 1.5% of the complete fixture adjustment.
- Do not redistribute missing component weight.
- Do not call an output a probability, edge, or wager before calibration passes.
