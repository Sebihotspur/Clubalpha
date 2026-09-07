# Fixture Calibration v1

Fixture Calibration v1 fixes two probability-translation problems without
changing Clubalpha's football-intelligence foundation:

```text
60% Club Form + 30% Projected-XI Player Alpha + 10% History
    -> contextual xG
    -> evidence-shrunk venue correction
    -> evidence-shrunk draw correction
    -> 50,000 weighted simulations
    -> calibrated shadow probabilities + draw-risk gate
```

## Venue correction

The league correction compares the aggregate observed home/away FotMob xG
ratio with the ratio expected by frozen forecasts. The log-ratio residual is
shrunk by 20 prior-match equivalents and capped before being divided evenly
between home and away xG. This changes venue translation, not team strength or
the 60/30/10 weights.

Team-specific venue effects are tracked but remain zero until a club has at
least five completed home observations and five completed away observations.
They are also shrunk and capped. This prevents one unusual home or away match
from becoming a permanent team trait.

## Draw correction

The layer compares the draw rate expected by frozen probabilities with the
observed append-only draw count. The posterior target uses 20 prior-match
equivalents centered on the model expectation. A bounded logit correction then
reweights diagonal scorelines from the 50,000 simulated outcomes while
rescaling non-draw scorelines coherently.

A fixture enters the draw zone when the corrected draw probability sits within
four percentage points of the strongest side probability and that side remains
at or below 50%. The draw zone is a pass/review gate, not an automatic draw
wager.

## Current artifact

The first artifact is trained through September 6, 2026 on 20 frozen and
completed Matchweek 2–3 fixtures. It applies:

- league home/away log-xG-ratio correction: -0.0538;
- draw logit correction: +0.5282;
- team-specific venue corrections: none yet eligible.

The cycle-forward audit trains on Matchweek 2 and evaluates Matchweek 3. It
improves 1X2 Brier score from 0.7416 to 0.7247 and log loss from 1.2099 to
1.1755, while top-pick accuracy remains 2/10. This is encouraging calibration
evidence, not probability validation.

## Boundaries

- Frozen forecasts are never changed.
- Player Alpha formulas remain locked.
- The 60/30/10 base weights remain locked.
- Contextual coefficients remain locked.
- Current-season research is recomputed from the full append-only ledger.
- The artifact remains shadow-only until at least 100 calibration matches.
- No price, market, stake, or capital decision is created by this layer.
