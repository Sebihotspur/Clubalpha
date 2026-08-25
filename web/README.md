# Clubalpha web

Read-only static dashboard for the frozen Clubalpha prediction and research
artifacts.

Production: <https://clubalpha-club-form-v1.vercel.app/>

```bash
python3 web/scripts/build_site_data.py
python3 -m http.server 4173 --directory web/public
```

The site deliberately contains no wager form, account state, or capital-sizing
control. The `/matchups/` route exposes Style Matchup v0 as a zero-weight
research challenger alongside the frozen 380-fixture W/D/L round robin:
attacking route, opponent exposure, projected-XI Player Alpha, and official
60/30/10 probabilities remain visually separate. Vercel serves `web/public` as a static
export. Regenerate `site.json` and the route entry points whenever a new
immutable prediction or matchup snapshot is frozen.
