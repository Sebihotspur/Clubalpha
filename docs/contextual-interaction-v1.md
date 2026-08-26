# Contextual Interaction v1

## Purpose

Contextual Interaction answers one question after the locked 60/30/10 model:

> How does this particular opponent change each team's scoring environment?

It does not create another team grade. The weighted foundation supplies base
expected goals; directional matchup evidence modifies each base continuously:

```text
60/30/10 Fixture Intelligence → base xG
continuous route / exposure / XI interaction → context multiplier
base xG × context multiplier → contextual xG
contextual xG → 50,000 coherent simulations
```

The archetype name is never a mathematical input. It is a human-readable label
for the continuous style fingerprint beneath it.

## Directional signal

Every fixture is evaluated twice: home attack against away defence, and away
attack against home defence. Each of five channels carries the transparent
Style Matchup v0 calculation:

```text
channel signal =
    35% attacking route expression
  + 35% opponent exposure
  + 30% projected-XI execution edge
```

The channels are box pressure, set pieces, wide delivery, high press, and
direct transition. A softmax over the attacking team's route expression gives
more influence to routes that the team actually uses without creating a hard
archetype rule.

Evidence reliability is 1.00 for measured channels, 0.70 for partial channels,
and 0.45 for hypothesis channels. Missing pressing evidence removes that
channel. Projected-XI confidence is 1.00 for high, 0.75 for medium, and 0.50 for
low. The directional reliability is:

```text
channel evidence reliability
× geometric mean of both projected-XI confidence values
```

The bounded directional signal and reliability create a smooth multiplier:

```text
log adjustment =
    maximum log sensitivity
  × continuous context signal
  × combined reliability

contextual xG = base xG × exp(log adjustment)
```

There are no favorite bands and no discontinuous probability jumps. A strong
base side remains anchored by its base xG; an opponent that resists its routes
can reduce that xG, while a favorable route can reinforce it. Both directions
are adjusted independently before the full simulation is rerun.

## First live shadow sensitivity

The 2026-08-26 slate uses a symmetric 0.10 maximum absolute log-xG sensitivity
as a safety rail. This is not a learned coefficient. Reliability shrinkage kept
the actual directional adjustments between approximately −4.3% and +3.8% xG
across the ten upcoming Premier League fixtures.

The contextual simulation reuses the baseline's deterministic seed for
reproducibility. Because the Poisson sampler consumes a variable number of
random draws, probability changes are treated as unpaired Monte Carlo
comparisons, not as a common-random-numbers variance-reduction experiment.

Notable shadow reads:

| Fixture | Base favorite | Favorite probability change | Context verdict | Goal environment |
|---|---|---:|---|---|
| Crystal Palace–Manchester City | Manchester City | +2.41 pp | Reinforced | Expansive |
| Liverpool–Nottingham Forest | Liverpool | +1.02 pp | Reinforced | Neutral |
| Chelsea–Brighton | Brighton | +1.36 pp | Reinforced | Neutral |
| Sunderland–Fulham | Sunderland | −0.80 pp | No clear side edge | Suppressed |
| Aston Villa–Arsenal | Arsenal | +2.63 pp | Reinforced | Neutral |

The complete baseline-versus-context output is stored in
`artifacts/contextual_interaction/2026-08-26/`. The official Premier League
fixture amendment published before the slate was used to verify all ten
kickoff pairings.

## Activation boundary

This is the first live shadow observation, not a market-ready forecast. The
0.10 sensitivity must be replaced by a coefficient learned only from earlier,
out-of-sample residuals:

```text
observed xG − locked base-model xG = residual target
```

Only contextual relationships that improve later xG MAE, 1X2 Brier score, log
loss, totals calibration, or BTTS calibration may survive. Fitting the residual
rather than raw performance prevents Club Form and Player Quality from being
counted a second time. Until that chronological gate passes, the locked base
forecast remains the official shadow baseline and the context output is logged
as a sensitivity comparison with zero capital weight.
