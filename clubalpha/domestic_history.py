"""Pure helpers for mapping and filtering club domestic-history samples."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from clubalpha.fotmob import league_matches, normalize_fixture


def build_domestic_competitions(
    teams: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Map relevant current clubs to their previous domestic competition."""

    statuses = set(config["included_ucl_statuses"])
    excluded = {int(value) for value in config.get("excluded_league_ids") or []}
    overrides = config.get("team_league_overrides") or {}
    buckets: dict[tuple[int, str], dict[str, Any]] = {}

    for team in teams:
        team_id = int(team["team_id"])
        override = overrides.get(str(team_id))
        relevant = team.get("ucl_status") in statuses or override is not None
        if not relevant:
            continue

        league_id = int(override["league_id"] if override else team["primary_league_id"])
        if league_id in excluded and not override:
            continue
        season = str(
            (override or {}).get("season")
            or (config.get("league_seasons") or {}).get(str(league_id))
            or config["default_season"]
        )
        league_name = str(
            (override or {}).get("league_name")
            or (config.get("league_names") or {}).get(str(league_id))
            or team.get("primary_league")
            or f"League {league_id}"
        )
        key = (league_id, season)
        bucket = buckets.setdefault(
            key,
            {
                "league_id": league_id,
                "league_name": league_name,
                "season": season,
                "target_teams": [],
            },
        )
        bucket["target_teams"].append(
            {
                "team_id": team_id,
                "team": team.get("name"),
                "ucl_status": team.get("ucl_status"),
                "override_reason": (override or {}).get("reason"),
            }
        )

    output = []
    for bucket in buckets.values():
        bucket["target_teams"].sort(key=lambda row: (row.get("team") or "", row["team_id"]))
        output.append(bucket)
    return sorted(output, key=lambda row: (row["league_name"], row["league_id"]))


def select_domestic_fixtures(
    league_payload: dict[str, Any],
    competition: dict[str, Any],
) -> list[dict[str, Any]]:
    target_ids = {row["team_id"] for row in competition["target_teams"]}
    selected: list[dict[str, Any]] = []
    for row in league_matches(league_payload):
        home_id = (row.get("home") or {}).get("id") or row.get("homeTeamId")
        away_id = (row.get("away") or {}).get("id") or row.get("awayTeamId")
        if not ({int(value) for value in (home_id, away_id) if value is not None} & target_ids):
            continue
        normalized = normalize_fixture(row, source_scope="domestic_history_previous")
        normalized["competition_id"] = competition["league_id"]
        normalized["competition"] = competition["league_name"]
        normalized["season"] = competition["season"]
        selected.append(normalized)
    return selected


def filter_target_player_rows(
    rows: list[dict[str, Any]],
    competition: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep only target-club players so opponent-only partial seasons cannot grade."""

    target_ids = {row["team_id"] for row in competition["target_teams"]}
    output = []
    for row in rows:
        if int(row["team_id"]) not in target_ids:
            continue
        output.append(
            {
                **row,
                "competition_id": competition["league_id"],
                "competition": competition["league_name"],
                "season": competition["season"],
                "source_scope": "domestic_history_previous",
            }
        )
    return output


def filter_target_stat_rows(
    rows: list[dict[str, Any]],
    competition: dict[str, Any],
) -> list[dict[str, Any]]:
    target_ids = {row["team_id"] for row in competition["target_teams"]}
    return [row for row in rows if row.get("team_id") in target_ids]


def target_fixture_counts(
    fixtures: list[dict[str, Any]],
    competition: dict[str, Any],
) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    target_ids = {row["team_id"] for row in competition["target_teams"]}
    for fixture in fixtures:
        for team_id in (fixture.get("home_team_id"), fixture.get("away_team_id")):
            if team_id in target_ids:
                counts[int(team_id)] += 1
    return dict(counts)
