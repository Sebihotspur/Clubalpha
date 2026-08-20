# Clubalpha

Football intelligence for Premier League and Champions League analysis.

## Foundations

1. **Data sources** — trustworthy, traceable football data.
2. **Player quality** — position-aware Alpha Ability Grades.
3. **Squad form** — previous season, World Cup, and preseason state.
4. **Historical fixtures** — evidence from Premier League and Champions League matches.

These foundations combine into a simple Football Intelligence Snapshot for each team and fixture. Prediction, market, and capital layers will be added only after the foundation is trustworthy.

## Project documents

- [Architecture](docs/architecture.md)
- [FotMob data pipeline](docs/data-pipeline.md)
- [Player quality](docs/player-grade-spec.md)
- [Data-source bakeoff](research/data-source-bakeoff.md)

## Pull the foundation

No API key or paid account is required.

```bash
python3 scripts/pull_fotmob_foundation.py
```

The command caches FotMob responses, normalizes the local datasets under
`data/processed/foundation`, and writes a compact, reviewable coverage audit to
`reports/foundation-coverage.json`. Raw and normalized provider data are not
committed to this public repository.

## Build Player Quality

Once the foundation pull is present, add previous domestic history for the
non-English UCL field and promoted PL clubs:

```bash
python3 scripts/pull_domestic_history.py
```

Then build Player Quality:

```bash
python3 scripts/build_player_quality.py
```

This aggregates match rows into traceable per-90 features and runs the locked
WCALPHA v1 attacker, centre-back, and fullback Alpha Ability formulas. Generated
rows stay under `data/processed/player_quality`; the tracked summary is
`reports/player-quality-audit.json`.

## Player Ratings v2

v1 grades three positions, which is six of the eleven on a pitch — not enough
for a team rating. v2 adds midfielders and goalkeepers, splits centre-backs
from fullbacks, and rebuilds the scoring layer. v1 stays in the repository
untouched as the parity baseline, and every rating change is reported as a
delta against it.

First, close the transferred-player gap. The foundation and domestic collectors
are club-filtered, so a player who spent part of last season elsewhere is
graded on a fragment:

```bash
python3 scripts/pull_transfer_backfill.py --detect-only
python3 scripts/pull_transfer_backfill.py
```

Detection reconciles each squad player's FotMob career history against the rows
already held, so the shortfall is exact rather than estimated. `--detect-only`
sizes the problem without spending collection requests.

Then build:

```bash
python3 scripts/build_player_quality_v2.py
```

Outputs land in `data/processed/player_quality_v2/` and stay out of Git. The
tracked audits are `reports/player-quality-v2-audit.json` and
`reports/transfer-backfill-coverage.json`.

See [Player quality](docs/player-grade-spec.md) for the formulas, the league
offset rebuild, standardisation, shrinkage, and the attack/defence roll-up.

## Status

The PL, UCL, and preseason foundation pull is operational. The WCALPHA v1
attacker and defender engine passes its formula-parity tests and remains the
baseline. v2 extends grading to all eleven pitch positions and produces team
attack and defence ratings.

Clubalpha does not yet produce deployment-ready probabilities or
recommendations. Squad Form has a data foundation but no scoring model, Club
Dynamic is designed but unbuilt, and the v2 roll-up weights are a prior that has
not been fitted against outcomes.
