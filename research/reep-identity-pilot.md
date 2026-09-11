# REEP identity pilot

## Purpose

REEP is an identity register, not a performance model. This pilot asks one
narrow question: how much of Clubalpha's current Premier League and Champions
League universe can the frozen public FotMob bridge resolve exactly?

It does not change Player Quality, Squad Form, or Historical Fixtures. FotMob
IDs remain Clubalpha's operational keys.

## Why v0 is treated as a seed

The GitHub repository is the frozen `2026.25` v0 release. It contains FotMob
player and team mappings, but stopped updating in June 2026. Current REEP v1 is
free and CC0, but its published provider coverage does not currently expose a
first-class FotMob bridge, and v0 IDs are not interchangeable with v1 IDs.

The pilot therefore uses v0 only to attach candidate provider cross-references
to an already-known FotMob ID. Its Transfermarkt bridge is then resolved through
the typed `spieler` or `verein` namespace in a pinned v1 snapshot. The v0 Reep
ID is never carried forward as a v1 identity.

## Safety rules

- Exact FotMob ID only. Names can flag a difference but cannot create a match.
- A conflicting date of birth quarantines a player row.
- A duplicated FotMob bridge is ambiguous and never resolves silently.
- Every output records the pinned source commit and release.
- Raw REEP files and derived crosswalks stay ignored by Git.
- Only the compact coverage audit is tracked.

## Run

```bash
python3 scripts/audit_reep_identity.py
```

The script downloads the required v0 CSV files plus the v1 bridges, entities,
and redirect ledger into `data/cache`, resolves current foundation players and
teams, and writes:

- `data/processed/identity/player_crosswalk.jsonl`
- `data/processed/identity/team_crosswalk.jsonl`
- `reports/identity-coverage.json`

The crosswalk is an optional validation surface. No runtime Clubalpha component
may require REEP coverage to grade a player or load a fixture.

## Measured result

The 21 August 2026 audit found:

| Scope | Current v1 players | Player coverage | Current v1 teams | Team coverage |
|---|---:|---:|---:|---:|
| Full PL/UCL universe | 707 / 1,425 | 49.6% | 36 / 58 | 62.1% |
| Premier League | 356 / 581 | 61.3% | 17 / 20 | 85.0% |
| UCL direct entrants | 416 / 738 | 56.4% | 22 / 29 | 75.9% |
| UCL play-off field | 37 / 250 | 14.8% | 2 / 14 | 14.3% |

Of 716 player rows eligible for the Transfermarkt handoff, 707 resolved in the
current v1 register: 98.7% of the eligible subset. No duplicate FotMob IDs or
date-of-birth conflicts were observed. Fifty-seven exact provider-ID matches
had different displayed names, primarily short names versus full legal names;
they remain flagged for review rather than being used as matching evidence.

The result supports a **selective validator**, not a universal identity spine.
It is useful for cross-source checks on the covered subset, especially Premier
League clubs, while FotMob remains canonical and every uncovered entity keeps
working normally.
