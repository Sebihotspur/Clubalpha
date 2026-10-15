# Clubalpha research checkpoint

As of: 2026-10-06

Completed frozen fixtures: 40/40

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Sunderland | 4 | 1.331 | 0.452 |
| Brighton & Hove Albion | 4 | 1.060 | 0.447 |
| Leeds United | 4 | 1.058 | 0.452 |
| Everton | 4 | 1.027 | 0.454 |
| Manchester City | 4 | 1.022 | 0.445 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Brighton & Hove Albion | 4 | 1.156 | 0.447 |
| Chelsea | 4 | 1.073 | 0.436 |
| Manchester City | 4 | 1.056 | 0.445 |
| Crystal Palace | 4 | 1.041 | 0.422 |
| Newcastle United | 4 | 1.022 | 0.446 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Sunderland | 4 | 1.154 | 0.452 |
| Brighton & Hove Albion | 4 | 1.120 | 0.447 |
| Manchester City | 4 | 1.045 | 0.445 |
| Leeds United | 4 | 1.012 | 0.452 |
| Fulham | 4 | 1.008 | 0.449 |

## Model diagnostics

- Base side-xG MAE: 0.618
- Holy Grail side-xG MAE: 0.619
- Best pre-match coefficient candidate: zero_coefficient
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Crystal Palace (starting_xi_accuracy), Coventry City (starting_xi_accuracy/formation_accuracy), Manchester City (formation_accuracy), Leeds United (formation_accuracy), Hull City (formation_accuracy), Arsenal (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 40
- Error attribution: club_form_or_team_strength=4, draw_calibration_review=2, lineup_projection=10, model_supported=4, outcome_variance=20
- Chronological challenger validation matches: 20
- Challenger xG MAE improvement: -0.027169
- Challenger 1X2 Brier improvement: -0.038119
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 0

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
