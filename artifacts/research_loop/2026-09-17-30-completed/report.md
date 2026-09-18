# Clubalpha research checkpoint

As of: 2026-09-17

Completed frozen fixtures: 30/30

## What the loop learned

The state below is deliberately tentative. Evidence is shrunk toward neutral, the five-match promotion gate remains active, and nothing was applied automatically to a forecast.

### Attack above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Sunderland | 3 | 1.188 | 0.441 |
| Leeds United | 3 | 1.154 | 0.436 |
| Brighton & Hove Albion | 3 | 1.094 | 0.435 |
| AFC Bournemouth | 3 | 1.057 | 0.451 |
| Nottingham Forest | 3 | 1.025 | 0.435 |

### Defensive exposure above expectation

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Brighton & Hove Albion | 3 | 1.195 | 0.435 |
| Crystal Palace | 3 | 1.121 | 0.410 |
| Brentford | 3 | 1.090 | 0.432 |
| Coventry City | 3 | 1.051 | 0.421 |
| Chelsea | 3 | 1.037 | 0.426 |

### Higher-tempo environments than expected

| Team | Matches | Multiplier | Confidence |
|---|---:|---:|---:|
| Brighton & Hove Albion | 3 | 1.161 | 0.435 |
| Leeds United | 3 | 1.065 | 0.436 |
| Sunderland | 3 | 1.063 | 0.441 |
| Coventry City | 3 | 1.016 | 0.421 |
| Nottingham Forest | 3 | 1.014 | 0.435 |

## Model diagnostics

- Base side-xG MAE: 0.657
- Holy Grail side-xG MAE: 0.658
- Best pre-match coefficient candidate: zero_coefficient
- Structural fixture reviews: Liverpool vs Nottingham Forest, Chelsea vs Brighton & Hove Albion, Leeds United vs Brentford, Ipswich Town vs Liverpool, Newcastle United vs AFC Bournemouth, Brentford vs Sunderland, Brighton & Hove Albion vs Leeds United, Nottingham Forest vs Tottenham Hotspur, Hull City vs Aston Villa, Everton vs Manchester United, Aston Villa vs Nottingham Forest, Chelsea vs Hull City, Crystal Palace vs Ipswich Town, Coventry City vs Brighton & Hove Albion
- Lineup reviews: Tottenham Hotspur (starting_xi_accuracy), Crystal Palace (starting_xi_accuracy), Coventry City (starting_xi_accuracy/formation_accuracy), Manchester United (starting_xi_accuracy), Chelsea (formation_accuracy), Manchester City (formation_accuracy), Leeds United (formation_accuracy), Everton (formation_accuracy), Hull City (formation_accuracy), Arsenal (formation_accuracy)
- Missing preferred route evidence: direct_transition, wide_delivery

## Adaptive learning audit

- Match Learning Cards: 30
- Error attribution: club_form_or_team_strength=3, draw_calibration_review=1, lineup_projection=9, model_supported=2, outcome_variance=15
- Chronological challenger validation matches: 10
- Challenger xG MAE improvement: -0.00682
- Challenger 1X2 Brier improvement: -0.039009
- Challenger promotion status: hold_champion
- Fast memory: lineup and formation state; medium memory: form and matchup execution; slow memory: structural review only.

## Promotion gate

Candidates eligible for review: 0

Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.
