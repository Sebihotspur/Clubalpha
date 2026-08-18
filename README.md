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

## Status

The first PL, UCL, and preseason foundation pull is operational. Clubalpha does
not yet produce deployment-ready probabilities or recommendations.
