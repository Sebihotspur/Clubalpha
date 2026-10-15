# FotMob Foundation Pipeline

## Scope

The first pull builds five local datasets from free FotMob web data:

1. The 2026/27 Premier League club and fixture universe.
2. The finalized 36-club 2026/27 Champions League league-phase field and current fixtures.
3. The previous Premier League and Champions League fixtures, player-match detail, and requested player and team season metrics.
4. The 2026 preseason fixture registry and every player-match detail FotMob exposes for those clubs.
5. Dated club snapshots, manager history, and confirmed transfer events for Club Dynamics.

UEFA remains the authority for qualification status. Qualification matches are
retained only for clubs that reached the final league phase; eliminated clubs
do not expand the target universe.

## Data flow

```text
FotMob web feeds + FotMob statistics CDN + UEFA qualifier registry
    -> cached source responses
    -> normalized local JSON/JSONL
    -> coverage audit
    -> Player Quality / Club Form + Club Dynamics / Historical Fixtures
```

## International-window player evidence

National-team appearances for players in the 51-club PL/UCL universe are
collected into a separate zero-live-weight ledger:

```bash
python3 scripts/pull_international_player_evidence.py \
  --from-date 2026-09-21 \
  --as-of 2026-10-06
```

The collector joins FotMob player IDs back to the current club squads and
preserves minutes, starts, results, goals, assists, xG, xA, chances created,
final-third and line-breaking passes, and defensive actions when published.
This evidence may inform workload, availability, role, condition, and projected
XI review. It has zero automatic Club Form, Player Alpha, probability, or
capital weight because national-team opposition and tactical context are not
directly comparable with club football.

The client uses the current FotMob paths:

- `/api/data/leagues`
- `/api/data/teams`
- `/api/data/matches`
- `/api/data/matchDetails`
- `/api/data/playerData`
- `/api/data/search/suggest`
- `data.fotmob.com/stats/...`

The older unprefixed WCALPHA league and team paths now return 404 and are not reused.

## Run

```bash
python3 scripts/pull_fotmob_foundation.py
```

Useful options:

```bash
python3 scripts/pull_fotmob_foundation.py --as-of 2026-08-18
python3 scripts/pull_fotmob_foundation.py --skip-match-details
python3 scripts/pull_fotmob_foundation.py --refresh
```

Normal runs reuse cached responses. `--refresh` deliberately re-downloads them
and should be used sparingly.

## Storage policy

- `data/cache/fotmob`: source responses, ignored by Git.
- `data/processed/foundation`: normalized datasets, ignored by Git.
- `data/processed/club_dynamics/source_snapshots.jsonl`: append-only dated squad and manager identity, ignored by Git.
- `reports/foundation-coverage.json`: compact counts, gaps, and errors; tracked.

This keeps the public repository reproducible without turning Git into a raw
provider-data warehouse.

## Coverage semantics

- Missing means unavailable, not zero.
- Player-match preseason detail is counted separately from fixture coverage.
- Declared starter status, lineup position, team formation, and lineup source
  are preserved from match cards. Missing lineup data remains unknown; a
  90-minute appearance is never used to infer a start.
- Team-match rows preserve both sides of every match for Club Form and opponent adjustment.
- Decorated team values preserve their leading counts and percentages for style analysis.
- Confirmed transfers retain effective and reported dates so `--as-of` builds can reject future information.
- Every observation keeps FotMob IDs so players, teams, and matches remain joinable.
- Parent competition IDs remain stable across FotMob stage changes; the stage
  ID is preserved separately for audit.
- Red cards, their timing, and estimated 11-v-11 minutes are preserved so a
  numerically distorted match is not mistaken for clean tactical evidence.
- FotMob `excludeFromRanking` is ranking eligibility, not roster status; all
  non-coach squad members are retained.
- The collector fails if FotMob silently returns the wrong requested league season.
- The UCL registry is dated and tied to its official UEFA schedule source.

## First-pull result

The 2026-08-18 snapshot found complete player-match detail for all 380 previous
Premier League matches and all 189 previous Champions League matches. In both
competitions, minutes, xG, xA, chances created, box touches, shots, dribbles,
duels, tackles, interceptions, blocks, clearances, and passing appeared in every
match. UCL physical top-speed data was also complete; Premier League top-speed
coverage was effectively absent.

Preseason is thinner: FotMob listed 179 relevant friendlies, 178 were complete,
and 77 exposed player-match statistics (43.3%). Chances created and box touches
were present throughout the detailed subset, while xG and xA appeared much less
often.
Club Form must therefore apply metric-level coverage confidence rather than one
blanket preseason weight.

Completed current competitive fixtures are pulled into current player- and
team-match datasets on every foundation refresh. Future schedules may remain in
the registry, but an `--as-of` snapshot clears later results and finished
statuses to prevent leakage.

Team pages also produce `club_snapshots.jsonl`, `manager_history.jsonl`, and
`transfer_events.jsonl`. The foundation contains the current normalized source
state; Club Dynamics carries dated snapshots forward so squad continuity can be
measured on later pulls.

## Player Quality handoff

`scripts/build_player_quality.py` consumes current squads, historical
player-match rows, season leaderboards, and current-team domestic league IDs.
It emits traceable per-90 features and versioned Alpha Ability grades without
altering the source layer. The tracked player-quality audit makes the remaining
domestic-history gap explicit.

## Domestic-history expansion

```bash
python3 scripts/pull_domestic_history.py
```

This second cached collector maps current non-English UCL clubs and promoted PL
clubs to their previous domestic competitions. It selects only fixtures
involving those clubs, then retains player-match rows only for the target side.
Opponent-only rows are deliberately excluded: two matches against a target club
must never masquerade as a complete player season.

Outputs live under `data/processed/domestic_history/` and remain ignored by
Git. `reports/domestic-history-coverage.json` records the league mapping,
fixture coverage, metric coverage, errors, and any club without a complete
fixture registry.

The first version pulls match detail plus only two season leaderboards: goals as
a reconciliation fallback and possessions won in the attacking third. The
primary non-penalty-goal count is derived from reconciled match shot maps or
match goal events; other canonical features are calculated from match detail.

## Current foreign-UCL domestic evidence

The same collector is reused for the current season rather than creating a
second provider pipeline:

```bash
python3 scripts/pull_domestic_history.py \
  --config config/domestic-current.json \
  --output-dir data/processed/domestic_current \
  --audit reports/domestic-current-coverage.json
```

It selects only matches involving the 31 non-English UCL clubs across their 15
domestic leagues and clips results to the build's `as_of` date. These rows feed
shared team form, style, strength/weakness, lineup, and historical evidence.
They do not enter the Premier League prediction ledger or Premier
League-specific calibration sample. Player Alpha's locked prior-season formula
also remains unchanged; current matches describe condition and selection until
a separately validated rating update is approved.

When the five-season archive has already been scored, Historical Fixtures can
ingest it incrementally instead of rematerializing every old match card:

```bash
python3 scripts/build_historical_fixtures.py \
  --config config/historical-fixtures-v2.json \
  --seed-scored-history data/processed/historical_fixtures_v2/scored_history_observations.jsonl \
  --output-dir data/processed/historical_fixtures_v2 \
  --audit reports/historical-fixtures-v2-audit.json
```

## Historical Fixtures handoff

After the foundation and domestic-history pulls are present, build the dated
fixture context:

```bash
python3 scripts/build_historical_fixtures.py
```

The builder consumes normalized competitive team-match rows only. It rejects
matches after the `as_of` date, selects unplayed Premier League and active
Champions League qualifying fixtures inside a 14-day horizon, and writes:

```text
data/processed/historical_fixtures/
├── historical_fixture_intelligence.jsonl
├── scored_history_observations.jsonl
└── manifest.json

reports/historical-fixtures-v1-audit.json
```

Generated rows remain ignored by Git. The compact audit is tracked. Direct
head-to-head evidence is recency-weighted, receives a small same-venue boost,
and can never supply more than 25% of a historical attack signal. Missing xG is
preserved as missing rather than converted to zero.

## Five-season historical expansion

The simulation-oriented archive is a separate cached pull:

```bash
python3 scripts/pull_deep_history.py --as-of 2026-08-18
```

It requests Premier League and Champions League seasons 2021/22 through
2025/26, validates that FotMob returned the requested season, excludes future,
cancelled, and abandoned matches, and pulls team-match detail only. Player
Quality keeps its own versioned player evidence; duplicating five seasons of
player rows here would add cost without strengthening the historical-fixture
layer.

```text
data/processed/deep_history/
├── fixtures.jsonl
├── match_team_stats.jsonl
├── manifest.json
└── coverage.json

reports/deep-history-coverage.json
```

The dated 2026-08-18 archive contains 2,653 matches and 5,306 team-match rows,
with detail for 100% of matches. Goals, xG, shots on target, big chances, and
total shots are complete across both competitions. Source and processed rows
stay ignored by Git; the compact coverage report is tracked.

Build the deeper fixture snapshot explicitly so v1 remains reproducible:

```bash
python3 scripts/build_historical_fixtures.py \
  --config config/historical-fixtures-v2.json \
  --output-dir data/processed/historical_fixtures_v2 \
  --audit reports/historical-fixtures-v2-audit.json
```

The build deduplicates overlapping one-season and deep-history rows by FotMob
match/team ID before scoring them.

## Fixture State handoff

After Club Form, Squad Selection Prior, and Historical Fixtures v2 are built,
materialize the dated composite input:

```bash
python3 scripts/build_fixture_state.py
```

```text
data/processed/fixture_state/
├── fixture_states.jsonl
└── manifest.json

reports/fixture-state-v1-audit.json
```

The generated fixture rows remain ignored by Git; the compact audit is tracked.
The builder requires matching `as_of` dates and source versions, validates the
Historical Fixtures manifest, rejects future or age-inconsistent history rows,
and preserves the competition xG baseline outside the 60/30/10 adjustment.

The first snapshot writes raw components only. Normalized contributions and the
fixture signal stay null until `--component-scales` points to a complete artifact
trained strictly before the snapshot date. Fixture State never accepts a goal
calibration coefficient or emits a calibrated goal probability.

## Prediction Lab handoff

Prediction Lab v0 consumes frozen Fixture States rather than reaching around
them into the foundation layers. It fits an outcome-free component-scale
artifact, then a separately versioned xG coefficient, and finally runs 50,000
deterministic independent-Poisson simulations per future fixture. The first
frozen outputs are tracked under `artifacts/prediction_lab/2026-08-24/`.

The first scale snapshot reconstructs August 11 roster membership by reversing
later effective-dated transfers and discards all later injury statuses. That
provenance is embedded in the scale artifact. Predictions remain shadow-only;
the goal layer cannot mark market or capital deployment ready.
