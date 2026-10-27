# Matchweek 9 provisional research slate

Status: provisional shadow, built from evidence available through 2026-10-26.

This slate is deliberately not final. Thirteen participating clubs have EFL
Cup fixtures from October 27–29, so the final lineup, availability, workload and
form refresh must run after the last cup match. Real capital remains
unauthorized.

## Decision policy

- Strong side: at least 55% win probability and a 15-point separation.
- Medium side: at least 45%, a 10-point separation, reliable projected lineups,
  supportive context, and agreement from Club Form and projected-XI Player
  Alpha.
- Draw-zone, model-layer disagreement, or a leader below 45% forces a pass.
- Total: Over 2.5 at 58% or higher; Under 2.5 at 58% or higher; otherwise pass.
- A provisional direction is not final-call eligible while a participating
  club has a pending preleague fixture.

## Provisional predictions

| Fixture | H | D | A | xG | 1X2 | O/U 2.5 |
|---|---:|---:|---:|---:|---|---|
| Chelsea–Manchester United | 37.4% | 29.7% | 32.9% | 1.43–1.34 | Pass | Pass |
| Bournemouth–Leeds | 44.0% | 30.4% | 25.6% | 1.50–1.08 | Pass | Pass |
| Brentford–Nottingham Forest | 36.4% | 30.4% | 33.2% | 1.38–1.31 | Pass | Pass |
| Coventry–Sunderland | 36.9% | 31.4% | 31.7% | 1.32–1.21 | Pass | Pass |
| Hull–Ipswich | 33.5% | 29.9% | 36.6% | 1.34–1.42 | Pass | Pass |
| Manchester City–Brighton | 44.7% | 27.7% | 27.6% | 1.76–1.33 | Pass | **Over 2.5 · 58.1%** |
| Tottenham–Crystal Palace | 45.1% | 30.0% | 24.9% | 1.57–1.10 | Pass | Pass |
| Aston Villa–Fulham | 39.4% | 30.9% | 29.7% | 1.39–1.18 | Pass | Pass |
| Liverpool–Arsenal | 29.6% | 32.7% | 37.7% | 1.08–1.26 | Pass | **Under 2.5 · 60.0%** |
| Newcastle–Everton | 34.8% | 30.0% | 35.2% | 1.37–1.37 | Pass | Pass |

The refusal result is meaningful: no side currently satisfies every
probability, separation, foundation-support, context and lineup gate. The two
totals above are an accuracy shortlist, not allocations.

## Final-refresh gate

Refresh after the October 29 cup slate, rebuild the projected XIs, and compare
the final output against this artifact. Never overwrite these provisional
probabilities. The final runner must refuse to freeze if any preleague fixture
is still pending.

## Canonical artifacts

- `decisions.json`: flattened side and totals decisions.
- `../../current_matchweek/2026-10-26-mw9/`: base simulation inputs and output.
- `../../contextual_interaction/2026-10-26-mw9/`: matchup-context simulation.
- `../../prematch_load/2026-10-26-mw9.json`: workload and pending-fixture audit.
- `../../style_matchup/2026-10-26/style-matchups.json`: current tactical routes.
- `../../../reports/premier-league-alpha-snapshot-2026-10-26.json`: projected-XI Player Alpha.
