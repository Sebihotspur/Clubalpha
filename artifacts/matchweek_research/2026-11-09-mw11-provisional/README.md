# Matchweek 11 provisional research slate

Prepared: 2026-11-09  
First kickoff: 2026-11-21  
Status: provisional shadow; international-window and final availability refresh
required; no capital authorization

## Evidence refresh

- All 100 completed 2026/27 Premier League matches are present in the
  normalized foundation.
- The append-only learning state and fixture calibration contain 90 completed
  frozen forecasts through Matchweek 10.
- Player Quality v2 retains 1,051 grades. Projected-XI Player Alpha covers all
  20 clubs and uses only selection evidence available through November 9.
- Club Form and Club Dynamics use 4,830 team-match rows across 2,415 finished
  matches, including Premier League, UCL, current domestic, historical and
  preseason evidence.
- Historical Fixtures v2 evaluates all ten fixtures from 8,650 team-match rows;
  eight fixtures have direct-history evidence and all ten have complete
  competition baselines.
- The Matchweek 10 scoreline is not learned blindly. Sunderland–Chelsea enters
  as strong process evidence, while Forest–Manchester City remains primarily
  outcome variance because City won the xG process.

## Provisional slate

| Fixture | H | D | A | xG | 1X2 leader | O/U 2.5 direction | Decision |
|---|---:|---:|---:|---:|---|---|---|
| Manchester City–Fulham | 52.8% | 26.0% | 21.2% | 1.80–1.06 | Manchester City | Over 53.0% | Pass: XI reliability |
| AFC Bournemouth–Nottingham Forest | 44.0% | 29.2% | 26.8% | 1.47–1.09 | Bournemouth | Under 53.8% | Pass: below 45% |
| Aston Villa–Sunderland | 44.7% | 27.2% | 28.1% | 1.64–1.26 | Aston Villa | Over 54.6% | Pass: below 45% |
| Chelsea–Leeds United | 39.8% | 28.6% | 31.6% | 1.45–1.27 | Chelsea | Over 50.1% | Pass: foundation disagreement |
| Coventry City–Crystal Palace | 39.0% | 27.8% | 33.2% | 1.52–1.38 | Coventry | Over 54.8% | Pass: foundation disagreement |
| Tottenham Hotspur–Ipswich Town | 50.0% | 26.9% | 23.1% | 1.68–1.05 | Tottenham | Over 50.4% | Pass: XI reliability |
| Newcastle United–Arsenal | 26.5% | 28.6% | 44.9% | 1.08–1.49 | Arsenal | Under 53.7% | Pass: below 45% |
| Hull City–Brighton & Hove Albion | 22.1% | 27.4% | 50.5% | 1.03–1.67 | Brighton | Under 50.0% | Pass: XI reliability |
| Liverpool–Manchester United | 43.7% | 27.3% | 29.0% | 1.65–1.30 | Liverpool | Over 55.4% | Pass: foundation disagreement |
| Brentford–Everton | 39.4% | 28.3% | 32.3% | 1.43–1.28 | Brentford | Under 50.6% | Pass: foundation disagreement |

## What is closest to promotion

1. Arsenal away to Newcastle is the cleanest aligned watch. Base, context,
   Club Form and Player Alpha all support Arsenal, contextual interaction
   reinforces the baseline, and lineup reliability is 0.866. Its 44.9%
   calibrated probability remains just below the locked 45% boundary.
2. Manchester City and Brighton have the strongest raw leaders at 52.8% and
   50.5%, with aligned form and Player Alpha, but current projected-XI
   reliability is below the decision gate.
3. Bournemouth are supported by form, Player Alpha and context with complete
   lineup reliability, but 44.0% is still below the minimum side probability.
4. Liverpool–Manchester United Over 2.5 is the strongest total direction at
   55.4%; the locked totals boundary is 58%, so it remains a pass.

## Refresh gate

No 1X2 or O/U 2.5 call is promoted on November 9. The slate is twelve days
before kickoff and precedes the international-window workload, injury and
availability refresh. A separate final packet must be created after that
evidence is available. These probabilities must never be overwritten.

The next refresh should focus on projected-XI reliability for Manchester City,
Tottenham and Brighton; whether Arsenal remains above Newcastle after
international duty; and whether Sunderland's strong Chelsea process survives
opponent adjustment at Aston Villa. Real allocation remains 0.00u.

## Canonical evidence

- `decisions.json`: calibrated selective decisions and refusal reasons.
- `../../current_matchweek/2026-11-09-mw11-provisional/`: locked 60/30/10 base.
- `../../contextual_interaction/2026-11-09-mw11-provisional/`: opponent context.
- `../../prematch_load/2026-11-09-mw11/prematch-load.json`: workload audit.
- `../../style_matchup/2026-11-09/style-matchups.json`: tactical routes.
- `../../../reports/premier-league-alpha-snapshot-2026-11-09.json`: projected-XI Player Alpha.
- `../../fixture_calibration/2026-11-08/calibration.json`: 90-match calibration.

