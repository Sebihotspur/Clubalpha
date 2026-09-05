# Next session

Updated: 2026-09-04

Model and website checkpoint: see latest commit on `main`

Production: <https://clubalpha-club-form-v1.vercel.app/predictions/>

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
- All ten frozen fixtures are now recorded in the append-only result stream.
  Arsenal beat Aston Villa 1–0 with FotMob xG of 1.05–0.31.
- The completed backtest scores final-result calibration, observed xG, and the
  frozen projected XI separately. Holy Grail is effectively tied with the base:
  it slightly improves 1X2 Brier/log loss, over 2.5, BTTS, and goal-side MAE,
  while side-xG MAE is 0.677 versus 0.675 for the base. Both top-pick
  accuracies are 4/10.
- Villa–Arsenal was an outcome hit for both models. Context raised Arsenal's
  away-win probability from 51.1% to 53.8% and correctly suppressed Villa's
  attack, but total xG remained over-projected at 2.96 versus 1.36 observed.
- The strongest diagnostics are not a coefficient verdict. The projected XI
  averaged roughly nine correct starters, and total-xG forecasts are
  over-compressed: the base spanned 2.71–3.14 while observed match xG spanned
  1.36–6.83.
- A no-leakage ablation of coefficient choices already frozen before kickoff
  shows that simply increasing sensitivity is not the fix. The applied 0.1464
  conservative coefficient has the best side-xG MAE (0.661); the frozen 0.4457
  point estimate expands the range but worsens side-xG MAE to 0.735.
- Liverpool–Forest, Chelsea–Brighton, and Leeds–Brentford are the structural
  review queue. Bournemouth–Everton, Coventry–Hull, and Spurs–Newcastle were
  outcome misses whose xG direction still supported the forecast.
- Only box pressure, set pieces, and high pressing became preferred contextual
  routes in this slate; wide delivery and direct transition never led after
  evidence reliability was applied.
- Research Loop v1 now turns the append-only results into cumulative,
  conservative team beliefs for attack creation, defensive exposure, match
  tempo, lineup reliability, finishing variance, and route hypotheses. It
  recomputes from every registered cycle and cannot learn the same match twice.
- The latest cumulative research checkpoint is frozen at
  `artifacts/research_loop/2026-09-04-11-completed/`. Ipswich and Liverpool now
  have two observations; every other team has one. All signals remain
  tentative and zero adjustments passed the five-match proposal gate. Earlier
  checkpoints remain preserved.
- Official Matchweek 3 slates now feed Research Loop v1 through a read-only
  in-memory adapter. It preserves the frozen archive byte-for-byte, keeps the
  audited official decision separate from raw probability calibration, and
  binds each projected XI to the correct fixture so later snapshots cannot
  leak backward.
- Manchester United, Chelsea, and Nottingham Forest produced the largest
  tentative attacking upside relative to the frozen base. Ipswich, Brighton,
  and Liverpool showed the largest tentative defensive exposure. These are
  research beliefs, not forecast overrides.
- The first official shadow slate is frozen at
  `artifacts/official_shadow/2026-08-31-mw3/`: all ten Premier League
  Matchweek 3 fixtures, frozen at 18:56:06 UTC before Aston Villa–Arsenal
  kicked off. That final Matchweek 2 fixture is intentionally excluded from
  the evidence set.
- The official 1X2 calls are Liverpool, Newcastle, Brentford, Brighton,
  Fulham, Manchester City, Nottingham Forest, Aston Villa, Manchester United,
  and Arsenal. Liverpool at Ipswich and Aston Villa at Hull are explicit,
  documented football-audit overrides of the raw top model outcome.
- The archive stores immutable predictions, an append-only result stream,
  source hashes, validation, and reproducible generation. Website Predictions,
  Overview, Holy Grail, and Ledger now consume that official archive.
- Advancement requires a strictly greater than 50% official 1X2 hit rate after
  at least 30 settled fixtures. Passing it opens paper allocation and price
  validation only. Real capital remains disabled and requires separate
  calibration, price, lineup, availability, and drawdown gates.
- The Ledger now includes a collapsed Matchweek History view. Each week keeps
  1X2, O/U 2.5, and BTTS hit rates separate. Matchweek 2 reports 4/10, 4/10,
  and 6/10 respectively; it is labeled as research and does not count toward
  the official promotion gate. Matchweek 3 has begun: Liverpool's 2–0 win at
  Ipswich makes the official 1X2 ledger 1/1, while the model's Over 2.5 and
  BTTS leans are both 0/1. Nine fixtures remain pending.
- The Ipswich–Liverpool process was much lower-event than forecast: 1.39
  observed FotMob xG versus 3.05 predicted. The audited Liverpool direction
  was correct, but the totals and BTTS misses reinforce the existing
  goal-environment calibration concern.
- After conservative shrinkage, Ipswich's attack-creation multiplier moved
  from 1.131 to 0.956 and Liverpool's from 1.000 to 0.887. Their
  goal-environment multipliers moved to 1.012 and 0.927 respectively. These
  are research beliefs only; the large Isak finishing and Alisson prevention
  residuals remain isolated from xG strength.
- The public Methodology page now exposes the learning loop, its 11/20 frozen
  fixture coverage, proposal count, and zero automatic applications.
- All 179 tests pass, including regression guards proving the earlier Holy
  Grail experiment and original ledger observation were not rewritten by the
  new official scoring stream. The Matchweek 3 test now derives its settled
  count from the append-only result ledger instead of assuming zero results.

## Start here

1. Review the completed ten-match diagnostic, especially why the model placed
   Villa–Arsenal in a roughly 2.95-xG environment when the observed total was
   1.36. Keep the correct Arsenal direction separate from the totals error.
2. As each Matchweek 3 fixture settles, append results to the official archive
   and rerun the cumulative research loop. Score all ten fixtures; do not omit
   low-confidence calls or rewrite either audited override.

   ```bash
   python scripts/run_research_cycle.py --as-of YYYY-MM-DD
   python web/scripts/build_site_data.py
   ```
3. Audit projected-XI misses, beginning with Tottenham (6/11), Crystal Palace
   (7/11), and Manchester United (7/11). Player Alpha is only as good as the
   players and minutes passed into it.
4. Audit the goal-environment compression and the three structural fixtures.
   Do not solve compression by increasing one global coefficient. Test a richer
   pre-match xG translation that can distinguish attack creation, opponent
   prevention, lineup execution, and goal-environment volatility while leaving
   the 60/30/10 intelligence weights unchanged.
5. Audit why wide delivery and direct transition never become preferred routes;
   improve measured evidence rather than increasing their weight blindly.
6. Build a chronological residual-training set:

   ```text
   observed xG − locked base-model xG = context residual target
   ```

7. Fit contextual sensitivity only on earlier fixtures and judge it on later
   fixtures. Compare full context against route-channel and reliability
   ablations before activating anything.
8. Continue accumulating component-scale sides toward 200 and goal-calibration
   matches toward 100. Matchday 4 or 5 remains a review checkpoint, not an
   automatic capital date.
9. After fixture probability calibration is stable, extend the same expected-XI
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
