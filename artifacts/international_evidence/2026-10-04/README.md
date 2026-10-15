# International player-evidence checkpoint

As of: 2026-10-04  
Window: 2026-09-21 through 2026-10-04  
Status: incomplete until the international window closes on 2026-10-06

## Coverage

- 304 completed national-team matches inspected across senior and youth events.
- 210 match cards exposed player statistics.
- 132 matches contained at least one player in Clubalpha's current 51-club universe.
- 1,000 covered player-match rows were retained for 440 players from 48 clubs.
- Premier League coverage contains 198 players across all 20 clubs.
- Minutes are complete, match ratings cover 95.7%, chances created 93.9%,
  final-third passes 82.7%, xA 55.9%, and xG 39.8%.
- FotMob exposed no line-breaking-pass values in this international sample;
  missing remains missing rather than zero in the raw ledger.

## Premier League signals

The strongest production signals so far are descriptive condition evidence:

- Wilson Isidor: 3 goals and 2 assists in 252 minutes for Sunderland's player pool.
- Erling Haaland: 3 goals, 2.20 xG, and 270 minutes.
- Viktor Gyökeres: 3 goals in 255 minutes.
- Martin Ødegaard: 3 assists and 8 chances created in 270 minutes.
- Mikkel Damsgaard: 2 goals, 1 assist, and 5 chances created in 254 minutes.
- Bruno Fernandes: 2 assists, 1.60 xA, and 10 chances created in 178 minutes.
- Florian Wirtz: 1 goal, 1.11 xG, 0.77 xA, and 9 chances created in 205 minutes.

The main workload flags entering the final days of the window are Bart
Verbruggen, Caoimhín Kelleher, Ethan Ampadu, Joachim Andersen, Konstantinos
Tsimikas, Konstantinos Tzolakis, Micky van de Ven, Neco Williams, Virgil van
Dijk, and Xaver Schlager at 360 minutes each. Workload is not an injury claim;
it triggers projected-XI and recovery review.

## Model boundary

International evidence has zero automatic weight in Club Form, Player Alpha,
fixture probabilities, and capital decisions. It may inform workload,
availability, role/position, recent condition, and projected-XI review. A final
refresh after October 6 is required before the Matchweek 6 slate is frozen.

The machine-readable audit is
`reports/international-player-evidence-v1-audit.json`; normalized source rows
remain in ignored `data/processed/international_current/`.

