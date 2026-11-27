# Adaptive learning loop

Status: research-only challenger layer

The adaptive loop improves Clubalpha's memory without allowing a completed
match to rewrite the Holy Grail architecture. Every completed frozen fixture
produces one append-only Match Learning Card. The cards are then folded into
three memory horizons and a chronological challenger replay.

## Immutable boundaries

- Player Alpha formulas do not update automatically.
- The 60% Club Form / 30% projected-XI Player Alpha / 10% historical residual
  base does not update automatically.
- Frozen predictions and results are never rewritten.
- A challenger cannot promote itself.
- Research evidence cannot authorize capital.

## Scheduled research passes

The recurring research pass is separate from the paper settlement job. Reuse
the existing collectors and forecast builders, and skip rebuilds if their
inputs and the fixtures in scope have not changed. For a narrow FotMob refresh:

```bash
python3 scripts/pull_fotmob_foundation.py --refresh-current-leagues \
  --as-of YYYY-MM-DD --audit /path/to/a/new/dated/foundation-coverage.json
```

The refresh reuses older match, preseason and leaderboard data. Refresh team
availability and current foreign-league evidence separately when needed for a
forecast. Use completed UCL matches as tagged, competition- and opponent-
adjusted Club Form evidence. Lineups and minutes can inform selection and
short-rest context, but UCL outcomes never enter the Premier League
calibration or accuracy ledger. Fixtures without an archived pre-kickoff
forecast are observational only.

Freeze the next PL and UCL forecast before kickoff in a dated archive. Capture
timestamped public price snapshots separately, without inferring missing
quotes. Score 1X2 and O/U 2.5 by competition against historical or naive
baselines and the saved market consensus where available. Use probability
scores and calibration as well as hit rate. Track closing-price comparisons
only when comparable closing quotes exist. Leave paper accounting to its
existing settlement task. Do not merge, deploy, promote the champion or place
trades as part of the research pass.

## Match Learning Card

Each card stores:

1. The exact pre-match xG, probabilities and contextual route evidence.
2. The score, observed xG, process winner and actual lineup.
3. Separate 1X2, total-goals, xG and lineup diagnostics.
4. A primary error attribution plus secondary review flags.
5. Evidence-quality weights for process and outcome learning.
6. Per-team signals for fast, medium and slow memory.

The primary attribution can be lineup projection, match-state disruption,
outcome variance, draw calibration, archetype context, club form/team strength,
or model supported. A scoreline can therefore be wrong without teaching the
strength model the wrong lesson.

## Memory horizons

- **Fast — seven-day half-life:** projected-XI reliability and formation
  persistence. This layer reacts quickly and expires quickly.
- **Medium — 28-day half-life:** attack creation, defensive exposure and goal
  environment relative to the frozen forecast.
- **Slow — 120-day half-life:** structural team-quality review. It requires at
  least eight matches and cannot rewrite Player Alpha.

All residuals are shrunk toward neutral. Reliability, recency, rotation and
available match-state evidence control how much a fixture is allowed to teach.

## Champion versus challenger

The current Holy Grail contextual forecast remains the champion. The first
challenger applies bounded, evidence-shrunk medium-memory residuals to future
xG only after both teams have sufficient prior matches. Evaluation is strictly
chronological: a match never helps predict itself.

Promotion requires the configured validation sample, improvements in side-xG
MAE and 1X2 Brier score, no material totals regression, and explicit human
review. Until every gate passes, the champion remains untouched.

## Current checkpoint

Run:

```bash
python3 research/run_research_loop_v1.py --as-of YYYY-MM-DD
```

The checkpoint writes `state.json`, `report.md`, and
`match-learning-cards.jsonl` beneath `artifacts/research_loop/`. Existing
checkpoint files are immutable: rerunning the same path must reproduce the
same bytes or fail.

## Archetype matchup memory

Run:

```bash
python3 research/build_archetype_memory_v1.py \
  --as-of YYYY-MM-DD \
  --cards artifacts/research_loop/CHECKPOINT/match-learning-cards.jsonl \
  --output-dir artifacts/archetype_memory/YYYY-MM-DD
```

The archetype memory derives two team-perspective observations from every
completed Match Learning Card and keeps three ledgers separate:

1. Direct opponent history.
2. Team versus opponent-archetype history.
3. League-wide archetype versus archetype history.

xG process, forecast residual, lineup accuracy, preferred route and W-D-L are
retained together so a finishing outlier does not become a false tactical
lesson. Fewer than three comparable matches are descriptive, three to four
are tentative, five to seven are challenger-eligible, and eight or more may
enter human promotion review. The ledger has zero live weight and cannot
rewrite Player Alpha, Club Form, probabilities or capital authorization.
