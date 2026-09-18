# Matchweek 5 preweek shadow draft

Frozen: 2026-09-15T16:06:32.744373+00:00

This is a dated research draft, not a new official ledger cycle or a real-capital recommendation. It has not been published to Vercel or pushed to GitHub. Preserve this record; later lineup checks must create a separate dated version rather than overwrite it.

## Evidence and boundaries

- Refreshed squads and availability on September 15.
- Club Form uses all 40 completed Premier League fixtures and 18 completed UCL fixtures, with the existing competition normalization and historical/preseason evidence.
- Venue/draw calibration uses 30 completed frozen PL forecasts. UCL results do not enter PL calibration.
- The latest-five selection runner now reuses UCL appearances and completed cup/other-European lineups. Supplementary appearances affect selection only, not Alpha formulas, Club Form or PL calibration.
- Player Alpha and the 60% Form / 30% projected-XI quality / 10% historical-residual weights remain unchanged. Tentative team research beliefs have zero automatic probability impact.
- Each baseline/context/calibration run uses the existing 50,000-draw policy per fixture. Simulation volume does not establish calibration quality.
- The unresolved goal-environment compression and unvalidated context coefficient remain explicit.
- Prices, spreads, liquidity and closing-line value have not been checked. No high-confidence or capital call is made.

## Proposed calls

| Fixture | Shadow 1X2 call | Model probability of call | Evidence confidence | Totals shortlist |
|---|---|---:|---|---|
| Brentford–Chelsea | Brentford | 36.7% | low | Over 2.5 (61.9%) |
| Tottenham Hotspur–Aston Villa | Draw | 35.6% | low | Pass |
| Brighton & Hove Albion–Arsenal | Arsenal | 37.3% | low | Pass |
| Everton–Ipswich Town | Everton | 39.3% | medium | Pass |
| Newcastle United–Hull City | Newcastle United | 39.7% | low | Pass |
| Nottingham Forest–Coventry City | Nottingham Forest | 40.8% | medium | Pass |
| AFC Bournemouth–Liverpool | Draw | 33.6% | low | Pass |
| Leeds United–Crystal Palace | Leeds United | 45.8% | medium | Over 2.5 (57.0%) |
| Manchester City–Sunderland | Manchester City | 53.3% | medium | Pass |
| Fulham–Manchester United | Manchester United | 42.1% | low | Pass |

The Spurs–Villa and Bournemouth–Liverpool draw calls are documented decision overrides inside the existing draw zone. Their raw probability leaders remain visible in picks.json. Arsenal remains a low-conviction away lean despite the pass/draw zone; the risk gate is not an automatic instruction to pick a draw.

All ten model totals directions and probabilities are retained in picks.json. Only Brentford–Chelsea and Leeds–Palace are shortlisted for totals analysis; do not present an all-fixture model-direction hit rate as the performance of these two shortlisted calls.

## Main research theses

1. City–Sunderland: City own the strongest projected Alpha advantage, especially box-pressure execution. Sunderland's improving creation is respected; City's Thursday EFL Cup and Sunderland's Wednesday Europa game prevent a high-confidence call. The 51.5% over forecast does not justify a City-plus-over combo.
2. Leeds–Palace: Leeds' earlier positive chance-creation evidence was reinforced by the 4–1 Newcastle win (2.08–0.88 xG). Palace's defensive exposure and Thursday Europa game make this a cleaner matchup than merely chasing Leeds' last scoreline. Leeds' Alpha coverage is still provisional.
3. Brentford–Chelsea: projected-quality favors Chelsea but the refreshed fixture signal narrowly favors Brentford. The stronger forecast is the 61.9% over probability, not either team's winner call. Caicedo's current absence is reflected in the available squad, not a separate arbitrary adjustment.
4. Forest–Coventry: Forest's 1–2 win at Villa had a 1.92–0.82 xG advantage; Coventry's 0–5 loss to Brighton had 1.33–2.81 xG. Back Forest's process cautiously, not a repeat of Coventry's extreme scoreline.
5. Bournemouth–Liverpool: better Bournemouth creation versus superior Liverpool player quality remains a conflicting signal. Liverpool's attack has under-created relative to the frozen model; Bournemouth's Thursday European trip still needs review.

## Before final release

- Check all completed midweek cup/European games for actual minutes, injuries, formation and availability. Do not ingest games that have not finished.
- Recheck Arsenal's and Tottenham's attacking/defensive availability, provisional Alpha coverage for Leeds/Liverpool/Palace, and XI uncertainty for United/Spurs.
- Compare selected outcome prices with model probabilities, executable spread/depth, fees and market settlement rules before any paper allocation.
- Keep 1X2 and O/U separate. BTTS remains diagnostic-only.

## UCL schedule

There are no UCL league-phase games in the MW5 week. Matchday 2 is October 13–14; no official prediction is frozen that far ahead. Reuse Matchday 1 performances as shared club evidence, not as retrospective UCL predictions.

Sources: [Revised PL MW5 schedule](https://www.premierleague.com/es/news/4699026/manchester-city-v-sunderland-match-moved-to-a-new-date), [UEFA schedule](https://www.uefa.com/uefachampionsleague/news/02a8-2174c9e9019d-f909a77bd77a-1000/). Full source hashes and model output are stored in picks.json.
