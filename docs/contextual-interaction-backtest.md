# Contextual Interaction backtest protocol

The frozen base forecast and Holy Grail contextual forecast are scored side by
side. Never regenerate a dated prediction after its match has started.

## Collect completed matches

```bash
python scripts/collect_contextual_results.py
```

The collector intersects FotMob's Premier League feed with the ten frozen match
IDs. For each newly completed match it appends the final score, xG, normalized
team statistics, and both declared starting XIs to `results.jsonl`. Existing
match IDs are rejected, and the frozen prediction files are not modified.

## Score the slate

```bash
python research/backtest_contextual_interaction_v1.py
```

The report keeps three evidence layers separate:

1. Final-result calibration: 1X2 Brier/log loss, top-pick accuracy, over 2.5,
   and BTTS.
2. Football-process accuracy: side xG MAE/RMSE and total xG MAE.
3. Input accuracy: projected-XI hit rate and formation accuracy.

It also scores the goal-model coefficient choices that were already frozen
before kickoff: zero, the applied conservative bound, the point estimate, and
the raw estimate. This is a no-leakage ablation, not a refit. It distinguishes
"the coefficient is too cautious" from "the xG translation needs richer
features."

A contextual change is helpful only when it reduces error against observed xG
or increases probability on the outcome that occurred. Positive values in the
Holy Grail improvement block always mean the contextual version beat the base.

An outcome miss is labelled `process_supported_outcome_variance` when the
forecast's top 1X2 side still agrees with the match's xG direction (a gap below
0.25 xG counts as balanced). It is labelled `structural_miss` when both the
scoreline and the underlying xG direction disagree with the forecast.

No coefficient or locked 60/30/10 base weighting can be changed from a partial
slate. All forecasts remain shadow-only and authorize zero capital.
