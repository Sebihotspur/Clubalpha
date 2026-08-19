# Player Quality v0.1

## Purpose

Player Quality answers one question: **How good is this player?**

It is a slow-moving, position-aware Alpha Ability Grade. Current squad role, opponent matchup, and projected minutes belong to Squad Form or future match layers.

## WCALPHA baseline

Clubalpha starts with the existing WCALPHA attacker and defender formulas.

For each usable metric:

```text
metric_z = clamp(
    (league_adjusted_player_metric - positional_peer_mean)
    / positional_peer_standard_deviation,
    -3,
    +3
)

alpha_ability_z =
    sum(metric_z × metric_weight)
    / sum(available_metric_weight)
```

Only confirmed or calculated metrics are usable. Estimated metrics are excluded. Positive grades with thin metric coverage are dampened.

The public Player Quality value is the raw `alpha_ability_z`. The engine also
publishes `reliability_adjusted_z`, which applies the locked WCALPHA minutes and
coverage weights. Neither score contains preseason form, injuries, expected
lineups, or the next opponent.

## Attacker formula

Version: `wcalpha_attacker_v1`

| Metric | Weight |
|---|---:|
| Non-penalty goals/90 | 3.0 |
| xG/90 | 2.8 |
| Shot-creating actions/90 | 2.5 |
| Assists + xA/90 | 2.2 |
| Opposition-box touches/90 | 2.0 |
| Shots on target/90 | 1.8 |
| Key passes/chances created/90 | 1.6 |
| Successful dribbles/90 | 1.4 |
| Progressive carries/90 | 1.2 |
| Possessions won in the attacking third/90 | 1.0 |

## Defender formula

Version: `wcalpha_defender_v1`

| Metric | Weight | Direction |
|---|---:|---|
| Errors | 3.0 | Inverted |
| One-versus-one/tackle performance | 2.8 | Positive |
| Aerial-duel performance | 2.5 | Positive |
| Interceptions/90 | 2.2 | Positive |
| Ground-duel performance | 2.0 | Positive |
| Times dribbled past | 1.8 | Inverted |
| Pace/recovery measure | 1.5 | Positive |
| Clearances + blocks/90 | 1.3 | Positive |
| Pass completion percentage | 1.2 | Positive |
| Versatility | 1.0 | Positive |

Fullbacks and center backs use the same metric weights but remain separate peer populations.

## FotMob v1 mappings

Previous-season Premier League, Champions League, and target-club domestic
player-match rows are aggregated before scoring. Current club membership
supplies the player's peer role and domestic-league quality multiplier.

- `npg90`: goals classified from reconciled match shot maps, with match goal
  events as a fallback, excluding penalties, own goals, and shoot-outs. The
  season goals row is only a fallback when its scope reconciles to the match
  sample.
- `xg90`: non-penalty xG when available, otherwise xG.
- `axa90`: assists plus expected assists per 90.
- `kp90`: FotMob `chances_created`; this is the canonical key-pass feature.
- `v1v1`: tackles per 90, preserving the WCALPHA v1 proxy.
- `aer` and `gnd`: attempt-weighted duel-win percentages.
- `clrblk`: clearances plus one non-duplicated block field per match.

FotMob's detailed match cards omit event keys when a player records zero. Once
a match is known to have full player detail, those absent event counts are
calculated as zero. Provider-level gaps remain missing. Every derived feature
stores its numerator, minutes or attempts, source fields, and calculation note.

## Canonical metric rules

- `chances_created` and `key_passes` are one canonical metric unless a provider documents a real distinction.
- Source values are stored separately even when a WCALPHA compatibility feature combines them.
- Penalties remain separate from open-play scoring.
- Raw values, per-90 values, adjusted values, and grade inputs remain traceable.
- Missing metrics remain missing; they are never silently replaced with invented values.

## Reliability

The grade records:

- minutes;
- available and missing metrics;
- coverage percentage;
- source and retrieval time;
- competition-quality adjustment;
- raw and reliability-adjusted grade.

The existing WCALPHA formulas must pass a parity test: the same inputs must reproduce the same scores before Clubalpha changes or extends them.

The parity suite locks sample standard deviation, the ±3 clamp, league-quality
multiplication, inverted defensive metrics, available-weight normalization,
minutes bands, and positive-only coverage damping.

## Known source-mapping gaps

The existing WCALPHA FotMob importer does not currently populate every weighted field:

- attacker shot-creating actions;
- attacker progressive carries;
- defender pace;
- defender versatility.

The data-source bakeoff must determine whether these fields can be mapped reliably. A future formula change requires a new version and comparison against the WCALPHA baseline.

## Run

After the FotMob foundation exists:

```bash
python3 scripts/build_player_quality.py
```

Generated player features and grades live under
`data/processed/player_quality/` and remain out of Git. The compact coverage and
leader audit is written to `reports/player-quality-audit.json`.

## Current boundary

The domestic-history layer has complete fixture registries for the target clubs
and player detail for 90.5% of finished target fixtures. It is club-filtered
rather than league-wide. A player who transferred from a non-target club may
therefore still need a player-centric backfill. Four smaller leagues expose no
player cards for their target fixtures; those gaps remain explicit in the
coverage audit and must not be filled with partial opponent samples.
