# Clubalpha research checkpoint

As of: 2026-10-26

Completed frozen fixtures: 70/70

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| AFC Bournemouth | 7 | 1.129 | 0.596 |
| Nottingham Forest | 7 | 1.110 | 0.588 |
| Manchester City | 7 | 1.027 | 0.576 |
| Arsenal | 7 | 1.021 | 0.581 |
| Brighton & Hove Albion | 7 | 0.995 | 0.590 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Manchester United | 7 | 1.096 | 0.584 |
| Ipswich Town | 7 | 1.087 | 0.581 |
| Brentford | 7 | 1.070 | 0.578 |
| Crystal Palace | 7 | 1.038 | 0.571 |
| Sunderland | 7 | 1.022 | 0.580 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Ipswich Town | 7 | 1.031 | 0.581 |
| Sunderland | 7 | 1.026 | 0.580 |
| Nottingham Forest | 7 | 1.019 | 0.588 |
| AFC Bournemouth | 7 | 1.008 | 0.596 |
| Brentford | 7 | 1.006 | 0.578 |

## Model diagnostics

- Base side-xG MAE: 0.597
- Holy Grail side-xG MAE: 0.597
- Best pre-match coefficient candidate: applied_conservative
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion, AFC Bournemouth vs Liverpool, Fulham vs Manchester United, Manchester United vs Tottenham Hotspur, Everton vs Chelsea, Brentford vs Liverpool, Newcastle United vs Aston Villa, Coventry City vs Fulham, Chelsea vs Tottenham Hotspur, Hull City vs Brentford, Liverpool vs Brighton & Hove Albion, Manchester United vs AFC Bournemouth, Sunderland vs Leeds United
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Crystal Palace (starting_xi_accuracy), Manchester City (formation_accuracy), Chelsea (formation_accuracy), Coventry City (formation_accuracy), Hull City (formation_accuracy), Leeds United (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 70
- Error attribution: club_form_or_team_strength=8, draw_calibration_review=4, lineup_projection=15, model_supported=9, outcome_variance=34
- Chronological challenger validation matches: 50
- Challenger xG MAE improvement: -0.004714
- Challenger 1X2 Brier improvement: -0.010747
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 26

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
