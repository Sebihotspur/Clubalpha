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
- Prediction Lab v0 reconstructs an August 11 scale snapshot with 34 complete
  fixture sides, reverses 50 later transfer events, clears later injuries, and
  preserves the 200-side validation gate.
- The separate August 24 goal artifact trains on 10 opening Premier League
  matches and preserves the 100-match validation gate.
- Small-sample simulations apply the bootstrap coefficient bound closest to
  zero, not the more aggressive point estimate.
- Ten August 28–31 Premier League shadow predictions are frozen with 50,000
  deterministic simulations each.
- A read-only Overview, Predictions, Shadow Ledger, and Methodology dashboard is
  deployed at `https://clubalpha-club-form-v1.vercel.app/`.
- The first manual Polymarket observation for Crystal Palace–Manchester City is
  frozen separately from model artifacts. No price changed the forecast and no
  real capital was authorized.
- FotMob `excludeFromRanking` is correctly treated as ranking eligibility, not
  squad membership.
- The complete 121-test suite passes.

## Start here

1. Review the frozen Prediction Lab v0 slate and audit.
2. Keep every forecast immutable; append outcomes only after kickoff.
3. Continue logging timestamped market observations only after forecasts are
   frozen; never use them to refit the same slate.
4. Add more earlier Fixture State snapshots until component scaling reaches 200
   sides.
5. Accumulate at least 100 chronological goal-calibration matches.
6. Score the next slate on xG MAE, 1X2 Brier/log loss, totals calibration, and
   probability reliability before changing any coefficient.

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
- Do not use the point goal coefficient while the small-sample conservative
  policy is active.
- Market observations may be logged after a prediction is frozen, but they may
  not alter the forecast, count as validation, or authorize capital before the
  probability-validation gates pass.
