# Matchweek 7 frozen research slate

Prepared: 2026-10-15  
First kickoff: 2026-10-17  
Status: frozen preweek shadow research; no capital authorization

## Decision policy

- The locked 60% Club Form / 30% projected-XI Player Alpha / 10% Historical
  base remains the anchor.
- Context may reinforce or weaken confidence. It cannot reverse the base leader
  in this slate.
- A side is a pass when the leading outcome is fewer than five percentage
  points clear of the runner-up.
- Over is called only at 58% or higher; Under only when Over is 42% or lower.
- Fixture Calibration remains shadow-only and cannot reverse a call.
- Market prices gate the price-aware shortlist but never train or rewrite the
  football probabilities.

## Frozen slate

| Fixture | Contextual H-D-A | 1X2 call | O/U 2.5 call | Context | Load |
|---|---:|---|---|---|---|
| Everton–Chelsea | 48.1–23.3–28.6 | Everton | Over 59.5% | Supported | Low / Low |
| Brentford–Liverpool | 39.7–24.8–35.5 | Pass; Brentford lean | Pass | No clear edge | Low / High |
| Fulham–Hull | 49.8–24.6–25.5 | Fulham | Pass | Supported | Medium / Medium |
| Manchester City–Ipswich | 65.9–18.4–15.6 | Manchester City | Over 65.9% | Reinforced | High / Medium |
| Newcastle–Aston Villa | 41.9–23.9–34.2 | Newcastle | Over 60.2% | Supported | Medium / High |
| Bournemouth–Sunderland | 48.2–24.2–27.6 | Bournemouth | Pass | Supported | Low / Low |
| Brighton–Crystal Palace | 62.8–19.0–18.2 | Brighton | Over 67.0% | Reinforced | Medium / Low |
| Leeds–Manchester United | 38.7–25.5–35.8 | Pass; Leeds lean | Pass | No clear edge | Medium / Medium |
| Nottingham Forest–Arsenal | 27.0–25.9–47.2 | Arsenal | Pass | Reinforced | Low / Medium |
| Tottenham–Coventry | 47.3–25.8–26.9 | Tottenham | Pass | Reinforced | Low / Low |

## Shortlists

Accuracy shortlist:

1. Manchester City to beat Ipswich — 65.9%.
2. Brighton to beat Crystal Palace — 62.8%.
3. Brighton–Crystal Palace Over 2.5 — 67.0%.

Price-aware shadow shortlist:

1. Everton to beat Chelsea — 48.1% model probability versus a 30% best ask.
   Everton's stronger current form and Chelsea's defensive weakness outweigh
   Chelsea's projected-XI Alpha advantage in the locked base. Both base and
   context select Everton; low load on both sides removes a scheduling excuse.

Manchester City and Brighton are the strongest result forecasts, but their win
prices are already at or above the model's probabilities. They are accuracy
tests, not price edges. Brighton–Crystal Palace Over is the best totals call,
but its 4.96-point observed edge narrowly misses the strict five-point price
gate. Tottenham–Coventry Under displays a large apparent price discrepancy,
but the model assigns Under only 52.5%; the new totals gate correctly rejects
it.

Canonical evidence:

- `artifacts/current_matchweek/2026-10-15-mw7/`
- `artifacts/contextual_interaction/2026-10-15-mw7/`
- `artifacts/prematch_load/2026-10-15-mw7.json`
- `artifacts/market_snapshots/2026-10-15-mw7-polymarket.json`
- `reports/premier-league-alpha-snapshot-2026-10-15.json`
