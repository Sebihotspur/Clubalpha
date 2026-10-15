# Matchweek 6 settlement review

Settled: 2026-10-15  
Status: research shadow; excluded from the official capital gate

## Scorecard

- Advertised 1X2 calls: 5/10.
- Advertised O/U 2.5 calls: 5/10.
- Base 1X2 probability leaders: 7/10.
- Holy Grail contextual 1X2 leaders: 6/10.
- Side shortlist: 1/3.
- Totals shortlist: 0/1.
- Combined higher-conviction shortlist: 1/4.

## What worked

- Arsenal, Ipswich, Brighton, Manchester City and Coventry were correct 1X2 calls.
- Villa–Brentford, Chelsea–Bournemouth, Ipswich–Fulham, Liverpool–City and
  Coventry–Newcastle were correct totals directions.
- Projected lineups averaged 9.05 correct starters from 11 and formations were
  correct for 18 of 20 teams. Data coverage and lineup projection were not the
  main cause of the misses.
- The low-confidence Ipswich and Coventry upset leans both won. These remain
  useful evidence, not proof that low-confidence contrarian picks should be
  promoted automatically.

## What failed

- The final calibration/context translation reduced the base model from 7/10
  to the advertised 5/10. The base model preferred Chelsea; changing the final
  call to Bournemouth cost one hit. Villa remained a miss either way.
- The higher-conviction ordering failed: Manchester United drew, Everton drew,
  and Sunderland–Brighton stayed Under. Arsenal was the only shortlist hit.
- Manchester United–Tottenham was the only structural miss: Tottenham won xG
  1.62–0.80. Villa–Brentford, Palace–Forest and Hull–Everton were result misses
  whose xG process still supported the predicted side.
- Total-xG dispersion remains compressed. Observed match xG ranged from 2.13
  to 5.75 while contextual forecasts ranged only from 2.51 to 3.17.

## Learning decision

Do not loosen the capital gate. Preserve the 60/30/10 foundation and Player
Alpha. The immediate research priority is confidence calibration: require the
downstream context/calibration layer to prove incremental value over the base
before it may reverse a base leader or elevate a shortlist. The adaptive
challenger still worsens both xG MAE and 1X2 Brier over chronological
validation, so the champion remains unchanged.
