# Clubalpha research checkpoint

As of: 2026-11-08

Completed frozen fixtures: 90/90

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 9 | 1.106 | 0.646 |
| Manchester City | 9 | 1.024 | 0.627 |
| Aston Villa | 9 | 1.018 | 0.635 |
| Nottingham Forest | 9 | 1.015 | 0.638 |
| Brighton & Hove Albion | 9 | 0.992 | 0.644 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 9 | 1.218 | 0.628 |
| Crystal Palace | 9 | 1.156 | 0.622 |
| Aston Villa | 9 | 1.041 | 0.635 |
| Ipswich Town | 9 | 1.032 | 0.636 |
| Brentford | 9 | 1.031 | 0.632 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 9 | 1.090 | 0.628 |
| Crystal Palace | 9 | 1.082 | 0.622 |
| Aston Villa | 9 | 1.055 | 0.635 |
| Sunderland | 9 | 1.016 | 0.630 |
| AFC Bournemouth | 9 | 0.996 | 0.646 |

## Model diagnostics

- Base side-xG MAE: 0.609
- Holy Grail side-xG MAE: 0.610
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa, Coventry City vs Fulham, Chelsea vs Tottenham Hotspur, Hull City vs Brentford, Liverpool vs Brighton & Hove Albion, Manchester United vs AFC Bournemouth, Sunderland vs Leeds United, Hull City vs Ipswich Town, Aston Villa vs Fulham, Newcastle United vs Everton, Fulham vs Newcastle United
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy/formation_accuracy), Crystal Palace (starting_xi_accuracy), Chelsea (formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 90
- Error attribution: club_form_or_team_strength=8, draw_calibration_review=4, lineup_projection=19, model_supported=14, outcome_variance=45
- Chronological challenger validation matches: 70
- Challenger xG MAE improvement: -0.003345
- Challenger 1X2 Brier improvement: -0.006298
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 22

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
