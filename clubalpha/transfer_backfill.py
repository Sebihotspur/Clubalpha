"""Player-centric transfer backfill.

The domestic and foundation collectors are club-filtered: they keep only rows
for clubs in the current PL/UCL universe. A player who spent part of last
season elsewhere is therefore graded on a fragment, and the fragment is biased
— it is usually their settling-in minutes at the new club.

FotMob's ``careerHistory.seasonEntries`` returns one entry per club per season
with per-competition appearance counts, so the shortfall is an exact
reconciliation rather than an estimate. This module turns that ledger into a
list of gaps and keeps the collected rows player-filtered, so no unrelated
opponent player ever enters the grading population on a partial sample.

Pure helpers only: no network calls.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def season_entries(player_payload: dict[str, Any], season: str) -> list[dict[str, Any]]:
    """Every club spell a player recorded in one season.

    A transferred player produces two or more entries for the same season, one
    per club, each carrying its own per-competition appearance counts.
    """

    senior = (
        ((player_payload.get("careerHistory") or {}).get("careerItems") or {}).get("senior") or {}
    )
    return [
        entry
        for entry in (senior.get("seasonEntries") or [])
        if str(entry.get("seasonName") or "") == season
    ]


def expected_ledger(player_payload: dict[str, Any], season: str) -> list[dict[str, Any]]:
    """Flatten a season's club spells into (club, competition, appearances) rows.

    Competitions FotMob reports without a league id — one-off exhibition
    tournaments, for instance — are kept but marked, because they cannot be
    resolved to a fixture list and so cannot be collected.
    """

    ledger: list[dict[str, Any]] = []
    for entry in season_entries(player_payload, season):
        team_id = _int(entry.get("teamId"))
        for tournament in entry.get("tournamentStats") or []:
            appearances = _int(tournament.get("appearances")) or 0
            if appearances <= 0:
                continue
            league_id = _int(tournament.get("leagueId"))
            ledger.append(
                {
                    "team_id": team_id,
                    "team": entry.get("team"),
                    "league_id": league_id,
                    "league": tournament.get("leagueName"),
                    "season": tournament.get("seasonName") or season,
                    "expected_appearances": appearances,
                    "is_friendly": bool(tournament.get("isFriendly")),
                    "resolvable": league_id is not None and not tournament.get("isFriendly"),
                }
            )
    return ledger


def held_appearances(rows: Iterable[dict[str, Any]]) -> dict[tuple[int | None, int | None], set[Any]]:
    """Distinct match ids already held, keyed by (team, competition)."""

    held: dict[tuple[int | None, int | None], set[Any]] = defaultdict(set)
    for row in rows:
        key = (_int(row.get("team_id")), _int(row.get("competition_id")))
        held[key].add(row.get("match_id"))
    return held


def find_gaps(
    ledger: list[dict[str, Any]],
    held: dict[tuple[int | None, int | None], set[Any]],
) -> list[dict[str, Any]]:
    """Compare the provider's ledger against what has actually been collected.

    Status is ``complete`` when the held count meets or exceeds the reported
    appearances, ``partial`` when some are held, and ``absent`` when none are.
    A held count above the ledger is not treated as an error: FotMob's own
    season leaderboards are known to disagree with match detail, and the match
    sample is the more trustworthy of the two.
    """

    gaps: list[dict[str, Any]] = []
    for entry in ledger:
        key = (entry["team_id"], entry["league_id"])
        held_count = len(held.get(key, ()))
        expected = entry["expected_appearances"]
        missing = max(0, expected - held_count)
        if held_count >= expected:
            status = "complete"
        elif held_count > 0:
            status = "partial"
        else:
            status = "absent"
        gaps.append(
            {
                **entry,
                "held_appearances": held_count,
                "missing_appearances": missing,
                "status": status,
            }
        )
    return gaps


def player_gap_summary(
    player_id: int,
    player: str,
    current_team_id: int | None,
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    """One record per player describing how complete their season is."""

    expected = sum(entry["expected_appearances"] for entry in gaps)
    held = sum(entry["held_appearances"] for entry in gaps)
    collectable = [
        entry for entry in gaps if entry["missing_appearances"] > 0 and entry["resolvable"]
    ]
    unresolvable = [
        entry for entry in gaps if entry["missing_appearances"] > 0 and not entry["resolvable"]
    ]
    clubs = sorted({entry["team_id"] for entry in gaps if entry["team_id"] is not None})
    return {
        "player_id": player_id,
        "player": player,
        "current_team_id": current_team_id,
        "clubs_in_season": len(clubs),
        "club_ids": clubs,
        "multi_club_season": len(clubs) > 1,
        "expected_appearances": expected,
        "held_appearances": held,
        "missing_appearances": max(0, expected - held),
        "coverage_pct": round(100.0 * held / expected, 1) if expected else None,
        "collectable_gaps": collectable,
        "unresolvable_gaps": unresolvable,
    }


def targets_by_competition(
    summaries: list[dict[str, Any]],
) -> dict[tuple[int, str], dict[str, Any]]:
    """Group collectable gaps into one fetch per (competition, season).

    Fetching a league once and selecting the fixtures that matter is far
    cheaper than walking each player's history separately, and several players
    frequently share the same missing club-season.
    """

    grouped: dict[tuple[int, str], dict[str, Any]] = {}
    for summary in summaries:
        for gap in summary["collectable_gaps"]:
            key = (int(gap["league_id"]), str(gap["season"]))
            bucket = grouped.setdefault(
                key,
                {
                    "league_id": int(gap["league_id"]),
                    "league": gap["league"],
                    "season": str(gap["season"]),
                    "team_ids": set(),
                    "player_ids": set(),
                    "players_by_team": defaultdict(set),
                },
            )
            if gap["team_id"] is not None:
                bucket["team_ids"].add(int(gap["team_id"]))
                bucket["players_by_team"][int(gap["team_id"])].add(int(summary["player_id"]))
            bucket["player_ids"].add(int(summary["player_id"]))
    return grouped


def filter_backfill_rows(
    rows: list[dict[str, Any]],
    wanted_player_ids: set[int],
    competition: dict[str, Any],
    already_held: set[tuple[Any, Any]],
) -> list[dict[str, Any]]:
    """Keep only the players we are actually backfilling.

    This is the guard that makes the backfill safe. Retaining every player in a
    collected match would hand the grading population thousands of opponents
    represented by one or two games, which is exactly the partial-sample
    problem the club-filtered collectors were built to avoid.
    """

    output: list[dict[str, Any]] = []
    for row in rows:
        player_id = _int(row.get("player_id"))
        if player_id is None or player_id not in wanted_player_ids:
            continue
        if (row.get("match_id"), player_id) in already_held:
            continue
        output.append(
            {
                **row,
                "competition_id": competition["league_id"],
                "competition": competition["league"],
                "season": competition["season"],
                "source_scope": "transfer_backfill",
            }
        )
    return output


def select_team_fixtures(
    league_payload: dict[str, Any],
    team_ids: set[int],
) -> list[dict[str, Any]]:
    """Finished fixtures involving any club we need to backfill."""

    from clubalpha.fotmob import league_matches, normalize_fixture

    selected: list[dict[str, Any]] = []
    for row in league_matches(league_payload):
        home = (row.get("home") or {}).get("id") or row.get("homeTeamId")
        away = (row.get("away") or {}).get("id") or row.get("awayTeamId")
        present = {value for value in (_int(home), _int(away)) if value is not None}
        if not (present & team_ids):
            continue
        fixture = normalize_fixture(row, source_scope="transfer_backfill")
        if fixture["finished"]:
            selected.append(fixture)
    return selected


def backfill_coverage(
    summaries: list[dict[str, Any]],
    collected_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compact provenance for the tracked audit."""

    by_player: dict[int, int] = defaultdict(int)
    for row in collected_rows:
        player_id = _int(row.get("player_id"))
        if player_id is not None:
            by_player[player_id] += 1

    multi_club = [row for row in summaries if row["multi_club_season"]]
    still_missing = [
        row
        for row in summaries
        if row["missing_appearances"] - by_player.get(int(row["player_id"]), 0) > 0
    ]
    return {
        "players_examined": len(summaries),
        "multi_club_players": len(multi_club),
        "players_with_gaps": sum(1 for row in summaries if row["missing_appearances"] > 0),
        "expected_appearances": sum(row["expected_appearances"] for row in summaries),
        "held_before": sum(row["held_appearances"] for row in summaries),
        "rows_collected": len(collected_rows),
        "players_backfilled": len(by_player),
        "players_still_incomplete": len(still_missing),
        "unresolvable_gap_players": sum(1 for row in summaries if row["unresolvable_gaps"]),
        "largest_gaps": sorted(
            (
                {
                    "player_id": row["player_id"],
                    "player": row["player"],
                    "expected": row["expected_appearances"],
                    "held": row["held_appearances"],
                    "missing": row["missing_appearances"],
                    "clubs": row["clubs_in_season"],
                }
                for row in summaries
                if row["missing_appearances"] > 0
            ),
            key=lambda row: -row["missing"],
        )[:25],
    }
