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
