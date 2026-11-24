# Matchweek 12 provisional research slate

Prepared: 2026-11-23  
First kickoff: 2026-11-27  
Status: provisional shadow; European workload and final availability refresh
required; no capital authorization

## Evidence refresh

- All 110 completed 2026/27 Premier League matches are present in the
  normalized FotMob foundation.
- The append-only learning state now contains 100 completed frozen forecasts
  and 100 Match Learning Cards through Matchweek 11.
- Club Form and Club Dynamics use 4,944 team-match rows across 2,472 finished
  matches. Projected-XI Player Alpha covers all 20 Premier League clubs.
- Historical Fixtures v2 evaluates the upcoming horizon from 8,762
  team-match rows. The locked 60% Club Form / 30% projected-XI Player Alpha /
  10% historical residual foundation is unchanged.
- Matchweek 11 ended Brentford 4–0 Everton. The result is ingested, but the
  Everton red card prevents the score margin from being treated as clean
  eleven-versus-eleven strength evidence.
- Fixture Calibration uses 100 completed observations. Its downstream venue
  correction is −0.0294 and draw-logit correction is +0.1654; neither rewrites
  the three intelligence foundations.

## Provisional slate

| Fixture | Calibrated xG | H | D | A | 1X2 leader | O/U 2.5 direction | Side decision |
|---|---:|---:|---:|---:|---|---|---|
| Nottingham Forest–Chelsea | 1.57–1.24 | 43.2% | 27.7% | 29.0% | Forest 43.2% | Over 52.3% | Pass: Form/Alpha conflict |
| Leeds United–Coventry City | 1.76–1.02 | 52.3% | 26.5% | 21.1% | Leeds 52.3% | Over 51.8% | Pass: XI reliability |
| Manchester United–Brentford | 1.73–1.27 | 46.2% | 26.7% | 27.2% | Man United 46.2% | Over 56.7% | Pass: Form/Alpha conflict |
| Ipswich Town–Aston Villa | 1.39–1.55 | 33.1% | 27.6% | 39.2% | Villa 39.2% | Over 55.6% | Pass: leader below 45% |
| Everton–Liverpool | 1.36–1.51 | 32.3% | 28.6% | 39.1% | Liverpool 39.1% | Over 53.4% | Pass: leader below 45% |
| Brighton–Newcastle United | 1.72–1.19 | 47.8% | 26.9% | 25.3% | Brighton 47.8% | Over 54.8% | Pass: XI reliability |
| Crystal Palace–Hull City | 1.77–1.31 | 46.4% | 26.3% | 27.3% | Palace 46.4% | **Over 58.7%** | Pass: XI reliability |
| Fulham–AFC Bournemouth | 1.29–1.33 | 34.2% | 29.5% | 36.2% | Bournemouth 36.2% | Under 52.4% | Pass: model layers disagree |
| Sunderland–Tottenham | 1.25–1.22 | 35.0% | 30.2% | 34.7% | Sunderland 35.0% | Under 56.3% | Pass: model layers disagree |
| Arsenal–Manchester City | 1.42–1.33 | 37.3% | 28.8% | 33.9% | Arsenal 37.3% | Over 50.9% | Pass: Form/Alpha conflict |

## Intentional decision

Crystal Palace–Hull Over 2.5 is the only systematic football direction above
the locked total threshold, at 58.7%. The current best executable ask is 56¢
and market no-vig consensus is 55.0%, leaving only +2.7 percentage points
against execution and +3.7 points against consensus. It therefore fails the
five-point price gate and remains provisional even before the required final
availability refresh.

No 1X2 selection is promoted. The model refuses seemingly attractive prices
where the football layers do not agree: Forest, Fulham Under and Sunderland
all show raw model-price discrepancies, but price cannot turn a football pass
into a position.

## Structured review queue

Four totals may receive bounded qualitative review after the midweek matches:

1. Manchester United–Brentford Over 2.5 at 56.7%.
2. Ipswich–Aston Villa Over 2.5 at 55.6%.
3. Crystal Palace–Hull Over 2.5 at 58.7%.
4. Sunderland–Tottenham Under 2.5 at 56.3%.

No discretionary adjustment is active. The review cannot override weak lineup
evidence, foundation disagreement, price quality or the final-refresh gate.

## Market and refresh gate

- Kalshi currently exposes all ten 1X2 events and open totals inventory.
- Polymarket exposes nine of ten match events and nine O/U 2.5 markets.
- The complete market gate contains zero paper positions and zero real
  positions.
- Nine teams have a pending preleague fixture: Bournemouth, Arsenal, Aston
  Villa, Brighton, Crystal Palace, Liverpool, Manchester City, Manchester
  United and Sunderland.

After the European slate, refresh lineups, availability, minutes and prices;
then rebuild a separately dated final candidate. These probabilities must
never be overwritten.

## Canonical evidence

- `decisions.json`: calibrated selective decisions and refusal reasons.
- `../../current_matchweek/2026-11-23-mw12-provisional/`: locked 60/30/10 base.
- `../../contextual_interaction/2026-11-23-mw12-provisional/`: opponent context.
- `../../prematch_load/2026-11-23-mw12/prematch-load.json`: workload audit.
- `../../style_matchup/2026-11-23/style-matchups.json`: tactical routes.
- `../../../reports/premier-league-alpha-snapshot-2026-11-23.json`: projected-XI Player Alpha.
- `../../fixture_calibration/2026-11-23/calibration.json`: 100-match calibration.
- `../../market_snapshots/2026-11-23-mw12-provisional-polymarket.json` and
  `../../market_snapshots/2026-11-23-mw12-provisional-kalshi.json`: read-only prices.
- `../../market_gates/2026-11-23-mw12-provisional/gate.json`: complete paper gate.
- `../../discretionary_reviews/2026-11-23-mw12-provisional/`: inactive review journal.
