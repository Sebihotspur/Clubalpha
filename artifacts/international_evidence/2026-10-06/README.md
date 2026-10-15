# International player-evidence checkpoint

As of: 2026-10-06  
Window: 2026-09-21 through 2026-10-06  
Status: current through the 15:48 UTC collection; refresh if later October 6 fixtures finish

## Coverage

- 337 completed national-team matches inspected across senior and youth events.
- 228 match cards exposed player statistics.
- 141 matches contained at least one player in Clubalpha's current 51-club universe.
- 1,081 covered player-match rows were retained for 444 players from 48 clubs.
- The collector recorded zero player-detail request errors.
- FotMob exposed no line-breaking-pass values in this international sample;
  missing remains missing rather than zero.

## Premier League condition signals

- Wilson Isidor: 3 goals and 2 assists in 341 minutes.
- Viktor Gyokeres: 4 goals and 2.60 xG in 345 minutes.
- Erling Haaland: 3 goals in 270 minutes.
- Martin Odegaard: 3 assists in 270 minutes.
- Rayan Cherki: 1 goal and 2 assists in 197 minutes.
- Mikkel Damsgaard: 2 goals and 1 assist.
- Bruno Fernandes: 2 assists, 1.60 xA and 10 chances created.
- Dominik Szoboszlai: 15 chances created in 347 minutes.

Condition output is descriptive. It does not re-grade prior-season Player
Alpha or override the fixture probabilities.

## Workload use

Projected-XI international minutes now feed the pre-match load audit. Four or
more projected starters at 180+ minutes produce a heavy-load flag; two or more
at 270+ minutes produce an extreme-load flag. Compressed recovery below five
days combined with either flag is high risk. These rules change review urgency
and confidence only; they do not apply a hidden xG adjustment.

The machine-readable audit is
`reports/international-player-evidence-v1-audit.json`; normalized source rows
remain in ignored `data/processed/international_current/`.
