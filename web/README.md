# Clubalpha web

Read-only static dashboard for the frozen Clubalpha prediction and research
artifacts.

Production: <https://clubalpha-club-form-v1.vercel.app/>

```bash
python3 web/scripts/build_site_data.py
python3 -m http.server 4173 --directory web/public
```

The site deliberately contains no wager form, account state, or capital-sizing
control. The `/predictions/` route exposes the first official Matchweek 3
shadow slate: ten immutable 1X2 calls, their original model probabilities,
audited football verdicts, confidence, and evidence notes. More than 50% 1X2
accuracy after at least 30 settled official fixtures opens paper allocation and
price validation; it does not authorize real capital.

The `/ledger/` route keeps a collapsible history by matchweek. Every week
reports 1X2, O/U 2.5, and BTTS separately; research backtests are visibly
excluded from the official promotion-gate sample.

The `/holy-grail/` route preserves the frozen Contextual Interaction v1 slate
beside its immutable baseline, including directional routes, reliability, xG
changes, and rerun probabilities. The `/matchups/` route exposes Style
Matchup v0 as a zero-weight
research challenger alongside the frozen 380-fixture W/D/L round robin:
attacking route, opponent exposure, projected-XI Player Alpha, and official
60/30/10 probabilities remain visually separate. Vercel serves `web/public` as a static
export. Regenerate `site.json` and the route entry points whenever a new
immutable prediction or matchup snapshot is frozen. The current official slate
lives at `artifacts/official_shadow/2026-08-31-mw3/`.

After completed fixtures appear in FotMob, append them without modifying the
frozen predictions, then rebuild the static payload:

```bash
python scripts/collect_official_shadow_results.py
python web/scripts/build_site_data.py
```
