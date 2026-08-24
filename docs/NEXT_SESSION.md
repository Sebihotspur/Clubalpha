# Next session

Updated: 2026-08-24

Working branch: `codex/fixture-state-v1`

## Current checkpoint

- Player Quality v2 is locked and grades all five positional populations.
- Club Form v1, Club Dynamics v1, and Squad Selection Prior v1 are merged.
- Historical Fixtures v2 and the accepted Composite Model v1 are merged.
- Fixture State v1 now materializes the confidence-aware raw handoff.
- The frozen 2026-08-18 snapshot contains 31 upcoming fixtures.
- All 31 have Club Form, historical residual, and competition xG inputs.
- Twenty-seven have complete projected-XI lineup priors; four preserve neutral,
  explicitly flagged selection gaps.
- Player Quality uses absolute projected-XI Alpha quality; the own-baseline
  availability delta remains diagnostic.
- All 31 lineups remain dated priors rather than fixture-specific or confirmed.
- Historical manifest, version, kickoff, age, and `as_of` integrity are enforced.
- No past-only component-scale artifact exists, so all final composites are null.
- Fixture State contains no goal-calibration coefficient or calibrated xG path.
- The complete 113-test suite passes.

## Start here

1. Review Fixture State v1 and its tracked real-data audit.
2. Merge only if the confidence treatment and residual definitions remain
   accepted.
3. Build dated historical Fixture State snapshots and fit frozen component scales.
4. Activate and verify 60/30/10 only with a past-only scale artifact.
5. Fit and evaluate home and away xG coefficients in a separate layer.

## Preserve these boundaries

- Do not change the locked Player Quality formulas inside calibration work.
- Do not shrink released Club Form scores a second time.
- Do not replace the competition xG baseline with the 60/30/10 signal.
- Do not reduce Player Quality back to only the own-baseline availability delta.
- Do not activate weights without past-only component scales.
- Do not allow direct history above 1.5% of the complete fixture adjustment.
- Do not redistribute missing component weight.
- Do not put goal calibration inside Fixture State.
- Do not call an output a probability, edge, or wager before calibration passes.
