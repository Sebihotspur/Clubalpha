# Next session

Updated: 2026-08-24

Working branch: `codex/club-form-v1`

Draft PR: [#6 — Build Club Form intelligence and squad selection priors](https://github.com/Sebihotspur/Clubalpha/pull/6)

## Start here

1. Perform the final review of the August 24 Squad Selection corrections.
   - Re-run the 83-test suite: `python3 -m unittest discover -s tests`.
   - Confirm no player exceeds 90 expected minutes and every usable team totals 990.
   - Confirm tactical selection roles remain separate from locked Alpha grading positions.
   - Confirm partial recent and historical evidence reduces prior strength.
   - Confirm `Unknown` injury text remains unknown rather than becoming a hard exclusion.
   - Reinspect Arsenal, Chelsea, Manchester City, Coventry City, and Shakhtar Donetsk.
2. If the final audit is clean, mark PR #6 ready and merge it into `main`.
3. Create a new branch from the updated `main` for Fixture Intelligence v1.

## Current Club Form checkpoint

- Performance Form: 58/58 clubs.
- Style and strengths/weaknesses: 56/58 clubs.
- Complete baseline XI priors: 55/58 clubs.
- Recent detailed player evidence: 38 clubs.
- Exact recent declared XI evidence: 37 clubs.
- Squad players: 1,407.
- Availability: 75 unavailable, 61 questionable, and 2 explicitly unknown.
- Selection shapes: 37 exact recent lineups and 21 transparent default shapes.
- Evidence controls: 14 teams carry partial recent-minute coverage and one carries partial historical-workload coverage.
- Safeguards: no player exceeds 90 expected minutes, no unavailable player is selected, usable team priors total 990 minutes, and no future-match leakage.
- Explicit FotMob squad-page gaps: NK Celje, Sabah FK, and Shakhtar Donetsk.
- The joined snapshot intentionally remains `projection_ready=false`.

## Keep outside PR #6

Do not add fixture-specific expected lineups or minutes, opponent matchup logic, fresh team news, probabilities, market prices, or capital deployment rules to this PR. Club Form is complete at its current boundary.

## Fixture Intelligence v1 — first scope

Build the next layer around a selected fixture:

1. fixture and opponent identity;
2. home/away context;
3. tactical style matchup;
4. fresh team news and rotation context;
5. fixture-specific expected XI;
6. expected-minute scenarios for questionable players.

Its eventual handoff should be:

```text
Player Quality × Expected Minutes × Fixture Context
```

Only after walk-forward validation should that feed goalscorer, assist-maker, team-goal, over/under, and capital-deployment probabilities.
