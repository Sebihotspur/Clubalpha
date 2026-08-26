# Premier League round-robin baseline — 2026-08-25

This directory is the outcome-free baseline for Clubalpha's first complete
Premier League matchup experiment. It contains 380 fixed-strength predictions,
one for every ordered home/away pairing, with 50,000 simulations per fixture.

## Immutability contract

- `predictions.jsonl`, `summary.json`, and `README.md` are frozen.
- `manifest.json` records SHA-256 hashes for those artifacts and the recoverable
  model inputs and builders.
- `results.jsonl` is the only mutable file here. It is append-only and begins
  empty because no result was used to build this baseline.
- Never regenerate or tune this dated archive in place. Any adjusted model must
  write to a new dated directory and receive its own manifest.
- This first archive predates the raw-input provenance file required for future
  freezes. Its predictions and summary remain hash-locked, but exact raw cache
  reconstruction is explicitly incomplete.

Run the integrity check at any time:

```bash
python3 scripts/freeze_round_robin_archive.py
```

## Result reconciliation

Join a real result to its frozen prediction with:

```text
season|home_team_id|away_team_id
```

The IDs are FotMob team IDs. The synthetic `match_id` values in the prediction
rows exist only for deterministic simulation and must not be used for joining.
Every result row must include `result_version`, `recorded_at_utc`, `season`,
both team IDs, `kickoff_utc`, final goals, `outcome`, `source`, and the source's
real match ID.

Append through the validated command rather than editing the stream directly:

```bash
python3 scripts/append_round_robin_result.py \
  --season 2026/2027 \
  --home-team-id ID --away-team-id ID \
  --kickoff-utc 2026-08-29T14:00:00Z \
  --home-goals 2 --away-goals 1 \
  --source FotMob --source-match-id MATCH_ID
```

## Backtest plan

Primary evaluation is multiclass Brier score, log loss, and probability
calibration. Secondary diagnostics are 1X2 accuracy and predicted-xG mean
absolute error. Style Matchup v0 remains a zero-weight challenger; its value
will be tested as an ablation against this untouched baseline.
