# Next session

Updated: 2026-08-26

Model and website checkpoint: `b077a72`

Production: <https://clubalpha-club-form-v1.vercel.app/holy-grail/>

## Current checkpoint

- The three intelligence foundations remain locked: 60% Club Form, 30%
  Projected-XI Player Quality, and 10% Historical Fixture residual.
- Player Quality v2 still owns the positional Alpha Ability grades. It evaluates
  expected minutes after squad projection and never selects the lineup.
- Squad Selection v2 is locked: latest five completed matches, dated
  competition/recency weights, a three-lineup formation vote, same-competition
  latest-XI persistence, and competition-switch suppression.
- Early-season squad transition and the Premier League Alpha table are frozen.
- The 380-fixture fixed-strength Premier League round robin is frozen at
  `artifacts/round_robin/2026-08-25/`, with an empty append-only result stream.
- Contextual Interaction v1 now links the weighted foundation to opponent
  context continuously and directionally:

  ```text
  contextual xG = base xG
                × exp(max sensitivity × matchup signal × reliability)
  ```

- The matchup signal uses 35% attacking-route expression, 35% opponent
  exposure, and 30% projected-XI execution. Channel evidence and XI confidence
  shrink the adjustment automatically.
- Archetype names are explanatory labels only and cannot change the math.
- The first ten-fixture August 28–31 Premier League contextual slate is frozen
  at `artifacts/contextual_interaction/2026-08-26/`. Every fixture was rerun
  through 50,000 simulations.
- The first run moved directional xG by approximately −4.3% to +3.8%. Arsenal
  at Aston Villa (+2.6 percentage points), Manchester City at Crystal Palace
  (+2.4), and Brighton at Chelsea (+1.4) were the largest favorite-probability
  reinforcements. Sunderland–Fulham was the clearest suppression read.
- The 0.10 maximum log-xG sensitivity is a safety rail, not a learned
  coefficient. Context remains shadow-only with zero capital weight.
- The original Prediction Lab forecast and public ledger observation remain
  unchanged. Holy Grail is preserved as a separately auditable challenger.
- The website now publishes Overview, Predictions, Holy Grail, Matchups,
  Ledger, and Methodology routes. The production Holy Grail data reports ten
  fixtures and `capital_deployment_ready: false`.
- All 156 tests pass. The model and production website were deployed from
  `b077a72`; the latest `main` additionally contains this documentation-only
  handoff.

## Start here

1. Let the frozen August 28–31 fixtures complete and append observed results
   without regenerating either the base or contextual predictions.
2. Score the locked baseline and Holy Grail challenger side by side on xG MAE,
   1X2 Brier score, log loss, totals calibration, and BTTS calibration.
3. Build a chronological residual-training set:

   ```text
   observed xG − locked base-model xG = context residual target
   ```

4. Fit contextual sensitivity only on earlier fixtures and judge it on later
   fixtures. Compare full context against route-channel and reliability
   ablations before activating anything.
5. Continue accumulating component-scale sides toward 200 and goal-calibration
   matches toward 100. Matchday 4 or 5 remains a review checkpoint, not an
   automatic capital date.
6. After fixture probability calibration is stable, extend the same expected-XI
   and goal-environment foundation to scorer and assist heads.

## Preserve these boundaries

- Never rewrite a frozen forecast after kickoff or after seeing market prices.
- Never change the locked Player Quality formulas inside calibration work.
- Player Alpha evaluates the projected XI; it never selects it.
- Do not shrink released Club Form scores a second time.
- Do not replace the competition xG baseline with the 60/30/10 signal.
- Do not redistribute missing component weight.
- Historical residual remains capped and subordinate to current evidence.
- Context is downstream of the base model; it may bend expected goals but may
  not silently reweight the three foundations.
- Archetype labels may explain the interaction but never enter the formula.
- Do not fit context to raw performance. Fit only the locked base model's
  chronological residuals to avoid double counting form and player quality.
- Do not treat the 0.10 safety rail as a learned coefficient.
- Do not call an output a market edge or deploy capital before calibration,
  lineup confirmation, price, and evidence gates all pass.
