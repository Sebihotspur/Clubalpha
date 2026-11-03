# Matchweek 9 settlement and learning review

Status: settled published-provisional shadow. No capital was deployed.

The decision slate promoted no 1X2 selections and two O/U 2.5 selections. Liverpool–Arsenal Under 2.5 won; Manchester City–Brighton Over 2.5 lost. The promoted totals result is therefore 1/2. Probability leaders are retained only as diagnostics: the calibrated 1X2 leader finished 7/10 and the calibrated totals direction finished 6/10.

## Process before scoreline

The ten fixtures averaged only 2.10 goals but produced 2.79 observed xG, above the calibrated pre-match mean of 2.67. The low-scoring week was therefore primarily a finishing outcome, not evidence that the league's underlying chance environment collapsed. The research loop keeps finishing variance separate from team strength and does not make a large score-only Under adjustment.

- Manchester City lost 0–1 but won the xG process 1.64–1.00. The Over miss is stored as outcome variance, with a smaller tempo correction rather than a Brighton structural-strength rewrite.
- Newcastle lost 0–1 and also lost the xG process 1.29–2.34. The fixture-calibration layer's Everton lean was supported by the match process and is meaningful evidence against excess home bias.
- Brentford won 2–0 from a 0.46–0.86 xG deficit, while Coventry won 3–1 from a 0.69–1.82 deficit. Those scorelines are not allowed to inflate attacking-strength beliefs.
- Aston Villa–Fulham finished 1–1 despite 4.07 total xG. This is finishing suppression, not proof of a naturally low-tempo matchup.
- Tottenham's 2–0 win was supported by a dominant 3.47–0.14 xG process.

## Updated learning state

- Frozen completed fixtures: 80/80.
- Match Learning Cards: 80.
- Error attribution: 40 outcome variance, 18 lineup projection, 10 model supported, 8 club-form/team-strength review, and 4 draw-calibration review.
- The medium-memory challenger improves O/U 2.5 Brier score by 0.003589 but worsens side-xG MAE and 1X2 Brier. It remains a challenger; the champion is retained.
- League home-advantage correction softens from -0.0925 to -0.0821 log-ratio after the new evidence.
- Draw correction softens from +0.2303 to +0.1864 logit; the observed draw rate is now 30.0% across 80 fixtures.
- The recency-weighted total-xG correction is nearly unchanged at -0.0556 log, approximately a 0.946 multiplier. The new xG evidence does not justify a score-driven overhaul.

## Lineup and archetype memory

The largest lineup review flags remain Tottenham starting-XI accuracy plus Chelsea, Manchester City and Leeds formation accuracy. The archetype ledger now contains 160 team-perspective observations, 96 team-versus-opponent-archetype rows and 33 league archetype interactions. All archetype evidence remains zero live weight pending chronological challenger validation.

## Governance verdict

The engine absorbed the new matches without changing Player Alpha, the locked 60/30/10 foundation, frozen predictions, or capital authorization. The adaptive challenger failed the full promotion gate, so no unproven adjustment was allowed to replace the champion.
