"""Separate national-team evidence for players in Clubalpha's club universe.

International matches are useful for workload, availability, role, and recent
condition.  They are deliberately kept outside Club Form and the locked Player
Alpha formula because national-team opposition and tactical context are not
directly comparable with club football.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


EXCLUDED_COMPETITION_TOKENS = (
    "women",
    "club friendlies",
    "champions league",
    "europa league",
    "conference league",
    "youth league",
    "super cup",
    "libertadores",
    "sudamericana",
)

NATIONAL_TEAM_COMPETITION_TOKENS = (
    "nations league",
    "world cup",
    "friendlies",
    "qualification",
    "cup of nations",
    "copa america",
    "gold cup",
    "euro",
    "olympic",
    "fifa asean cup",
)

SUM_METRICS = (
    "goals",
    "non_penalty_goals",
    "assists",
    "expected_goals",
    "expected_assists",
    "chances_created",
    "total_shots",
    "ShotsOnTarget",
    "touches_opp_box",
    "passes_into_final_third",
    "line_breaking_passes",
    "dribbles_succeeded",
    "matchstats.headers.tackles",
    "interceptions",
    "recoveries",
    "defensive_actions",
    "clearances",
)

PER_90_METRICS = tuple(
    metric
    for metric in SUM_METRICS
    if metric not in {"goals", "non_penalty_goals", "assists"}
)


def is_national_team_competition(league: dict[str, Any]) -> bool:
    """Return whether one FotMob daily-feed group is a national-team event."""

    if str(league.get("ccode") or "").upper() != "INT":
        return False
    name = str(league.get("name") or "").lower()
    if any(token in name for token in EXCLUDED_COMPETITION_TOKENS):
        return False
    return any(token in name for token in NATIONAL_TEAM_COMPETITION_TOKENS)


def metric_value(row: dict[str, Any], key: str) -> float | None:
    value = ((row.get("metrics") or {}).get(key) or {}).get("value")
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_pair(value: Any) -> tuple[int | None, int | None]:
    text = str(value or "").replace(":", "-")
    parts = [part.strip() for part in text.split("-")]
    if len(parts) < 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def enrich_player_match(
    row: dict[str, Any],
    fixture: dict[str, Any],
    covered_player: dict[str, Any],
) -> dict[str, Any]:
    """Attach club identity and national-team result to a player match row."""

    home_score, away_score = score_pair(fixture.get("score"))
    player_team_id = int(row["team_id"])
    if player_team_id == int(fixture["home_team_id"]):
        opponent_id = fixture["away_team_id"]
        opponent = fixture["away_team"]
        venue = "home"
        goals_for, goals_against = home_score, away_score
    elif player_team_id == int(fixture["away_team_id"]):
        opponent_id = fixture["home_team_id"]
        opponent = fixture["home_team"]
        venue = "away"
        goals_for, goals_against = away_score, home_score
    else:
        opponent_id = None
        opponent = None
        venue = None
        goals_for, goals_against = None, None

    result = None
    if goals_for is not None and goals_against is not None:
        result = "W" if goals_for > goals_against else "L" if goals_for < goals_against else "D"

    return {
        **row,
        "covered_clubs": sorted(covered_player.get("clubs") or []),
        "covered_positions": sorted(covered_player.get("positions") or []),
        "international_team_id": player_team_id,
        "international_team": row.get("team"),
        "opponent_id": opponent_id,
        "opponent": opponent,
        "venue": venue,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "result": result,
    }


def summarize_player_matches(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate one international-window summary per covered player."""

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["player_id"])].append(row)

    output: list[dict[str, Any]] = []
    for player_id, player_rows in grouped.items():
        ordered = sorted(
            player_rows,
            key=lambda row: (str(row.get("kickoff_utc") or ""), int(row["match_id"])),
        )
        minutes = sum(metric_value(row, "minutes_played") or 0.0 for row in ordered)
        totals = {
            metric: round(
                sum(metric_value(row, metric) or 0.0 for row in ordered), 4
            )
            for metric in SUM_METRICS
        }
        ratings = [
            (metric_value(row, "rating_title"), metric_value(row, "minutes_played") or 0.0)
            for row in ordered
            if metric_value(row, "rating_title") is not None
        ]
        rating_weight = sum(max(weight, 1.0) for _, weight in ratings)
        average_rating = (
            sum(float(rating) * max(weight, 1.0) for rating, weight in ratings)
            / rating_weight
            if rating_weight
            else None
        )
        per_90 = {
            metric: round(90.0 * totals[metric] / minutes, 4)
            for metric in PER_90_METRICS
            if minutes > 0
        }
        results = [row.get("result") for row in ordered]
        output.append(
            {
                "player_id": player_id,
                "player": ordered[-1].get("player"),
                "covered_clubs": sorted(
                    {
                        club
                        for row in ordered
                        for club in row.get("covered_clubs") or []
                    }
                ),
                "covered_positions": sorted(
                    {
                        position
                        for row in ordered
                        for position in row.get("covered_positions") or []
                        if position
                    }
                ),
                "international_teams": sorted(
                    {str(row.get("international_team")) for row in ordered if row.get("international_team")}
                ),
                "appearances": len(ordered),
                "starts": sum(row.get("is_starter") is True for row in ordered),
                "minutes": round(minutes, 1),
                "record": {
                    "wins": results.count("W"),
                    "draws": results.count("D"),
                    "losses": results.count("L"),
                },
                "average_rating": round(average_rating, 3) if average_rating is not None else None,
                "totals": totals,
                "per_90": per_90,
                "match_ids": [int(row["match_id"]) for row in ordered],
                "last_kickoff_utc": ordered[-1].get("kickoff_utc"),
                "workload_band": (
                    "high" if minutes >= 180 else "medium" if minutes >= 90 else "low"
                ),
            }
        )
    return sorted(output, key=lambda row: (-float(row["minutes"]), str(row["player"])))

