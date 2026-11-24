# Clubalpha research checkpoint

As of: 2026-11-23

Completed frozen fixtures: 100/100

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 10 | 1.159 | 0.639 |
| Liverpool | 10 | 1.084 | 0.627 |
| Nottingham Forest | 10 | 1.074 | 0.631 |
| Leeds United | 10 | 1.046 | 0.628 |
| Brighton & Hove Albion | 10 | 1.024 | 0.636 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 10 | 1.289 | 0.619 |
| Crystal Palace | 10 | 1.151 | 0.615 |
| Ipswich Town | 10 | 1.067 | 0.625 |
| Everton | 10 | 1.042 | 0.631 |
| Chelsea | 10 | 1.013 | 0.613 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 10 | 1.127 | 0.619 |
| Crystal Palace | 10 | 1.090 | 0.615 |
| AFC Bournemouth | 10 | 1.062 | 0.639 |
| Liverpool | 10 | 1.020 | 0.627 |
| Nottingham Forest | 10 | 1.020 | 0.631 |

## Model diagnostics

- Base side-xG MAE: 0.630
- Holy Grail side-xG MAE: 0.630
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa, Coventry City vs Fulham, Chelsea vs Tottenham Hotspur, Hull City vs Brentford, Liverpool vs Brighton & Hove Albion, Manchester United vs AFC Bournemouth, Sunderland vs Leeds United, Hull City vs Ipswich Town, Aston Villa vs Fulham, Newcastle United vs Everton, Fulham vs Newcastle United, Chelsea vs Leeds United, Newcastle United vs Arsenal
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Chelsea (formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 100
- Error attribution: club_form_or_team_strength=8, draw_calibration_review=5, lineup_projection=22, model_supported=16, outcome_variance=49
- Chronological challenger validation matches: 80
- Challenger xG MAE improvement: -0.00647
- Challenger 1X2 Brier improvement: -0.003373
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 21

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
