# Clubalpha research checkpoint

As of: 2026-11-02

Completed frozen fixtures: 80/80

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 8 | 1.080 | 0.620 |
| Nottingham Forest | 8 | 1.044 | 0.614 |
| Manchester City | 8 | 1.007 | 0.602 |
| Fulham | 8 | 1.001 | 0.613 |
| Arsenal | 8 | 0.996 | 0.600 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 8 | 1.151 | 0.606 |
| Crystal Palace | 8 | 1.115 | 0.598 |
| Newcastle United | 8 | 1.066 | 0.605 |
| Brentford | 8 | 1.011 | 0.606 |
| Ipswich Town | 8 | 0.997 | 0.610 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Crystal Palace | 8 | 1.024 | 0.598 |
| Sunderland | 8 | 1.013 | 0.608 |
| Manchester United | 8 | 1.011 | 0.606 |
| Everton | 8 | 0.980 | 0.613 |
| Manchester City | 8 | 0.979 | 0.602 |

## Model diagnostics

- Base side-xG MAE: 0.600
- Holy Grail side-xG MAE: 0.601
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa, Coventry City vs Fulham, Chelsea vs Tottenham Hotspur, Hull City vs Brentford, Liverpool vs Brighton & Hove Albion, Manchester United vs AFC Bournemouth, Sunderland vs Leeds United, Hull City vs Ipswich Town, Aston Villa vs Fulham, Newcastle United vs Everton
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Chelsea (formation_accuracy), Manchester City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 80
- Error attribution: club_form_or_team_strength=8, draw_calibration_review=4, lineup_projection=18, model_supported=10, outcome_variance=40
- Chronological challenger validation matches: 60
- Challenger xG MAE improvement: -0.000564
- Challenger 1X2 Brier improvement: -0.009296
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 21

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
