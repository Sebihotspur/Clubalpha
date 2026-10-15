# Matchweek 6 preparation packet

Prepared: 2026-10-06  
First kickoff: 2026-10-10  
Status: preweek shadow research; not the final lineup freeze and not a capital recommendation

## Evidence used

- Club Form uses every completed Premier League match from Matchweeks 1–5.
- Forecast-error learning uses 40 immutable pre-match forecasts from
  Matchweeks 2–5. Matchweek 1 contributes football evidence but is excluded
  from calibration because no frozen forecasts existed.
- Projected-XI Player Alpha is refreshed from current club appearances.
  International appearances enter only the separate workload/lineup review.
  Prior-season grading formulas and the 60% Form / 30% projected-XI Alpha / 10%
  Historical base remain locked.
- Venue/draw calibration is a 40-match shadow challenger. Its 15/40 observed
  draw rate is unusually high, so it may gate confidence but is not trusted as
  a standalone edge.
- Archetype memory contains 80 team-side observations. No matchup has reached
  the five-match challenger threshold, so it explains or weakens confidence
  without changing probabilities.
- The read-only Polymarket comparison was captured at
  2026-10-06T15:58:11Z. Prices will move and are not an authorization to trade.

## Provisional slate

“Football” is the contextual Holy Grail forecast. “Calibrated” applies the
small-sample venue/draw challenger downstream. The research verdict requires
agreement between the two before a side can be shortlisted.

| Fixture | Football H-D-A | Calibrated H-D-A | Provisional leader | Research verdict | O/U 2.5 | XI load |
|---|---:|---:|---|---|---|---|
| Arsenal–Leeds | 57-23-19 | 49-31-20 | Arsenal | Medium shortlist | Under 53% | High / High |
| Aston Villa–Brentford | 39-24-37 | 32-32-36 | Split | Pass | Over 56% | High / High |
| Chelsea–Bournemouth | 39-24-37 | 33-31-37 | Split | Pass | Over 58% | Medium / Low |
| Ipswich–Fulham | 44-24-32 | 37-32-31 | Ipswich | Low upset lean | Over 54% | Medium / High |
| Sunderland–Brighton | 36-24-40 | 31-30-39 | Brighton | Low away lean | Over 59% | Medium / High |
| Manchester United–Tottenham | 58-22-20 | 50-30-20 | Manchester United | Medium; cleanest 1X2 | Over 52% | Medium / Medium |
| Crystal Palace–Nottingham Forest | 37-26-37 | 31-33-36 | Forest by a sliver | Pass | Under 51% | Medium / Medium |
| Hull–Everton | 36-27-37 | 30-34-36 | Everton | Medium shortlist | Under 56% | Medium / Low |
| Liverpool–Manchester City | 37-25-38 | 31-32-38 | Manchester City | Pass | Over 53% | Medium / Medium |
| Coventry–Newcastle | 43-25-32 | 36-33-32 | Coventry | Low upset lean | Over 51% | Medium / Low |

Percentages are rounded; rows may not display as exactly 100 because of
rounding.

## What the first five matchweeks change

1. **Manchester United is the cleanest result call, not the cleanest price.**
   Both probability layers agree, and projected-XI Alpha ranks United third
   versus Tottenham fifteenth. The market ask near 58% was richer than the
   calibrated 50%, so this is an accuracy shortlist rather than a value claim.
2. **Everton is the clearest matchup-supported secondary lean.** Hull ranks
   twentieth in projected-XI Alpha, carries more load risk, and is 0-1-1 with a
   negative 0.58 xG differential in its first two descriptive matches against
   adaptive-hybrid opponents. The sample is too small for an automatic modifier.
3. **Ipswich and Coventry are useful contrarian tests.** Club Form plus venue
   makes each the model leader while the market prefers the higher-Alpha away
   team. These should be archived as learning cases, not upgraded because the
   prices look attractive.
4. **Villa–Brentford and Chelsea–Bournemouth are deliberate passes.** The
   football layer and the venue/draw challenger reverse the side leader. That
   is unresolved model uncertainty, not hidden conviction.
5. **The best totals research case is Sunderland–Brighton Over 2.5.** The
   calibrated model is 59% versus a 54% ask, while four-match memory flags both
   Sunderland and Brighton as higher-tempo environments than expected. Heavy
   Brighton load and the still-compressed total-xG model keep it shadow-only.

## Market observations, not bets

- Arsenal is a football shortlist but the 72% home ask is substantially above
  the calibrated 49% probability; no price edge is claimed.
- Manchester United is the strongest side call, but the 58% home ask is above
  the calibrated 50% probability.
- Bournemouth, Ipswich and Coventry display the largest side-price conflicts.
  They are diagnostic opportunities for calibration, not deployment signals.
- The market expects substantially more goals than Clubalpha in United–Spurs
  and Liverpool–City. Because total-goal dispersion is still the model's
  weakest structural area, those apparent Under edges stay on the watchlist.

## Final-freeze checklist

- Refresh any later October 6 internationals, then injuries, suspensions and
  expected XIs before the final freeze.
- Recheck Arsenal, Villa, Brentford, Brighton, Fulham and Leeds because their
  projected-XI load is high.
- Verify price, spread, available depth and settlement terms at the actual
  decision time.
- Freeze a new dated slate; never overwrite this packet.
- Keep capital deployment disabled.

Canonical machine-readable inputs:

- `artifacts/current_matchweek/2026-10-06-mw6/predictions.jsonl`
- `artifacts/contextual_interaction/2026-10-06-mw6/predictions.jsonl`
- `artifacts/fixture_calibration/2026-10-06/calibration.json`
- `artifacts/archetype_memory/2026-10-06/memory.json`
- `artifacts/prematch_load/2026-10-06-mw6.json`
- `artifacts/market_snapshots/2026-10-06-mw6-polymarket.json`
