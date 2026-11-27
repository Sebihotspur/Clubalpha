# Clubalpha research checkpoint

As of: 2026-11-27

Completed frozen fixtures: 101/110

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 10 | 1.155 | 0.625 |
| Liverpool | 10 | 1.082 | 0.613 |
| Nottingham Forest | 11 | 1.052 | 0.656 |
| Leeds United | 10 | 1.045 | 0.613 |
| Brighton & Hove Albion | 10 | 1.024 | 0.622 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 10 | 1.282 | 0.604 |
| Crystal Palace | 10 | 1.147 | 0.601 |
| Ipswich Town | 10 | 1.065 | 0.610 |
| Everton | 10 | 1.041 | 0.616 |
| Chelsea | 11 | 1.000 | 0.640 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 10 | 1.124 | 0.604 |
| Crystal Palace | 10 | 1.088 | 0.601 |
| AFC Bournemouth | 10 | 1.061 | 0.625 |
| Liverpool | 10 | 1.020 | 0.613 |
| Nottingham Forest | 11 | 1.009 | 0.656 |

## Model diagnostics

- Base side-xG MAE: 0.625
- Holy Grail side-xG MAE: 0.625
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa, Coventry City vs Fulham, Chelsea vs Tottenham Hotspur, Hull City vs Brentford, Liverpool vs Brighton & Hove Albion, Manchester United vs AFC Bournemouth, Sunderland vs Leeds United, Hull City vs Ipswich Town, Aston Villa vs Fulham, Newcastle United vs Everton, Fulham vs Newcastle United, Chelsea vs Leeds United, Newcastle United vs Arsenal
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Chelsea (starting_xi_accuracy/formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 101
- Error attribution: club_form_or_team_strength=8, draw_calibration_review=5, lineup_projection=22, model_supported=16, outcome_variance=50
- Chronological challenger validation matches: 81
- Challenger xG MAE improvement: -0.007339
- Challenger 1X2 Brier improvement: -0.0024
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 21

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
