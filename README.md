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
- [REEP identity pilot](research/reep-identity-pilot.md)

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

## Status

The first PL, UCL, and preseason foundation pull is operational, and the first
attacker/defender Player Quality engine passes WCALPHA formula-parity tests.
Clubalpha does not yet produce deployment-ready probabilities or recommendations.
