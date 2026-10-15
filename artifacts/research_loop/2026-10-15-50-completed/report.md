# Clubalpha research checkpoint

As of: 2026-10-15

Completed frozen fixtures: 50/50

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Sunderland | 5 | 1.142 | 0.500 |
| Nottingham Forest | 5 | 1.109 | 0.503 |
| Everton | 5 | 1.061 | 0.506 |
| Arsenal | 5 | 1.045 | 0.503 |
| Fulham | 5 | 1.041 | 0.497 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Crystal Palace | 5 | 1.161 | 0.476 |
| Manchester United | 5 | 1.055 | 0.494 |
| Brentford | 5 | 1.051 | 0.497 |
| Coventry City | 5 | 1.048 | 0.488 |
| Chelsea | 5 | 1.044 | 0.484 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Crystal Palace | 5 | 1.073 | 0.476 |
| Nottingham Forest | 5 | 1.073 | 0.503 |
| Sunderland | 5 | 1.067 | 0.500 |
| Brighton & Hove Albion | 5 | 1.042 | 0.496 |
| Leeds United | 5 | 1.025 | 0.507 |

## Model diagnostics

- Base side-xG MAE: 0.605
- Holy Grail side-xG MAE: 0.606
- Best pre-match coefficient candidate: zero_coefficient
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Crystal Palace (starting_xi_accuracy), Chelsea (starting_xi_accuracy), Coventry City (formation_accuracy), Manchester City (formation_accuracy), Arsenal (formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 50
- Error attribution: club_form_or_team_strength=4, draw_calibration_review=2, lineup_projection=11, model_supported=7, outcome_variance=26
- Chronological challenger validation matches: 30
- Challenger xG MAE improvement: -0.021547
- Challenger 1X2 Brier improvement: -0.029791
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 4

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
