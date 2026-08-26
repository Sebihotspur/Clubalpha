# Squad Selection v2

## Purpose

Squad Selection v2 answers the most important unresolved pre-match question:

> Who is likely to start this fixture, appear, and play how many minutes?

It is fixture-specific but never presented as a confirmed lineup. The current
Player Quality formula remains locked and cannot influence manager-selection
probabilities.

## Minimal model

Only the five latest completed matches before kickoff enter the projection.
The latest match has full rank weight and each older match keeps 75% of the
next-newer match's weight. A different competition receives 75% of the
same-competition weight.

At the season boundary, evidence also carries a transparent source weight:

```text
current season    2.00
preseason         0.50
previous season   0.25
```

The current competitive lineup is therefore the primary navigator, preseason
confirms the new personnel hierarchy, and the old season is a fallback. The
latest-XI persistence bonus applies to competitive evidence only. Preseason
receives no single-lineup bonus because split squads and experimental shapes
made its latest XI unreliable.

For each player:

```text
P(start)  = recency-weighted declared starts / exact-lineup weight
P(appear) = recency-weighted appearances / match weight

raw expected minutes =
    P(start) × E(minutes | start)
  + (P(appear) - P(start)) × E(minutes | substitute)
```

The raw values remain visible. A capped allocation then creates the 990 team
minutes required for Player Quality aggregation, with no player above 90.
Known unavailable players are set to zero before allocation; questionable and
unknown players remain visible.

Up to three exact recent formations vote on the projected shape. Players are
ranked within its tactical slots by expected minutes. Within the same
competition, members of the latest declared XI receive a 30-minute persistence
bonus. When the target changes competition, that one-lineup bonus is switched
off; all five-match evidence and the shape vote remain active. The complete
policy was chosen on the earlier 60% of the chronological development sample.

## Honest historical test

The walk-forward test uses 17,342 player-match rows from 569 Premier League and
Champions League matches. For every target, the model sees only earlier rows
for that club. The candidate pool contains only players previously observed
for the club, so a debuting or transferred starter is recorded as a miss.

The source is pinned by SHA-256
`82af6759d38800f8b5c2f3d1bd915924e135889eaa550a962af2da91dab0832c`.
The runner rejects a lookalike source without starter and lineup-position
fields. It searches the persistence bonus and competition-switch rule only on
the first 60% of projections. The final 40% remains the evaluation holdout:

| Holdout metric | v1 minutes policy | v2 | Change |
|---|---:|---:|---:|
| Mean starters found (of 11) | 8.477 | 8.615 | +0.138 |
| XI hit rate | 77.06% | 78.32% | +1.25 pp |
| Formation accuracy | 69.27% | 72.48% | +3.21 pp |
| Expected-minutes MAE | 20.811 | 20.811 | unchanged |

The activation gate passes, but the gain is intentionally described as modest.
The output is a stronger fixture prior, not a guarantee.
The start and appearance values are recency-weighted empirical frequencies,
not yet calibrated probabilities; the gate promotes the XI/minute policy only.

The improvement is positive when the holdout is split by competition: +0.152
starters per Premier League projection and +0.103 per Champions League
projection. A paired bootstrap resampling whole matches gives a 95% interval
of +0.053 to +0.220 starters and a 99.96% probability of a positive gain.
Realized rotations of five or more players remain the weakest segment, but the
previous two lineups did not identify those rotations in advance. That is a
confidence limitation for future team-news work, not permission to use the
actual lineup retrospectively.

## Early-season transition check

The first 2026/27 Premier League round supplies a small, separate transition
check. Using only previous-season competitive evidence found 6.10 opening-day
starters per club. Adding the conservative source hierarchy above raised that
to 6.35 across all twenty clubs and from 7.07 to 7.43 among the fourteen clubs
with usable preseason player detail. This is useful directional evidence, not
a large enough sample to fit another formula.

Preseason formation reduced opening-day formation accuracy, so once a current
competitive XI exists its shape wins. Preseason supports personnel continuity;
it does not dictate the competitive formation.

Run the reproducible backtest with an explicit normalized player-match source:

```bash
python3 research/backtest_squad_selection_v2.py \
  --player-match-rows /path/to/historical_match_player_stats.jsonl
```

Tracked result: `reports/squad-selection-v2-backtest.json`.

## Role-aware Alpha handoff

After the XI and expected minutes are frozen, the locked player grades are
attached. Existing, direction-oriented metric z-scores are reorganized into:

- scoring threat;
- chance creation;
- defensive prevention.

Each pillar is standardized against the same Alpha position and shrunk with
the grade's existing minutes reliability. Team pillars are expected-minute
weighted. Separate attacking-unit and defensive-unit averages use the locked
headline Alpha Ability grade.

This changes neither the overall player grade nor who the model selects. It
creates clearer inputs for team goals, scorers, assists, and opponent-specific
matchups. It does not yet create market probabilities.

## Decision boundary

```text
recent matches + formation + availability
    → XI probabilities and expected minutes

frozen XI/minutes + locked Alpha Ability
    → scoring / creation / prevention context

context + opponent + calibrated goal model
    → probabilities (separate future layer)
```

## Locked operating contract

1. Build the candidate pool from the current squad and remove only explicit
   hard unavailability.
2. Use no match row at or after the target kickoff.
3. Freeze start frequency, appearance frequency, raw minutes, the capped
   990-minute allocation, tactical shape, and projected XI before attaching
   any player grade.
4. Treat the result as a pre-lineup prior. A verified confirmed XI replaces
   the projected starters; it does not rewrite this model's historical output.
5. Keep selection frequencies labeled uncalibrated until a later reliability
   test supports probability language.
6. Never tune this version on the 436-projection holdout. Any changed signal,
   window, weight, or override becomes a new challenger with later data.

Team news and a confirmed matchday XI can override this prior closer to
kickoff. Alpha Ability cannot. This v2 policy is locked as the starting logic
from 2026-08-26; changes require a new version and a later chronological test.
