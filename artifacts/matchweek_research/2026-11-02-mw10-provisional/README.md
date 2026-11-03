# Matchweek 10 provisional research slate

Prepared: 2026-11-02  
First kickoff: 2026-11-06  
Status: provisional shadow; final refresh required after the November 3–5
European fixtures; no capital authorization

## Evidence refresh

- All 90 completed Premier League matches are present in the foundation.
- Player Quality v2 retains 1,051 grades after restoring the complete cached
  historical player layer.
- Club Form and Club Dynamics use 4,686 normalized team-match rows across
  2,343 finished matches.
- Projected-XI Player Alpha covers all 20 Premier League clubs and uses only
  past selection evidence through November 2.
- The 80-match calibration and 80-card adaptive-learning checkpoint remain
  downstream research layers; no challenger was automatically promoted.

## Provisional slate

| Fixture | H | D | A | xG | 1X2 | O/U 2.5 |
|---|---:|---:|---:|---:|---|---|
| Everton–Coventry | 47.2% | 29.1% | 23.7% | 1.56–1.02 | Pass | Pass |
| Leeds–Tottenham | 35.5% | 31.3% | 33.3% | 1.22–1.18 | Pass | **Under 2.5 · 58.2%** |
| Arsenal–Hull | 60.7% | 25.3% | 14.0% | 1.86–0.77 | **Arsenal** | Pass |
| Fulham–Newcastle | 43.5% | 29.5% | 27.0% | 1.50–1.13 | Pass | Pass |
| Nottingham Forest–Manchester City | 28.6% | 28.9% | 42.5% | 1.18–1.51 | Pass | Pass |
| Brighton–Brentford | 44.7% | 28.7% | 26.6% | 1.60–1.17 | Pass | Pass |
| Crystal Palace–Liverpool | 27.5% | 28.3% | 44.2% | 1.22–1.61 | Pass | Pass |
| Ipswich–Bournemouth | 26.5% | 28.6% | 44.9% | 1.17–1.60 | Pass | Pass |
| Sunderland–Chelsea | 33.6% | 29.4% | 36.9% | 1.33–1.41 | Pass | Pass |
| Manchester United–Aston Villa | 39.7% | 29.0% | 31.3% | 1.50–1.30 | Pass | Pass |

Arsenal is the sole side that clears the football decision gate. Club Form,
projected-XI Player Alpha and context align, but the 60.7% model probability is
well below the captured 85-cent best ask. It is an accuracy call, not a price
edge.

Leeds–Tottenham Under 2.5 is the only football call that also clears the
five-point price gate: 58.2% model probability versus a 52-cent best ask, a
provisional +6.2 percentage-point discrepancy. It remains a zero-capital
shadow watch until the final refresh and later closing-price audit.

## Refresh gate

Nine clubs have a European match before Matchweek 10: Arsenal, Aston Villa,
Liverpool, Manchester City, Manchester United, Bournemouth, Brighton,
Crystal Palace and Sunderland. Their latest minutes, availability and lineup
evidence must be ingested after November 5. The final packet must be stored as
a new artifact; these probabilities must never be overwritten.

## Canonical evidence

- `decisions.json`: calibrated selective decisions and refresh gate.
- `../../current_matchweek/2026-11-02-mw10-provisional/`: locked 60/30/10 base.
- `../../contextual_interaction/2026-11-02-mw10-provisional/`: opponent context.
- `../../prematch_load/2026-11-02-mw10.json`: workload and pending fixtures.
- `../../style_matchup/2026-11-02/style-matchups.json`: tactical routes.
- `../../market_snapshots/2026-11-02-mw10-provisional-polymarket.json`: read-only executable prices.
- `../../../reports/premier-league-alpha-snapshot-2026-11-02.json`: projected-XI Player Alpha.

The market collector is read-only, uses no wallet or credentials and cannot
place orders. Real allocation remains 0.00u.
