# Club Dynamics v1

## Purpose

Club Dynamics extends Club Form without replacing its performance score. It
answers three different questions:

1. How does the club play?
2. Where has it been strong or weak?
3. How much change is the manager and squad absorbing?

These outputs remain separate. Style is not quality, a transfer fee is not
football impact, and a new manager is not automatically an upgrade or a
downgrade.

```text
Club Form
├── Performance Form v1
├── Club Dynamics v1
│   ├── Style fingerprint
│   ├── Strengths and weaknesses
│   └── Manager, transfers, and continuity
└── Availability
```

## Source handoff

The FotMob foundation now normalizes three additional provider datasets:

```text
data/processed/foundation/
├── club_snapshots.jsonl
├── manager_history.jsonl
└── transfer_events.jsonl
```

Club snapshots preserve the current coach and squad player IDs. Manager
history preserves season records. Transfer events preserve the effective and
reported dates, direction, position, counterparty, loan state, fee, and market
value.

The source is undocumented, so all interpretation happens after this
normalization boundary. Confirmed transfers are clipped by both their
effective date and reported date for the requested `--as-of` snapshot.

## Style fingerprint

Style is neutral and has no composite grade. Six axes describe the club
relative to its competition peers:

| Axis | FotMob evidence | High value means |
|---|---|---|
| Control | Possession | Possession-dominant |
| Territory | Opposition-half share of completed half passes | More advanced territory |
| Directness | Estimated long-ball attempts per 100 passes | More direct |
| Crossing | Estimated cross attempts per 100 opposition-half passes | More cross-oriented |
| Set-piece reliance | Set-play xG as a share of total xG | More reliant on set plays |
| High pressing | Previous-season possessions won in the attacking third | More high regains |

FotMob publishes accurate long balls and crosses with rounded percentages.
Attempt volumes are therefore estimates. A match with zero completed crosses
and a zero percent rate cannot reveal its attempt count, so the value remains
missing rather than becoming zero.

Match-level style uses a 90-day half-life. Preseason begins at 0.60 weight and
cannot exceed 45% of the available style evidence. This makes preseason useful
for detecting tactical change while preventing friendlies from erasing the
competitive record.

High pressing is currently a previous-season team statistic. If the manager
changed, it is explicitly flagged as predating the current coach.

The profile also compares previous competitive style with preseason/current
evidence. It reports the direction and size of each season-boundary shift, but
does not claim the manager caused it. That causal boundary matters when an
appointment date is unavailable or transfers changed the same team at once.

## Strengths and weaknesses

The diagnostic profile contains nine competition-relative characteristics:

- chance creation;
- shot quality;
- finishing versus xG;
- box access;
- set-piece attack;
- chance prevention;
- shot suppression;
- box defence;
- set-piece defence.

Each characteristic is normalized within the match's competition. Defence is
inverted so a positive value always means better performance. Evidence uses a
60-day half-life, preseason begins at 0.25, and preseason is capped at 20%.

The underlying signal determines whether an axis is called a strength or
weakness. The published z-score is multiplied by evidence confidence. This
keeps the football observation visible while showing that thin evidence is
uncertain. Evidence confidence below 0.35 is labelled insufficient rather than
being forced into a strength or weakness.

Strengths and weaknesses are a decomposition of recent performance. They do
not modify Performance Form v1 and must not be added to it as another score.

## Manager and transfer change

The current coach is compared with FotMob's previous-season coach history.
When the current coach is absent, the club is marked as having changed
manager. FotMob does not publish a reliable appointment date in this payload,
so post-season-boundary match count is an adaptation-evidence proxy, not a
claim that every match occurred under the current coach.

Confirmed summer transfers are connected to Player Quality by FotMob player
ID. For incoming players, preseason and current competitive minutes estimate
integration:

```text
integration_share = player_minutes / (detailed_team_matches × 90)
```

A highly rated arrival with no observed minutes is therefore a potential
upgrade that is not yet integrated. Alpha Ability coverage and integration are
always shown separately. Each arrival is labelled quality unknown, integration
unobserved, potential/unintegrated, partially integrated, or integrated. A
minutes-weighted known Alpha total describes how much of the known incoming
quality has appeared on the pitch. Fee and market value are retained for
traceability but never enter the football model.

If no transfer in a non-empty group joins to Player Quality, its Alpha total
remains missing rather than becoming zero. Zero is reserved for a truly empty
transfer group or a known minutes-weighted contribution of zero.

Squad continuity requires two dated snapshots. The first run is correctly
reported as `first_squad_snapshot`; later pulls calculate retained, added, and
removed players against the most recent earlier snapshot.

No change-state composite or Club Form modifier exists in v1. That boundary
can change only after walk-forward testing demonstrates predictive value.

## Outputs

```text
data/processed/club_dynamics/
├── dynamic_match_observations.jsonl
├── club_dynamics.jsonl
├── club_events.jsonl
├── source_snapshots.jsonl
└── manifest.json

reports/club-dynamics-v1-audit.json
```

Run after the foundation, domestic history, and Player Quality builds:

```bash
python3 scripts/build_club_dynamics.py
```

The dated source snapshot file is append-only and idempotent by team and date.
All detailed rows remain ignored by Git; the compact audit is tracked.

## First real-data audit

The 2026-08-18 build produces:

- 58 target clubs;
- 4,288 team-match observations;
- 56 clubs with style evidence;
- 56 clubs with strengths/weaknesses evidence;
- 55 current managers from 58 club pages;
- 18 manager changes detected against 2025/26;
- 828 confirmed incoming or outgoing transfer events in the summer window.

Only 207 transfer events currently connect to an Alpha Ability Grade (25.0%). The
known-only Alpha sums must therefore always be read with their coverage. This
is a data-coverage limit, not permission to infer quality from a transfer fee.
