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
minutes are converted into a 990-minute team distribution, with every player
constrained to the physical 0–90 range. A match's evidence strength is
multiplied by the share of its 990 current-squad minutes that was actually
observed. Previous-season minutes for the current squad create a separate,
coverage-aware workload distribution.

## Conservative workload prior

Previous-season workload contributes the equivalent of two matches:

```text
match_minute_coverage = observed current-squad minutes / 990
recent_strength       = sum(match weight × match minute coverage)

historical_coverage = min(players with workload / 11, 1)
historical_strength = 2 × historical_coverage

baseline_minutes =
    (recent_distribution × recent_strength
     + historical_distribution × historical_strength)
    / (recent_strength + historical_strength)
```

Each usable team distribution sums to 990 minutes, while no player can exceed
90. If partial evidence covers too few players, the known leaders reach their
physical cap and residual opportunity is distributed neutrally rather than
inflating one player into the missing team. Substitutes retain their share of
the total.

If neither recent nor historical evidence exists, the layer does not create a
lineup from Alpha Ability. Provider-side squad gaps remain empty.

## Shape and XI

The latest complete declared XI supplies the formation and tactical selection
slots from FotMob's lineup-position IDs. Tactical selection role and Alpha
grading position are deliberately separate: Dimarco can be a tactical
midfielder or wing-back while remaining a fullback in the locked Alpha formula;
a CAM can occupy a midfield selection slot while remaining in the Alpha forward
population.

When no complete usable XI exists, the transparent fallback is:

```text
GK 1 · DEF 4 · MID 3 · FWD 3
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
same tactical selection role and then across the eligible squad if a role has
no cover. The 90-minute cap remains enforced. This changes expected
opportunity, not Performance Form or team strength.

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
- 75 known unavailable, 61 questionable, and 2 explicitly unknown players;
- zero players above 90 expected minutes, down from 127 in the pre-merge audit;
- 14 teams whose recent evidence is discounted for partial current-squad minute coverage;
- 21 teams using the transparent default shape, exactly matching the teams without a complete recent XI;
- zero unavailable players selected in a baseline XI;
- zero future-match leakage.

NK Celje, Sabah FK, and Shakhtar Donetsk have no FotMob squad page in this
snapshot. Their empty priors are correct missing data, not zero-quality squads.

## Decision boundary

The layer is not fixture-specific and is never marked projection-ready. Before
goalscorer, assist, or team-goal probabilities can use expected minutes, a later
fixture layer must add the opponent, current team news, likely rotation, and a
confirmed or fixture-specific expected XI.
