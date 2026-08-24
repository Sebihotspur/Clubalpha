"""Helpers for the cached multi-season competitive history collector."""

from __future__ import annotations

from typing import Any, Iterable

from clubalpha.fotmob import clip_fixture_to_as_of, league_matches, normalize_fixture


def competition_seasons(config: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for competition in config["competitions"]:
        for season in competition["seasons"]:
            output.append(
                {
                    "key": competition["key"],
                    "name": competition["name"],
                    "fotmob_id": int(competition["fotmob_id"]),
                    "season": season,
                    "source_scope": f"{competition['key']}_history_{season.replace('/', '_')}",
                }
            )
    return output


def normalize_season_fixtures(
    payload: dict[str, Any], competition: dict[str, Any], as_of: str
) -> list[dict[str, Any]]:
    selected = (payload.get("details") or {}).get("selectedSeason")
    if selected != competition["season"]:
        raise RuntimeError(
            f"FotMob returned {selected!r} for {competition['key']}; "
            f"expected {competition['season']!r}"
        )
    fixtures: list[dict[str, Any]] = []
    for source in league_matches(payload):
        row = clip_fixture_to_as_of(
            normalize_fixture(source, source_scope=competition["source_scope"]), as_of
        )
        row.update(
            {
                "competition_id": competition["fotmob_id"],
                "competition": competition["name"],
                "season": competition["season"],
            }
        )
        if row.get("finished") and not row.get("cancelled"):
            fixtures.append(row)
    return fixtures


def dedupe_fixtures(
    fixture_sets: Iterable[Iterable[dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_match: dict[int, dict[str, Any]] = {}
    for fixtures in fixture_sets:
        for row in fixtures:
            by_match[int(row["match_id"])] = dict(row)
    return sorted(
        by_match.values(),
        key=lambda row: (str(row.get("kickoff_utc") or ""), int(row["match_id"])),
    )
