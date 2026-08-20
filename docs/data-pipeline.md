# FotMob Foundation Pipeline

## Scope

The first pull builds four local datasets from free FotMob web data:

1. The 2026/27 Premier League club and fixture universe.
2. The 29 confirmed 2026/27 Champions League league-phase clubs and 14 current play-off contenders.
3. The previous Premier League and Champions League fixtures, player-match detail, and requested player and team season metrics.
4. The 2026 preseason fixture registry and every player-match detail FotMob exposes for those clubs.

UEFA remains the authority for qualification status. The seven 2026/27 play-off
winners are intentionally provisional until the second legs finish on 26 August.

## Data flow

```text
FotMob web feeds + FotMob statistics CDN + UEFA qualifier registry
    -> cached source responses
    -> normalized local JSON/JSONL
    -> coverage audit
    -> Player Quality / Squad Form / Historical Fixtures
```

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
- `reports/foundation-coverage.json`: compact counts, gaps, and errors; tracked.

This keeps the public repository reproducible without turning Git into a raw
provider-data warehouse.

## Coverage semantics

- Missing means unavailable, not zero.
- Player-match preseason detail is counted separately from fixture coverage.
- Every observation keeps FotMob IDs so players, teams, and matches remain joinable.
- The collector fails if FotMob silently returns the wrong requested league season.
- UCL qualification status includes an `as_of` date because the field is still changing.

## First-pull result

The 2026-08-18 snapshot found complete player-match detail for all 380 previous
Premier League matches and all 189 previous Champions League matches. In both
competitions, minutes, xG, xA, chances created, box touches, shots, dribbles,
duels, tackles, interceptions, blocks, clearances, and passing appeared in every
match. UCL physical top-speed data was also complete; Premier League top-speed
coverage was effectively absent.

Preseason is thinner: FotMob listed 179 relevant friendlies, 178 were complete,
and 76 exposed player-match statistics (42.7%). Chances created and box touches
were present in all 76 detailed matches, while xG and xA appeared in only 10.
Squad Form must therefore apply metric-level coverage confidence rather than one
blanket preseason weight.

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

## Transfer backfill

```bash
python3 scripts/pull_transfer_backfill.py --detect-only
python3 scripts/pull_transfer_backfill.py
```

Both collectors above are club-filtered, so a player who spent part of last
season outside the PL/UCL universe is graded on a fragment — and the fragment
is biased, because it is usually their settling-in minutes at the new club.

FotMob's `careerHistory.seasonEntries` returns one entry per club per season
with per-competition appearance counts, so the shortfall is an exact
reconciliation rather than an estimate. Detection reads that ledger for every
squad player and compares it against the rows already held. `--detect-only`
sizes the problem without spending a collection request.

Collection then fetches only the fixtures needed to close the gaps, batched one
request per competition-season since players frequently share a missing club.

Three properties matter for data integrity:

- **Rows are player-filtered, not club-filtered.** Opponents in a backfilled
  match are discarded. Keeping them would hand the grading population thousands
  of players represented by one or two games, which is the partial-sample
  problem the club-filtered collectors exist to prevent.
- **`(match_id, player_id)` keys already held are skipped**, and newly kept rows
  join that set as collection proceeds, so a player appearing in two batches
  cannot be written twice.
- **Competitions without a league id remain missing.** FotMob reports some
  one-off ties with no league identifier, which cannot be resolved to a fixture
  list. They are recorded as unresolvable in the audit rather than dropped.

Outputs live under `data/processed/transfer_backfill/`; the tracked audit is
`reports/transfer-backfill-coverage.json`.

Career-history appearance counts come from the same provider as the match
sample, so this is reconciliation and not independent verification.
