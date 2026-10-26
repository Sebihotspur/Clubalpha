# Fixture Calibration v1

Fixture Calibration v1 fixes two probability-translation problems without
changing Clubalpha's football-intelligence foundation:

```text
60% Club Form + 30% Projected-XI Player Alpha + 10% History
    -> contextual xG
    -> evidence-shrunk venue correction
    -> evidence-shrunk total-xG correction
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

## Goal-environment correction

The layer also compares frozen predicted total xG with observed FotMob total
xG. Log residuals receive a 42-day recency half-life, 30 prior-match
equivalents, and a strict cap. The resulting multiplier is applied equally to
home and away xG after the venue-ratio correction, so it changes match tempo
without inventing a team-strength edge or moving the locked 60/30/10 weights.

The chronological audit reports total-xG MAE and Over 2.5 Brier score alongside
the existing 1X2 metrics. This correction stays shadow-only even when one
diagnostic improves; it cannot authorize a recommendation or capital.

## Current artifact

The current artifact is trained through October 25, 2026 on 70 frozen and
completed fixtures. It applies:

- league home/away log-xG-ratio correction: -0.0925;
- draw logit correction: +0.2303;
- total-xG log correction: -0.0568, a 0.945 multiplier;
- team-specific venue corrections: none yet eligible.

The six-cycle forward audit evaluates 60 later fixtures using only earlier
cycles for calibration. Top-pick accuracy rises from 38.3% to 43.3%, total-xG
MAE improves from 0.8236 to 0.8216, and Over 2.5 Brier improves from 0.2552 to
0.2533. However, 1X2 Brier worsens from 0.6366 to 0.6431. The layer therefore
remains useful research evidence, not validated probabilities.

## Boundaries

- Frozen forecasts are never changed.
- Player Alpha formulas remain locked.
- The 60/30/10 base weights remain locked.
- Contextual coefficients remain locked.
- The tempo correction applies symmetrically and cannot manufacture a side.
- Current-season research is recomputed from the full append-only ledger.
- The artifact remains shadow-only until at least 100 calibration matches.
- No price, market, stake, or capital decision is created by this layer.
