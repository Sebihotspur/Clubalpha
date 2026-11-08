# Clubalpha research checkpoint

As of: 2026-11-07

Completed frozen fixtures: 85/90

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 8 | 1.077 | 0.602 |
| Manchester City | 9 | 1.024 | 0.630 |
| Nottingham Forest | 9 | 1.015 | 0.642 |
| Brighton & Hove Albion | 8 | 0.966 | 0.599 |
| Leeds United | 9 | 0.955 | 0.638 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 8 | 1.147 | 0.588 |
| Crystal Palace | 8 | 1.111 | 0.579 |
| Brentford | 8 | 1.011 | 0.587 |
| Ipswich Town | 8 | 0.997 | 0.592 |
| Newcastle United | 9 | 0.980 | 0.628 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Crystal Palace | 8 | 1.024 | 0.579 |
| Sunderland | 8 | 1.012 | 0.589 |
| Manchester United | 8 | 1.011 | 0.588 |
| Manchester City | 9 | 0.982 | 0.630 |
| Everton | 9 | 0.978 | 0.640 |

## Model diagnostics

- Base side-xG MAE: 0.590
- Holy Grail side-xG MAE: 0.591
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa, Coventry City vs Fulham, Chelsea vs Tottenham Hotspur, Hull City vs Brentford, Liverpool vs Brighton & Hove Albion, Manchester United vs AFC Bournemouth, Sunderland vs Leeds United, Hull City vs Ipswich Town, Aston Villa vs Fulham, Newcastle United vs Everton, Fulham vs Newcastle United
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy/formation_accuracy), Chelsea (formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 85
- Error attribution: club_form_or_team_strength=8, draw_calibration_review=4, lineup_projection=19, model_supported=12, outcome_variance=42
- Chronological challenger validation matches: 65
- Challenger xG MAE improvement: -0.001429
- Challenger 1X2 Brier improvement: -0.00888
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 22

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
