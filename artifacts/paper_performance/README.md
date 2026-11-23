# Clubalpha paper-performance ledger

This directory preserves dated, reproducible snapshots of Clubalpha's paper
record. Each snapshot keeps four books separate:

1. `official_paper`: selections that cleared every football, refresh, price,
   spread and depth gate before kickoff. Only this book represents deployed
   paper capital.
2. `raw_price_diagnostics`: pre-match model/price discrepancies that did not
   clear the complete decision gate. Their equal-stake returns are
   counterfactual research only.
3. `discretionary_review_candidates`: structurally reviewable pre-match ideas.
   Unapproved candidates never count as official positions.
4. `model_accuracy_diagnostics`: the frozen 1X2 leader and O/U direction for
   every fixture, tracked without capital.

Gross paper return assumes equal capital staked at the captured executable ask.
Fees and subsequent slippage are excluded and remain explicit in every ledger.
Predictions are never backfilled after kickoff, shadow candidates never become
official retroactively, and this record never authorizes real capital.

The current partial Matchweek 11 ledger is stored at
`2026-11-23-mw11-partial/ledger.json`. It will remain immutable after the final
fixture; the settled record will be written to a new dated directory.

## $100,000 reconstructed bankroll

`2026-11-23-historical-bankroll-v1/bankroll.json` applies one locked strategy
to every Premier League round with a timestamped pre-match price snapshot:

- start with $100,000;
- evaluate the frozen 1X2 leader and O/U 2.5 direction;
- require at least five percentage points of raw model edge;
- require a spread no wider than three cents and at least $100 at the top ask;
- choose the cheapest executable ask saved from Polymarket or Kalshi;
- risk at most 1% of the current bankroll per position; and
- reduce the stake when the top ask cannot fill the full 1% allocation.

Coverage currently spans Matchweeks 5, 6, 7, 8, 10 and 11: 60 fixtures, 59
completed results and 120 forecast directions. Matchweeks 2–4 and 9 are
excluded because no timestamped pre-match exchange price was saved. Missing
prices are never reconstructed from closing or post-match markets.

The reconstructed strategy produced 17 positions, five wins, 12 losses and a
gross ending bankroll of $94,147.21. Gross P&L is -$5,852.79 (-5.85% of the
starting bankroll), ROI on $14,880.31 staked is -39.33%, and maximum drawdown
is 8.42%. Fees would make the result slightly worse.

This is a retrospective reconstruction: the standardized bankroll rule was
defined after some early results were known, even though every probability and
price used was genuinely captured before kickoff. It is useful diagnostic
evidence, not a valid out-of-sample profitability claim. The rule is now frozen
for forward paper tracking. Real capital remains unauthorized.
