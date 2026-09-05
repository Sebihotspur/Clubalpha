# Clubalpha Research Loop v1

The Research Loop is a permanent learning layer around the locked Clubalpha
model. It absorbs completed-match evidence without rebuilding the architecture
or rewriting any forecast.

```text
Frozen prediction
      ↓
Append-only result, FotMob xG, team stats and declared lineups
      ↓
Outcome / xG-process / lineup / route diagnosis
      ↓
Conservative research-state update
      ↓
Dated checkpoint + promotion queue
      ↓
Next pre-match cycle
```

## What updates automatically

- Attack creation relative to the locked base forecast.
- Defensive exposure relative to the locked base forecast.
- Goal-environment or tempo residuals.
- Lineup-projection reliability.
- Team and league route hypotheses.
- Finishing and goalkeeping variance, stored separately from xG strength.

Each strength observation is a log-xG residual. It is weighted by recency and
the accuracy of the frozen projected XI, then shrunk toward zero by a
three-match prior. One match therefore nudges a belief; repeated evidence is
required to move it materially.

## What never updates automatically

- Player Alpha formulas.
- The 60% Club Form / 30% Projected-XI Player Quality / 10% Historical residual
  architecture.
- Historical caps and evidence boundaries.
- Frozen predictions or results.
- Source code.
- Market or capital authorization.

The first promotion gate requires at least five observations, three effective
matches of evidence, a meaningful residual, and 60% directional consistency.
Passing the gate creates a proposal only. It does not silently change the next
forecast.

## Run one research cycle

One command refreshes the latest registered slate, reruns its backtest, and
recomputes the cumulative season state:

```bash
python scripts/run_research_cycle.py --as-of YYYY-MM-DD
```

The runner recomputes the state from the full result ledger, making it
deterministic and resistant to duplicated updates. Its dated checkpoint contains
`state.json`, a human-readable `report.md`, and a manifest binding both files to
the exact input-result fingerprint.

New frozen slates are registered as data in `config/research-loop-2026-27.json`.
The runner then reads every registered cycle, so earlier learning is retained
without carrying mutable hidden memory or applying the same match twice.

The registry accepts both native `contextual` experiments and
`official_shadow` slates. Official rows are adapted only in memory to the
research contract: their frozen predictions remain byte-identical, their
audited 1X2 decision stays separate from the probability model being
calibrated, and the append-only result retains its original archive version.
Each cycle's projected lineup is explicitly bound to its fixture ID so a later
lineup snapshot can never be used to grade an earlier projection.
