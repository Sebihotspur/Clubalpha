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

---

# Player Quality v2

Version: `clubalpha_player_quality_v2` — `config/player-quality-clubalpha-v2.json`

v1 above remains in the repository untouched as the parity baseline. v2 does
not modify it; the two engines run side by side and every rating change is
reported as a delta.

## What v2 changes

v1 graded three positions, covering only six places on a pitch. v2 adds the
midfielder and goalkeeper formulas WCALPHA already had but Clubalpha never
ported, and splits centre-backs from fullbacks so fullbacks can carry the
attacking work their role actually involves.

| Position | Metrics | Source-defined | Observed now |
|---|---:|---:|---:|
| FW | 12 | 10 | 9 |
| CM | 11 | 11 | 10 |
| CB | 11 | 10 | 9 |
| FB | 12 | 12 | 11 |
| GK | 5 | 5 | 5 |

51 slots, 48 sourced. `sca90` and `pc90` have no FotMob source; `pace` awaits
confirmation that `physical_metrics_topspeed` holds across the full season.
`line_breaking_passes` is source-defined for FW, CM, CB and FB but is absent
from all 38,193 rows in the current snapshot, so its weight leaves every
denominator until the dataset supplies it.

Forwards include both passes into the final third and line-breaking passes so
their grade recognises progression as well as finishing and creation.
Fullbacks add chances created and assists plus expected assists; modern
wing-backs must be measured on the chances they supply, not only their crossing
accuracy and defensive events. Their scoring slot is goals plus expected goals,
while their creation slot is assists plus expected assists, so assists are not
counted twice.

## Flat weights

Every metric inside a formula carries equal weight, so a composite is an
unweighted mean of available z-scores and the listed order is presentation
only. The WCALPHA 3.0-to-1.0 ladder was never fitted against outcomes, and
flattening removes concentration nobody chose: a centre-back's grade was 57%
duels and mistakes and is now 40%.

This is a judgement, not a measured improvement. The 569 completed 2025/26
PL and UCL fixtures are enough to test flat against laddered by which better
predicts goals scored, and that comparison has not been run.

## Minutes are not a scored metric

WCALPHA scored `avail` inside the midfielder and goalkeeper formulas. v2 drops
it. Availability belongs to Squad Form, and scoring it here would count minutes
twice — once as a metric, once through the reliability policy — and only for
two of the five positions.

`savepct` is dropped for a different reason: it measures the same event set and
the same outcome as goals prevented, without adjusting for shot quality. It
is not used as a fallback. Where direct goals prevented is unavailable, v2
derives it as expected goals on target faced minus goals conceded, and excludes
competitions that publish neither measurement rather than treating them as
zero.

## League quality

v1 multiplied the raw metric value by a tier multiplier read from the player's
**current club's** league. That was wrong three ways.

- It used the wrong league. A player who spent last season at Strasbourg and
  now plays for Chelsea had the Premier League's 1.15 applied to Ligue 1
  statistics.
- It ran backwards on inverted metrics. After the sign flip, 0.10 errors per 90
  scored −0.115 in the Premier League against −0.070 in a default league, so
  the weaker league graded better for an identical error rate.
- It moved bounded percentages roughly 2.5× harder than rates, because
  multiplying a 60% aerial rate by tier produces a 27-point swing against a
  population spread near 8.

v2 applies league quality as an additive offset on the finished z-score:

```text
z = clamp(((sign × raw − peer_mean) / peer_sd) + league_offset, −3, +3)

league_offset = Σ(offset_match × minutes_match) / Σ(minutes_match)
```

Each match takes the offset of the **opponent's** domestic league, so a
Champions League tie inherits the strength of who was actually faced and a cup
tie against a lower-division side is not scored as though it were a league
fixture. Offsets convert from the v1 tiers as `3.0 × (multiplier − 1.0)`,
preserving the existing ordering. The conversion constant is a prior.

## Standardisation and shrinkage

Raw composites were not comparable across positions. Forward grades ran to
1.655 while centre-backs topped out at 0.763 — not a football fact, but the
consequence of attacking metrics having fat right tails while defensive metrics
are bounded percentages. Any position weighting applied on top would have
amplified the artifact.

```text
standardised_z = (composite − position_mean) / position_sd
final_z        = standardised_z × minutes / (minutes + 900)
```

Standardisation comes first so that zero means "average for this position", and
shrinkage therefore pulls a thin sample toward its own positional average
rather than toward an arbitrary point. Together these replace the 700-minute
eligibility cliff and the reliability bands, whose 0.76 floor let a 90-minute
player keep three-quarters of their grade.

Peer means and standard deviations are computed from players with 700+ minutes
only. Every player is still scored against that reference; short samples simply
stop widening the spread everyone else is measured by.

## Two denominators, two rules

Thirty-six slots are per-90 rates and nine are percentages. Each has its own
small-sample protection because each has a different denominator.

| Metric | Minimum attempts |
|---|---:|
| Aerial duel win % | 50 |
| Ground duel win % | 50 |
| Pass completion % (CB) | 300 |
| Distribution accuracy % (GK) | 200 |
| Accurate crosses % (FB) | 30 |

Below its floor a percentage is treated as missing and its weight leaves the
denominator. Without this, a fullback completing two of three crosses reads 67%
and outranks one completing forty of eighty.

Per-90 rates are protected by minutes shrinkage instead, since minutes are a
property of the player rather than of an individual metric.

## Position mapping

`scoring_position()` resolves five populations. A fullback primary position wins
over the listed squad group. A wide-midfielder primary paired with a fullback or
wing-back secondary position also resolves to FB, because FotMob represents
players such as Federico Dimarco as `LM,LB`. A central midfielder carrying an
occasional secondary fullback position remains CM. CAM continues to resolve to
FW, matching WCALPHA.

## Run

```bash
python3 scripts/build_player_quality_v2.py
```

Generated rows live under `data/processed/player_quality_v2/` and stay out of
Git. The tracked audit is `reports/player-quality-v2-audit.json`. Data backfill
and team-level aggregation are separate layers and do not alter this formula.
