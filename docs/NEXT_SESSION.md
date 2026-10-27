# Next session

Updated: 2026-10-26

Model and website checkpoint: see latest commit on `main`

Production: <https://clubalpha-club-form-v1.vercel.app/predictions/>

## October 27 UCL Alpha catch-up

- UCL now uses the exact Premier League projected-XI Player Alpha generator:
  identical positional formulas, latest-five selection evidence, formation
  vote, 990-minute allocation and attach-Alpha-after-selection boundary.
- Matchdays 1–3 contribute 54 completed observational matches: 221 goals from
  189.58 xG, 40/54 Over 2.5, and score/xG winner alignment in 40/54. These
  describe the competition but never become retroactive prediction results.
- Matchday 4 has 18 provisional fixtures and 900,000 simulations. Shared
  decision thresholds expose two side and fifteen totals research candidates,
  but none is promoted because UCL-specific venue, draw and tempo calibration
  does not yet exist.
- Projected-XI Alpha rates 34/36 UCL clubs. Sabah FK and Shakhtar Donetsk remain
  explicit zero-coverage gaps; they enter the lineup component neutrally and
  cannot manufacture an opponent advantage.
- Before Matchday 4, refresh domestic/cup lineups and availability, rebuild the
  18 fixtures, freeze the first honest UCL slate, then begin the separate UCL
  ledger. Real capital remains unauthorized.

### October 27 domestic and league-strength refresh

- Current foreign-domestic evidence now contains 286 completed matches across
  15 leagues and 31 foreign UCL clubs; 268 matches have target-club player
  detail (93.7%).
- Club Form v1.1 now applies the locked Player Quality league-strength ladder
  once after competition normalization and opponent adjustment. Player Alpha
  formulas and the 60/30/10 weights remain unchanged.
- The revised Matchday 4 slate preserves the original snapshot separately.
  The clearest correction is Bodø/Glimt–Lille: the home probability moved from
  55.8% to 41.8%. Fenerbahçe–Liverpool changed leader, with Liverpool now at
  47.9%.
- Raw side research candidates are Barcelona, Liverpool and Borussia Dortmund.
  They remain unpromoted until the independent UCL calibration bucket exists.

## October 26 Matchweek 9 provisional slate

- The refreshed engine covers all ten Matchweek 9 fixtures with 500,000 total
  simulations. The selective decision policy promotes zero 1X2 calls and passes
  all ten sides rather than manufacturing conviction.
- Two provisional totals clear the 58% decision boundary: Manchester City–
  Brighton Over 2.5 at 58.1%, and Liverpool–Arsenal Under 2.5 at 60.0%.
- Thirteen participating clubs still have EFL Cup fixtures from October 27–29.
  Final-call eligibility is therefore blocked by design, even for the two
  provisional totals. Real allocation remains 0.00u.
- The current refresh includes 80 completed Premier League matches, 54 current
  Champions League matches, 4,602 current player-match rows, rebuilt Club Form
  and Dynamics, 1,051 Player Alpha grades, projected XIs, historical evidence,
  pre-match load, contextual interaction and downstream calibration.
- Start the next session after the October 29 EFL Cup matches: refresh FotMob,
  availability, minutes and projected XIs; rebuild the MW9 slate; compare every
  changed probability and decision with this preserved provisional artifact;
  then freeze only if no preleague fixture remains pending.

## October 26 Matchweek 8 settlement and learning upgrade

- The published Matchweek 8 slate is now settled without rewriting its
  pre-match probabilities. Promoted calls scored 1/5 on 1X2 and 1/2 on O/U
  2.5; the three-pick accuracy shortlist scored 2/3.
- Five side passes avoided five losing probability leans. Base leaders scored
  2/10 and contextual leaders 1/10, so the lesson is not to loosen thresholds:
  it is to demand more agreement before promoting a side.
- Projected XIs averaged 8.8/11 correct starters and formation accuracy was
  95%. The planned final post-Europe refresh was not completed, so the slate is
  explicitly labeled a settled published-provisional audit rather than a true
  final freeze.
- The append-only learning state now contains 70 Match Learning Cards. The
  calibration layer uses all 70 for descriptive fitting and six strictly
  chronological cycles for validation.
- Fixture Calibration v1 now adds a conservative total-xG environment
  correction: 42-day recency half-life, 30-match prior and 0.945 applied tempo
  multiplier. Cycle-forward total-xG MAE and O2.5 Brier improve slightly, but
  1X2 Brier worsens, so it remains shadow-only.
- Decision Policy v1 is now explicit and downstream. Strong sides require at
  least 55% probability and a 15-point gap. Medium calls require at least 45%,
  a 10-point gap, supportive context, reliable lineups, and Club Form plus
  projected-XI Player Alpha support. Draw-zone fixtures and leaders below 45%
  pass.
- No final slate may freeze while a participating club has a pending
  preleague fixture. This prevents the missing Matchweek 8 refresh from
  recurring.
- Player Alpha, the locked 60/30/10 base, and frozen forecasts remain
  unchanged. Real capital remains unauthorized.

## Start next session here

1. Refresh FotMob, UCL/domestic crossover evidence, Club Form, projected XIs,
   availability and pre-match load for Matchweek 9.
2. Build the base and contextual slates, then run the decision packet first as
   `provisional`.
3. After all midweek matches finish, refresh again and run `--stage final`.
   The runner must refuse the freeze if any pending preleague fixture remains.
4. Preserve the final packet before kickoff, score only promoted 1X2 and O/U
   calls after full time, and keep BTTS diagnostic-only.
5. Do not relax the new refusal gates from one matchweek. Judge the policy
   chronologically over the next evidence block.

## October 15 Matchweek 7 freeze

- A new ten-fixture Matchweek 7 baseline and contextual slate is frozen before
  the October 17 first kickoff. The base and contextual leaders agree in all
  ten fixtures; context makes no reversals.
- The stricter decision policy passes Brentford–Liverpool and
  Leeds–Manchester United because the leading side is fewer than five
  percentage points clear. Totals are called only above 58% Over probability
  or below 42%.
- Accuracy leaders are Manchester City over Ipswich (65.9%), Brighton over
  Crystal Palace (62.8%), and Brighton–Palace Over 2.5 (67.0%).
- Everton over Chelsea is the only strict price-aware shadow shortlist: 48.1%
  football probability versus a 30% best ask at capture time. It remains a
  research pick with zero capital authorization.
- Brighton–Palace Over misses the exact five-point price gate by 0.04 points;
  apparent Unders in Tottenham–Coventry and Leeds–Manchester United are
  rejected because the football probabilities do not reach the totals
  confidence boundary.
- Canonical selection evidence is stored in
  `artifacts/matchweek_research/2026-10-15-mw7/picks.json`. The frozen
  contextual archive is registered for automatic post-match collection.

## October 15 Matchweek 6 settlement

- All ten Matchweek 6 results are appended to the frozen October 6 contextual
  archive with final scores, FotMob xG, team statistics and actual lineups.
- The exact plain-language calls shown to the user scored 5/10 on 1X2 and 5/10
  on O/U 2.5. The side shortlist scored 1/3 and the one totals shortlist missed,
  so combined higher-conviction performance was 1/4.
- The uncalibrated base probability leaders scored 7/10; Holy Grail contextual
  leaders scored 6/10; final calibrated calls scored 5/10. The downstream
  translation removed value this week. It must prove incremental performance
  before reversing a base leader or elevating confidence.
- Manchester United–Tottenham was the only structural fixture miss. Villa–
  Brentford, Palace–Forest and Hull–Everton were final-result misses whose xG
  direction supported the predicted side.
- Projected XIs averaged 9.05 correct starters and 18/20 formations were right.
  Data coverage and lineup projection were not the main failure source.
- Total-xG dispersion remains compressed: observed match xG ranged 2.13–5.75,
  versus a 2.51–3.17 contextual forecast range.
- Adaptive Learning now holds 50 Match Learning Cards. Four signals reached
  the human-review queue, but the chronological challenger still worsens both
  side-xG MAE and 1X2 Brier; the champion remains unchanged.
- Fixture Calibration v1 now trains descriptively on 50 matches. Its
  cycle-forward Brier is 0.6624 versus 0.6613 for the baseline and top-pick
  accuracy is 37.5% versus 40.0%, so it remains shadow-only.
- Current source coverage contains 60 completed PL matches, 36 completed UCL
  league-phase matches, 234 current foreign-UCL domestic matches and 3,425
  current PL/UCL player-match rows.
- The website now exposes Matchweek 6 results, exact final calls, market
  benchmarks, process classifications, 50-card learning status and the
  unchanged no-capital boundary.
- Full settlement evidence is stored at
  `artifacts/matchweek_research/2026-10-06-mw6/review.md` and
  `artifacts/matchweek_research/2026-10-06-mw6/settlement.json`.

## October 6 Matchweek 6 preparation

- Club Form now includes all 50 completed Premier League matches from
  Matchweeks 1–5. The Adaptive Learning and calibration layers use only the 40
  matches that had genuinely frozen pre-match forecasts; Matchweek 1 informs
  team evidence but is never reverse-engineered into a fake forecast.
- The October international evidence is refreshed through the October 6
  collection time: 337 completed matches inspected, 1,081 covered player-match
  rows, 444 players and 48 current clubs. Workload is joined to the projected XI
  by FotMob player ID and remains a confidence/lineup-review input with zero
  probability weight. Refresh once more if later October 6 fixtures finish.
- The Matchweek 6 load audit marks six teams high risk, eleven medium and three
  low. Compressed recovery plus heavy projected-XI international minutes is a
  review gate, not an injury claim or automatic xG penalty.
- Archetype Matchup Memory v1 is live as a zero-weight research ledger. Forty
  frozen forecasts produce 80 team-side observations across direct-opponent,
  team-versus-archetype and league archetype-versus-archetype memory.
- No archetype interaction has reached the five-match challenger gate. The
  current adaptive challenger also failed chronological promotion, so the Holy
  Grail champion and locked 60/30/10 architecture remain unchanged.
- The dated Matchweek 6 preparation packet is at
  `artifacts/matchweek_research/2026-10-06-mw6/README.md`. It uses agreement
  between football probabilities and the shadow venue/draw calibration as a
  shortlist gate, with lineup load and archetype evidence controlling
  confidence.
- A read-only Polymarket snapshot matched 10/10 1X2 and 10/10 O/U 2.5 books.
  It is price context only; wallet use, orders and capital authorization remain
  disabled.
- Before the final freeze, refresh injuries/availability and expected XIs.
  Preserve this October 6 packet and create a new dated artifact if any call
  changes.

## October 4 evidence refresh

- The existing FotMob foundation is refreshed through October 4: all 50
  completed Premier League matches, all 18 completed UCL league-phase matches,
  and all 14 retained UCL qualifying matches have normalized player and team
  cards.
- Foreign-UCL domestic evidence now contains 205 completed target-club matches;
  193 expose target-player detail, for 94.1% match coverage.
- Club Form and Club Dynamics were rebuilt across 51 clubs from 2,186 unique
  competitive/preseason matches and 4,372 normalized team-match rows.
- Historical Fixtures v2 now exposes the upcoming Matchweek 6 and UCL horizon:
  37 fixtures, complete competition baselines, and 19 fixtures with direct
  history.
- A separate national-team collector now joins international appearances to
  current club squads by FotMob player ID. Through October 4 it retains 1,000
  player-match rows for 440 players from 48 clubs; all 20 Premier League clubs
  are represented by 198 players.
- International evidence has zero automatic model weight. It may review
  workload, availability, recent condition, role, and projected XI only.
- The international window remains open through October 6. Run the collector
  again after it closes, refresh squad availability, then rebuild and freeze
  the official Matchweek 6 slate.
- A dated provisional Matchweek 6 baseline, projected-XI Alpha snapshot, style
  snapshot, and contextual run are stored under the October 4 artifacts. They
  are research-only and must not be treated as the final pre-match slate.
- Full regression suite: 214 tests passing.

## September 21 Matchweek 5 settlement

- All ten Matchweek 5 results are appended to the pre-match contextual archive.
  The research slate scored 4/10 on 1X2 and 5/10 on Over/Under 2.5. It remains
  excluded from the official promotion gate because it was a research slate,
  not an official capital slate.
- Brentford 3–0 Chelsea was the cleanest process success. Clubalpha made
  Brentford the 44.9% football leader while the market made Chelsea the
  favourite; Brentford also won xG 2.65–0.83.
- Brighton 3–0 Arsenal must not be learned as tactical domination. Arsenal won
  xG 1.63–1.31, so the Match Learning Card attributes it primarily to outcome
  variance.
- Manchester City 5–3 Sunderland was a result hit but a process warning:
  Sunderland led xG 3.57–2.82. Preserve the win in the result ledger and the
  defensive warning in medium team memory.
- Projected-XI accuracy was 9.05/11 with 85% formation accuracy. The contextual
  layer slightly improved 1X2 Brier and totals Brier but did not improve raw
  top-pick accuracy or side-xG error.
- Adaptive Learning now contains 40 append-only Match Learning Cards. The
  medium-memory challenger failed the 20-match validation gate, so the Holy
  Grail champion remains active and no automatic weight change is authorized.
- Fixture Calibration v1 is refreshed descriptively on 40 matches. It remains
  an unvalidated shadow challenger and authorizes no capital.

## Start next session: archetype matchup memory

This is the highest-priority extension to Adaptive Learning v1.

- Preserve the readable archetype label and the continuous five-route tactical
  fingerprint exactly as they were frozen before kickoff.
- Add three separate, non-duplicative ledgers: direct opponent history,
  team-versus-opponent-archetype history, and league-wide
  archetype-versus-archetype history.
- Score W-D-L, goals, xG for/against, xG difference, goal environment, route
  execution, venue, opponent quality, lineup reliability, competition, manager,
  and match-state disruption.
- Let xG process lead the learning signal; keep W-D-L as supporting evidence so
  fragile finishing does not become a false tactical belief.
- Fewer than three comparable matches remain descriptive; three to four are
  tentative; five to seven may enter the challenger; eight or more may become
  eligible for human promotion review.
- Archetype memory is a bounded downstream context modifier. It must not alter
  Player Alpha, the 60/30/10 base, frozen forecasts, or capital authorization.

## September 17 adaptive-learning checkpoint

- Adaptive Learning v1 produced 30 immutable Match Learning Cards.
- Error attribution: 15 outcome-variance cases, 9 lineup-projection cases,
  3 club-form/team-strength reviews, 1 draw-calibration review, and 2 model-
  supported matches.
- Fast memory uses a seven-day half-life, medium memory 28 days, and slow
  structural memory 120 days.
- The first chronological challenger was evaluated on 10 later fixtures. It
  worsened side-xG MAE from 0.6135 to 0.6203 and 1X2 Brier from 0.6539 to
  0.6929, so the system correctly held the Holy Grail champion.
- The production Methodology page exposes the cards, memory horizons, and
  champion-challenger gate. Capital remains disabled.
- Full regression suite: 211 tests passing.

## September 16 research checkpoint

- The three newly requested support layers are implemented as versioned,
  zero-live-weight research: an empirical Over 2.5 challenger, a projected-XI
  load/rotation audit, and a no-auth, read-only Polymarket order-book snapshot.
- The goals challenger failed its frozen-fixture promotion gate. On 20 official
  fixtures its Brier score was 0.2606 versus 0.2554 for the existing baseline,
  and log loss was 0.7161 versus 0.7044. It remains inactive. The evidence says
  total-xG estimation is the larger problem; globally raising Over probability
  is not the solution.
- The pre-match audit marks Bournemouth, Crystal Palace, Manchester City, and
  Sunderland high risk. The first three still have a match before their league
  fixture; Sunderland has short rest plus heavy projected-XI load. Refresh the
  affected teams after those matches before freezing Matchweek 5.
- The market collector matched 10/10 Premier League fixtures and 10/10 O/U 2.5
  books. It reads executable asks, spreads, and shallow depth, never places an
  order, and uses no wallet or credentials.
- The first market comparison exposes probability compression rather than a
  deployable edge. Across the slate, Clubalpha assigns the market favourite
  39.4% on average versus 53.8% no-vig, and assigns draws 33.5% versus 23.8%.
  The 30-match Fixture Calibration v1 artifact learned from an unusually
  draw-heavy 13/30 sample and remains explicitly unvalidated.
- Next build: a separate 1X2 calibration challenger using long-run prior
  evidence and chronological frozen-fixture validation. Do not change the
  60/30/10 foundation, Player Alpha, or existing calibration in place. Market
  prices are a benchmark, not a football-intelligence training target.
- Full regression suite: 207 tests passing.
- Detailed evidence:
  `artifacts/research_phase/2026-09-16/README.md`.

## Locked market focus

- Active research markets are now 1X2 and Over/Under 2.5 only.
- BTTS remains in the append-only scorecard as a zero-weight diagnostic. It
  cannot generate an official recommendation, paper-allocation review, or
  capital decision.
- The intelligence foundations, simulation output, frozen historical slates,
  and market-specific backtest history remain unchanged.

## UCL shared-evidence checkpoint

- The final 36-team 2026/27 UCL league-phase registry is resolved. The core
  universe is now 51 clubs: 20 PL clubs plus 31 foreign UCL clubs.
- Current evidence includes 30 completed PL matches, 12 completed UCL matches,
  7 retained UCL qualification matches, and 142 completed foreign domestic
  matches across 15 leagues.
- Foreign domestic player detail is 134/142 matches (94.4%). FotMob exposes
  team results but no player cards for Sabah's three and Shakhtar's five
  domestic matches; both stay explicitly low-confidence.
- Shared Club Form and strength evidence exists for 51/51 clubs. Squad priors
  are usable for 49/51; Sabah and Shakhtar lack complete FotMob squad pages.
- Current UCL/domestic evidence can update shared form, dynamics, historical
  context, and lineup expectations. PL and UCL ledgers/calibration remain
  separate, and the locked prior-season Player Alpha formula was not changed.

## Matchweek 4 frozen checkpoint

- The September 12–14 Premier League slate is frozen before kickoff at
  `artifacts/official_shadow/2026-09-08-mw4/`: 10 fixtures, 4 low-confidence
  calls, 6 medium-confidence calls, 1 audited model override, and zero high
  confidence calls.
- Official 1X2 calls: Bournemouth–Brentford draw, Villa–Forest draw, Chelsea,
  Crystal Palace, Liverpool, Tottenham–Everton draw, Arsenal,
  Coventry–Brighton draw, Manchester City, and Leeds.
- Fixture Calibration v1 is applied downstream of the locked 60/30/10 base.
  The calibrated slate contains four draw calls and four explicit pass/draw
  zones; calibration does not rewrite Player Alpha, Club Form, History, or
  Context.
- The cumulative official ledger remains 3/10 (30%) with 10 Matchweek 4 calls
  pending. The research learner now sees 30 frozen fixtures, 20 completed
  observations, and 10 pending results. No coefficients were automatically
  promoted.
- Fresh FotMob inputs include all 30 completed Premier League matches through
  September 6. The current projected-XI Player Alpha and Club Form snapshots
  are dated September 8 and bound to the actual Matchweek 4 fixture IDs.
- After full time, run `python scripts/run_research_cycle.py --as-of YYYY-MM-DD`.
  The collector automatically targets the newest official archive, appends
  results, rebuilds diagnostics, updates the cumulative learner, and refreshes
  fixture calibration without mutating the frozen slate.

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
  `artifacts/research_loop/2026-09-07-20-completed/`. All twenty teams now have
  two completed observations.
  All signals remain tentative and zero adjustments passed the five-match
  proposal gate. Earlier checkpoints remain preserved.
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
  the official promotion gate. Matchweek 3 is fully settled: official 1X2 is
  3/10, raw probability-leader 1X2 is 2/10, O/U 2.5 is 4/10, and BTTS is 6/10.
- The Ipswich–Liverpool process was much lower-event than forecast: 1.39
  observed FotMob xG versus 3.05 predicted. The audited Liverpool direction
  was correct, but the totals and BTTS misses reinforce the existing
  goal-environment calibration concern.
- After conservative shrinkage, Ipswich's attack-creation multiplier moved
  from 1.131 to 0.956 and Liverpool's from 1.000 to 0.887. Their
  goal-environment multipliers moved to 1.012 and 0.927 respectively. These
  are research beliefs only; the large Isak finishing and Alisson prevention
  residuals remain isolated from xG strength.
- Across the ten official results, mean total xG was close at 2.99 forecast
  versus 2.82 observed. The distribution was badly compressed: forecasts
  ranged only 2.76–3.19 while observed xG ranged 1.39–5.10. Five fixtures are
  now seven structural reviews; Fulham–Palace is an outcome miss whose 3.13–1.97 xG
  process still supported Fulham.
- The raw probability model selected the home side in nine of ten Matchweek 3
  fixtures while six matches finished as draws. Fixture Calibration v1 now
  addresses this in future slates with shrinkage rather than rewriting the
  frozen Matchweek.
- Projected lineups averaged 8.40/11 correct. Tottenham fell to 5/11 against
  Forest, so much of its Player Alpha input evaluated players who did not
  start. Tottenham, Palace, Coventry, Brighton, and Leeds remain priority
  lineup reviews.
- FotMob's full player-match payloads are cached. Early Player Alpha checks are
  directionally useful: Haaland's +2.03 scoring-threat grade preceded his goal,
  Donnarumma's positive keeper grade preceded +1.48 goals prevented, and
  Elliot Anderson's +1.52 headline Alpha aligned with an 8.32 match rating.
  Tyrick Mitchell's two-goal spike came from a −0.15 scoring-threat grade and
  is retained as finishing variance rather than rewriting his player quality.
- The public Methodology page now exposes the learning loop, its 20/20 frozen
  fixture coverage, proposal count, and zero automatic applications.
- The Ledger now shows every settled score, actual FotMob xG, hit/miss status,
  official versus raw-model accuracy, lineup accuracy, and the xG-dispersion
  diagnostic. The website builder automatically selects the latest cumulative
  research checkpoint and latest chronological backtest instead of requiring
  a dated pointer update.
- Fixture Calibration v1 is frozen at
  `artifacts/fixture_calibration/2026-09-07/`. The 20-match artifact reduces the
  current league home/away log-xG ratio by 0.0538 and applies a +0.5282 draw
  logit correction. No team-specific venue effect is eligible before five home
  and five away observations.
- Its honest cycle-forward audit trained on Matchweek 2 and evaluated
  Matchweek 3. Brier score improved from 0.7416 to 0.7247 and log loss from
  1.2099 to 1.1755, but top-pick accuracy stayed 2/10. It remains a
  shadow-only calibration layer, not a validated edge.
- All tests pass, including regression guards proving the earlier Holy
  Grail experiment and original ledger observation were not rewritten by the
  new official scoring stream. The Matchweek 3 test now derives its settled
  count from the append-only result ledger instead of assuming zero results.

## Start here

1. Before the next Matchweek, refresh the foundations and freeze a new slate
   using the September 7 fixture-calibration artifact. Preserve the uncalibrated
   and calibrated probabilities side by side.

   ```bash
   python scripts/run_research_cycle.py --as-of YYYY-MM-DD
   python web/scripts/build_site_data.py
   ```
2. Continue running the cumulative research cycle after every completed
   Matchweek. It now rebuilds Fixture Calibration v1 automatically from every
   registered frozen result.
3. Audit projected-XI misses, beginning with Tottenham (5/11), Crystal Palace
   (7/11), and Manchester United (7/11). Player Alpha is only as good as the
   players and minutes passed into it.
4. Audit the goal-environment compression and the five structural fixtures.
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
