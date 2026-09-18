# Research phase checkpoint — 2026-09-16

## Decision

The locked 60/30/10 intelligence, Player Alpha, projected-XI logic, and current
fixture probabilities remain unchanged. Three missing support layers were run
as versioned, zero-live-weight research. None authorizes an official Matchweek
5 slate or capital deployment.

## 1. Total-goals challenger

The challenger learned an empirical relationship between pre-match total xG
and Over 2.5 results from pre-2026/27 Premier League and Champions League
matches. Training is chronological and excludes the current season.

It failed the frozen-fixture promotion test:

| Frozen evaluation | Baseline Brier | Challenger Brier | Baseline log loss | Challenger log loss |
| --- | ---: | ---: | ---: | ---: |
| All 30 fixtures | 0.2545 | 0.2614 | 0.7024 | 0.7172 |
| 20 official fixtures | 0.2554 | 0.2606 | 0.7044 | 0.7161 |

Direction accuracy was unchanged at 50% across all 30 fixtures and 55% across
the 20 official fixtures. The challenger raises most Over probabilities, but
that does not solve the current error. This is evidence that the more urgent
problem is the estimated total-xG environment, not merely the distribution
used to translate total xG into an Over probability.

**Verdict:** rejected for promotion; zero live weight.

## 2. Pre-match lineup and load audit

The audit uses the projected XI, actual minutes in each team's latest completed
match, starter overlap, competition changes, rest, pending matches before the
league fixture, and Player Alpha coverage. It is a risk gate only and does not
select the XI or change probabilities.

Current risk distribution: 2 low, 14 medium, and 4 high.

High-risk teams:

- AFC Bournemouth: Europa League match still pending before the league fixture.
- Crystal Palace: Europa League match still pending before the league fixture.
- Manchester City: EFL Cup match still pending before the league fixture.
- Sunderland: under four days' rest and a heavy projected-XI load in the latest
  Europa League match.

**Verdict:** useful immediately as an evidence-quality gate. Refresh after the
three pending matches; do not freeze those affected league reads beforehand.

## 3. Read-only market observation

The public Polymarket event and order-book interfaces matched all 10 Matchweek
5 fixtures and all 10 Over/Under 2.5 markets. The snapshot stores executable
best bids and asks, spreads, top-of-book size, shallow ask depth, reported
liquidity, and model edge versus the best ask. It uses no wallet, credentials,
or order endpoint.

The first snapshot is a diagnostic warning, not an edge list:

- The market's no-vig favourite averaged 53.8%; Clubalpha assigned those same
  sides only 39.4%, a mean gap of -14.4 percentage points.
- Clubalpha's draw probability averaged 33.5%; the market's no-vig draw
  probability averaged 23.8%, a mean gap of +9.7 points.
- Clubalpha's Over 2.5 probability averaged 51.7%; the market midpoint averaged
  58.0%, a mean gap of -6.3 points.
- Every sampled book had a one-cent top-of-book spread, so the disagreement is
  not explained by a wide displayed spread.

The 1X2 pattern is systematic: the current fixture calibration is compressing
too much probability toward the draw and away from clear favourites. Its
30-match training sample contained 13 draws, while the artifact is already
flagged as a small sample. Market prices are not treated as truth and will not
be copied into the model, but the cross-slate disagreement is too consistent to
label as deployable value.

Example: Manchester City is 53.0% in Clubalpha versus 75.9% no-vig in the
market, while the model draw is 30.8% versus 15.6%. Both clubs are also marked
high load risk. This is an audit case, not a City fade or draw recommendation.

**Verdict:** market collection works; price validation is now observable, but
the current probability layer is not market-ready.

## Next controlled experiment

Build a separate 1X2 calibration challenger that addresses probability
compression using long-run, pre-season Premier League outcome evidence and
chronological validation. Compare it against both the uncalibrated model and
Fixture Calibration v1. It must improve multiclass Brier score and log loss on
later frozen fixtures before it can replace the existing downstream
calibration. Market prices remain an external benchmark, never a training
target for football intelligence.

## Locked boundaries

- No frozen forecast was rewritten.
- Player Alpha formulas and the 60/30/10 foundation were not changed.
- The goals challenger has zero live weight.
- The lineup/load audit has zero probability weight.
- The market collector is read-only and cannot place orders.
- Matchweek 5 is not frozen while pre-league fixtures remain pending.
- Paper allocation and real capital remain disabled.
