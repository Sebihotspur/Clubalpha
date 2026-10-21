# Clubalpha research checkpoint

As of: 2026-10-21

Completed frozen fixtures: 60/60

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 6 | 1.082 | 0.557 |
| Nottingham Forest | 6 | 1.066 | 0.548 |
| Manchester City | 6 | 1.044 | 0.535 |
| Ipswich Town | 6 | 1.030 | 0.542 |
| Fulham | 6 | 1.011 | 0.543 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Crystal Palace | 6 | 1.112 | 0.531 |
| Sunderland | 6 | 1.107 | 0.542 |
| Brentford | 6 | 1.059 | 0.540 |
| Manchester City | 6 | 1.047 | 0.535 |
| Manchester United | 6 | 1.045 | 0.544 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Sunderland | 6 | 1.104 | 0.542 |
| Manchester City | 6 | 1.049 | 0.535 |
| Ipswich Town | 6 | 1.047 | 0.542 |
| Nottingham Forest | 6 | 1.034 | 0.548 |
| Crystal Palace | 6 | 1.030 | 0.531 |

## Model diagnostics

- Base side-xG MAE: 0.608
- Holy Grail side-xG MAE: 0.610
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Crystal Palace (starting_xi_accuracy), Coventry City (formation_accuracy), Manchester City (formation_accuracy), Chelsea (formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 60
- Error attribution: club_form_or_team_strength=7, draw_calibration_review=2, lineup_projection=13, model_supported=9, outcome_variance=29
- Chronological challenger validation matches: 40
- Challenger xG MAE improvement: -0.019482
- Challenger 1X2 Brier improvement: -0.019348
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 17

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
