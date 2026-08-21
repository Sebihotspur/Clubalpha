# Club Form v1

## Purpose

Club Form answers one question:

> What condition is this club in now?

It is the fast-moving partner to Player Quality. Player Quality estimates what
the squad can do; Club Form estimates what the team has recently been doing.
Neither layer contains the next opponent, market prices, or a betting decision.

## Inputs

Club Form v1 consumes only the existing FotMob foundation:

- previous-season domestic matches for every target club;
- previous-season Premier League and Champions League matches;
- completed current competitive matches;
- 2026 preseason friendlies;
- the dated FotMob injury snapshot;
- Alpha Ability Grades, used only to describe the quality of injured players.

The foundation and domestic collectors materialize one normalized row for each
team in every match. Older snapshots that predate this handoff can still build
from cached match cards, but refreshed pipelines never make the scoring layer
read raw provider JSON.

## Attack and defence

Every match has four flat attacking characteristics:

1. Goals
2. Expected goals
3. Shots on target
4. Big chances

For each characteristic, the team is compared with match-team peers from the
same competition. The Champions League and its current qualifying matches use
one continental peer group; preseason has its own peer group.

```text
metric_z = (team_value - competition_mean) / competition_sample_sd

match_attack_z  = mean(available attacking metric_z values)
match_defence_z = mean(inverted opponent metric_z values)
```

Missing does not mean zero. A score-only friendly supplies goals but not xG,
shots on target, or big chances, so it retains one-quarter metric coverage and
substantially less evidence than a detailed match.

Total shots and touches in the opposition box are preserved as diagnostics but
do not yet enter the score. Adding correlated metrics without validation would
only create hidden weighting.

## Opponent adjustment

A good performance against a strong opponent should count more. For every
match, Club Form estimates the opponent's attack and defence from its other
matches in the same competition group.

```text
opponent_baseline = other_match_mean × n / (n + 5)

adjusted_attack  = match_attack  + opponent_defence_baseline
adjusted_defence = match_defence + opponent_attack_baseline
```

The current match is excluded, the baseline is shrunk toward neutral with a
five-match prior, and the maximum adjustment is 0.75 z. Opponents appearing in
only one selected domestic match therefore receive no artificial strength.

This is schedule adjustment, not historical matchup analysis. Style clashes,
head-to-head effects, and fixture-specific context remain in Historical
Fixtures.

## Recency and preseason

Competitive evidence has full source weight. Preseason starts at 0.25.

```text
recency_weight = 0.5 ** (age_days / 60)
match_weight   = recency_weight × source_weight
```

Preseason can never exceed 20% of a club's total match weight when competitive
history exists. This allows new roles and tactical changes to show without
letting a friendly against a weak opponent erase a competitive season.

Current competitive, previous competitive, preseason, home competitive, and
away competitive results remain visible as separate breakdowns.

## Coverage and reliability

Metric coverage multiplies each match's weight. A dimension's evidence is the
sum of its coverage-adjusted match weights.

```text
confidence = evidence / (evidence + 5)
final_z    = target_universe_z × confidence
```

The unshrunk club aggregates are standardized across the current PL/UCL target
universe. Reliability then pulls low-evidence clubs toward neutral. Attack and
defence keep separate confidence values.

## Availability boundary

FotMob injury flags are classified conservatively:

- dated expected returns are `unavailable`;
- `Doubtful`, `Day to day`, and `Back in training` are `questionable`;
- the associated Alpha Ability Grade is shown when available.

Availability does **not** modify the Performance Form score. In the separate
Squad Selection Prior, a known unavailable player can receive zero expected
minutes and their opportunity can be redistributed within the squad. This
still does not create a team-strength modifier: player impact requires a
fixture-specific lineup and later validation. Questionable and unknown cases
are never silently treated as unavailable.

## Time integrity

The build accepts an inclusive `--as-of` date and rejects later matches. The
foundation can retain already-known future schedules, but it clears any later
score or finished status when recreating an earlier snapshot. Opponent
baselines also exclude the match currently being scored.

These two rules make the layer usable for future walk-forward evaluation.

## Outputs

```text
data/processed/club_form/
├── team_match_observations.jsonl
├── club_form.jsonl
└── manifest.json

reports/club-form-v1-audit.json
```

Provider rows and calculated rows remain ignored by Git. The compact audit is
tracked.

Run:

```bash
python3 scripts/build_club_form.py
```

### Joined Club Form Snapshot

After Club Dynamics and the Squad Selection Prior are built, one non-blended
team record joins Performance Form, Club Dynamics, Availability, and selection
evidence:

```bash
python3 scripts/build_club_form_snapshot.py
```

```text
data/processed/club_form_snapshot/
├── club_form_snapshot.jsonl
└── manifest.json

reports/club-form-snapshot-v1-audit.json
```

The join requires identical team universes, team names, and `as_of` dates. It
does not calculate a combined score. Every record explicitly states that
Dynamics and Availability do not change Performance Form and lists the missing
requirements for fixture-level projections.

The 2026-08-18 selection snapshot produces 55 complete XI priors from 58 clubs.
Thirty-eight clubs have recent player-match detail and 37 have at least one
exact FotMob-declared lineup. NK Celje, Sabah FK, and Shakhtar Donetsk remain
empty because FotMob supplied no current squad page; the model does not invent
their players.

## First real-data audit

The 2026-08-18 snapshot produces:

- 58 of 58 target clubs with a form profile;
- 2,144 finished matches and 4,288 team-match observations;
- 100% goals coverage;
- 79.5% xG coverage;
- 92.1% shots-on-target coverage;
- 89.1% big-chance coverage;
- zero missing cached match cards after current-match automation was added.

## Deliberately deferred

- fixture-specific lineups and locked expected minutes;
- World Cup workload and recovery;
- style matchup and head-to-head evidence;
- conversion of Club Form into goal probabilities.

Manager identity, confirmed transfers, integration, tactical style, and team
strengths/weaknesses are now surfaced by [Club Dynamics v1](club-dynamics-spec.md).
They remain separate from this performance score until predictive validation.

Those are additions to the foundation, not reasons to hide assumptions inside
v1.
