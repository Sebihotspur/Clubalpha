# Clubalpha web

Read-only static dashboard for the frozen Clubalpha prediction artifacts.

Production: <https://clubalpha-club-form-v1.vercel.app/>

```bash
python3 web/scripts/build_site_data.py
python3 -m http.server 4173 --directory web/public
```

The site deliberately contains no wager form, account state, or capital-sizing
control. Vercel serves `web/public` as a static export. Regenerate `site.json`
and the route entry points whenever a new immutable prediction slate is frozen.
