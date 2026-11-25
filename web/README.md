# Clubalpha web

Read-only static dashboard for the frozen Clubalpha prediction and research
artifacts.

Production: <https://clubalpha-club-form-v1.vercel.app/>

```bash
python3 web/scripts/build_site_data.py
python3 -m http.server 4173 --directory web/public
```

Predictions shows the latest saved pre-kickoff decision for each fixture.
Ledger keeps paper positions, the standardized bankroll, and matchweek hit
rates separate. Matchups retains the full 380-fixture benchmark and uses the
latest fixture forecast when the exact home/away pairing is on the slate.
Methodology and research detail stay in the repository; the previous
`/data/site.json` export remains available for existing consumers.

For a Champions League scoreboard refresh, capture a new dated snapshot:

```bash
python3 web/scripts/refresh_ucl_scoreboard.py --matchday 5 \
  --output artifacts/ucl_research/YYYY-MM-DD-md5/scoreboard.json
```

After adding a scoreboard, a new frozen decision slate, a style snapshot, or
settlements via the existing result collectors, regenerate the site with
`python3 web/scripts/build_site_data.py` and publish `web/public` through the
linked Vercel project. The display discovers dated artifacts on rebuild; it
does not place wagers, generate predictions, or treat score-only fixtures as
scored forecasts.
