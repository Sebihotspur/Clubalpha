# Matchweek 5 evidence refresh

Built: 2026-09-16

This is a pre-kickoff research refresh of the September 15 Matchweek 5 draft.
It does not overwrite that draft, create an official ledger cycle, or authorize
capital deployment.

## Evidence added

- 33 completed domestic-league fixtures for foreign UCL clubs were added to
  the shared current-season form, dynamics, history, and lineup evidence.
- Seven completed EFL Cup fixtures involving current Premier League clubs and
  Sunderland's completed Europa League fixture were added to current squad
  selection evidence.
- Slavia Prague's and Slovan Bratislava's completed domestic-cup match cards
  were cached for their future UCL lineup projections.
- Cup and Europa appearances are cross-competition evidence. Squad Selection
  v2 discounts them to 0.75 of same-competition evidence and suppresses the
  latest-XI persistence bonus on the switch back to the Premier League.
- Rotated cup scorelines do not enter the Premier League ledger, PL fixture
  calibration, or the locked Player Alpha formula.

The current foreign-domestic layer now contains 175 completed fixtures, up
from 142. Player-level detail is available for 165/175 (94.3%). The Premier
League projected-XI runner now sees 72 current-season matches, up from 64.

## Calibrated forecast comparison

The same September 15 fixture-calibration artifact was applied to both runs so
the comparison isolates refreshed football evidence. Percentages below are
the probability of the listed direction after context and calibration.

| Fixture | Sep 15 direction | Sep 15 | Sep 16 direction | Sep 16 | O2.5 Sep 15 | O2.5 Sep 16 |
|---|---|---:|---|---:|---:|---:|
| Brentford–Chelsea | Brentford | 36.7% | Brentford | 36.9% | 61.9% | 61.4% |
| Tottenham–Aston Villa | Tottenham* | 36.6% | Tottenham* | 36.2% | 45.9% | 44.8% |
| Brighton–Arsenal | Arsenal | 37.3% | Arsenal | 36.5% | 52.5% | 51.8% |
| Everton–Ipswich | Everton | 39.3% | Everton | 39.7% | 52.0% | 51.5% |
| Newcastle–Hull | Newcastle | 39.7% | Newcastle | 39.5% | 49.8% | 49.0% |
| Nottingham Forest–Coventry | Forest | 40.8% | Forest | 39.9% | 46.4% | 45.6% |
| Bournemouth–Liverpool | Bournemouth* | 36.4% | Bournemouth* | 37.0% | 53.1% | 52.6% |
| Leeds–Crystal Palace | Leeds | 45.8% | Leeds | 46.0% | 57.0% | 56.5% |
| Manchester City–Sunderland | Manchester City | 53.3% | Manchester City | 53.0% | 51.5% | 50.7% |
| Fulham–Manchester United | Manchester United | 42.1% | Manchester United | 42.5% | 53.2% | 52.7% |

`*` The raw model leader is shown. The September 15 research draft selected a
draw for Tottenham–Villa and Bournemouth–Liverpool inside the existing draw
review zone. The refreshed gaps remain close enough that neither override is
automatically removed.

No probability leader changed. The largest 1X2 movement was under one
percentage point, which is the desired response to heavily rotated cup games.
Brentford–Chelsea remains primarily an over research case rather than a strong
winner case; Leeds–Palace remains the second totals shortlist.

## Remaining pre-release checks

- Manchester City still plays Norwich in the EFL Cup on September 17.
- Bournemouth and Crystal Palace still have European matches on September 17.
- Refresh actual minutes, availability, and projected XIs after those matches.
- Preserve the September 15 draft and this refresh; any official MW5 slate must
  be a new immutable archive created before the first league kickoff.
