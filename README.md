# Clubalpha

Football intelligence for Premier League and Champions League analysis.

## Foundations

1. **Data sources** — trustworthy, traceable football data.
2. **Player quality** — position-aware Alpha Ability Grades.
3. **Club form** — recent team performance, preseason state, and squad availability.
4. **Historical fixtures** — evidence from Premier League and Champions League matches.

These foundations combine into a simple Football Intelligence Snapshot for each team and fixture. Prediction, market, and capital layers will be added only after the foundation is trustworthy.

## Project documents

- [Architecture](docs/architecture.md)
- [FotMob data pipeline](docs/data-pipeline.md)
- [Player quality](docs/player-grade-spec.md)
- [Club Form](docs/club-form-spec.md)
- [Club Dynamics](docs/club-dynamics-spec.md)
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

v1 grades three positions, covering only six of the eleven places on a pitch.
v2 adds midfielders and goalkeepers, splits centre-backs from fullbacks, and
rebuilds the scoring layer. v1 stays in the repository untouched as the parity
baseline, and every rating change is reported as a delta against it.

Build the five-position grades:

```bash
python3 scripts/build_player_quality_v2.py
```

Outputs land in `data/processed/player_quality_v2/` and stay out of Git. The
tracked audit is `reports/player-quality-v2-audit.json`. Transfer gaps remain
explicit in the coverage fields; closing them belongs in a separate data-layer
change rather than the locked rating formula.

See [Player quality](docs/player-grade-spec.md) for the formulas, the league
offset rebuild, standardisation, and shrinkage.

## Club Form v1

Refreshes of the foundation and domestic-history collectors now materialize
team-match scores, xG, shots on target, big chances, total shots, and box
touches. Completed current competitive matches are included automatically.

Build Club Form after Player Quality:

```bash
python3 scripts/build_club_form.py
```

The output separates attack, defence, confidence, preseason, venue splits, and
the dated availability snapshot. Preseason begins at one-quarter weight and is
capped at 20%; injuries are annotated with Alpha Ability but do not move the
score without a projected lineup.

See [Club Form](docs/club-form-spec.md) for the exact formulas and boundaries.

## Club Dynamics v1

Club Dynamics explains how each team plays, where its recent strengths and
weaknesses sit, and how manager or squad changes affect confidence. It uses
normalized FotMob manager history, confirmed transfers, match style statistics,
and Player Quality grades.

```bash
python3 scripts/build_club_dynamics.py
```

Style remains descriptive, transfer fees never enter the model, and manager or
transfer changes do not modify Club Form without walk-forward validation. The
first dated squad snapshot establishes the continuity baseline for later pulls.

See [Club Dynamics](docs/club-dynamics-spec.md) for the exact axes and safeguards.

## Status

The PL, UCL, and preseason foundation pull is operational. Player Quality v2
grades all eleven pitch positions. Club Form v1 builds attack, defence, and
evidence confidence, while Club Dynamics v1 adds style, strengths/weaknesses,
manager state, transfers, integration, and dated squad continuity.

Clubalpha does not yet produce deployment-ready probabilities or
recommendations. Historical Fixtures and the later probability layer remain
separate work.
