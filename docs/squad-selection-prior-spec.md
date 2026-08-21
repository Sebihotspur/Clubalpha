# Squad Selection Prior v1

## Purpose

The Squad Selection Prior answers:

> Which players currently hold the strongest evidence for minutes and a
> starting place?

It connects Player Quality to Club Form without pretending that a dated squad
snapshot is a confirmed matchday lineup. It contains no opponent, market, goal
probability, or capital decision.

## Source boundary

FotMob match cards expose declared starters, lineup positions, formations, and
player minutes. The normalized player-match row preserves all four fields.
Only a declared starter flag counts as a start; minutes never infer starter
status.

The layer also consumes:

- current FotMob squad identity and injury flags;
- completed current competitive player-match rows;
- detailed preseason player-match rows;
- previous-season workload from Player Quality v2;
- Alpha Ability as attached context only.

Rows after the inclusive `as_of` date are rejected.

## Recent evidence

Current competitive matches have full weight. Preseason has one-quarter weight.
Both decay with a 30-day half-life:

```text
match_weight = source_weight × 0.5 ** (age_days / 30)
```

For each player, weighted minutes and declared starts are accumulated. Recent
minutes are normalized into a 990-minute team distribution. Previous-season
minutes for the current squad create a separate 990-minute workload
distribution.

## Conservative workload prior

Previous-season workload contributes the equivalent of two matches:

```text
recent_strength     = sum(recent match weights)
historical_strength = 2 when historical squad minutes exist

baseline_minutes =
    (recent_distribution × recent_strength
     + historical_distribution × historical_strength)
    / (recent_strength + historical_strength)
```

Each team distribution sums to 990 minutes. This is an opportunity prior, not
a promise that the selected eleven will each play 90 minutes. Substitutes retain
their share of the total.

If neither recent nor historical evidence exists, the layer does not create a
lineup from Alpha Ability. Provider-side squad gaps remain empty.

## Shape and XI

The latest complete declared XI supplies the formation and the number of Alpha
role slots actually used by that team. This keeps the locked position mapper:
wing-backs such as Dimarco remain fullbacks, and CAMs remain in the forward
Alpha population even when the tactical formation labels them as midfielders.

When no complete usable XI exists, the transparent fallback is:

```text
GK 1 · CB 2 · FB 2 · CM 3 · FW 3
```

Players are selected within those role slots by expected-minute evidence,
declared-start rate, and previous-season workload. Alpha Ability is not a
selection input.

## Availability

- `unavailable`: removed from the adjusted minute prior;
- `questionable`: retained and flagged;
- `unknown`: retained and flagged;
- no injury: available.

Removed opportunity is redistributed to available players, first within the
same Alpha role and then across the eligible squad if a role has no cover. This
changes expected opportunity, not Performance Form or team strength.

## Outputs

```text
data/processed/squad_selection_prior/
├── squad_selection_prior.jsonl
└── manifest.json

reports/squad-selection-prior-v1-audit.json
```

Run:

```bash
python3 scripts/build_squad_selection_prior.py
```

## First real-data audit

The 2026-08-18 snapshot contains:

- 58 target teams and 1,407 normalized squad players;
- 55 complete baseline XI priors;
- 38 teams with recent detailed player evidence;
- 37 teams with at least one exact declared recent XI;
- 77 known unavailable and 61 questionable players;
- zero unavailable players selected in a baseline XI;
- zero future-match leakage.

NK Celje, Sabah FK, and Shakhtar Donetsk have no FotMob squad page in this
snapshot. Their empty priors are correct missing data, not zero-quality squads.

## Decision boundary

The layer is not fixture-specific and is never marked projection-ready. Before
goalscorer, assist, or team-goal probabilities can use expected minutes, a later
fixture layer must add the opponent, current team news, likely rotation, and a
confirmed or fixture-specific expected XI.
