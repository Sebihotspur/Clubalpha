"""Validation and integrity helpers for frozen round-robin experiments."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSON Lines artifact, ignoring blank lines."""

    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fixture_join_key(prediction: dict[str, Any]) -> str:
    """Return the stable key used to reconcile a prediction with a result."""

    fixture = prediction["fixture"]
    return (
        f'{fixture["season"]}|{int(fixture["home_team_id"])}|'
        f'{int(fixture["away_team_id"])}'
    )


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_round_robin(
    predictions: Iterable[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Validate a complete directed double round robin and its summary."""

    rows = list(predictions)
    if not rows:
        raise ValueError("round-robin archive contains no predictions")

    team_names: dict[int, str] = {}
    home_counts: Counter[int] = Counter()
    away_counts: Counter[int] = Counter()
    join_keys: list[str] = []
    seasons: set[str] = set()

    for index, row in enumerate(rows, start=1):
        fixture = row.get("fixture", {})
        probabilities = row.get("probabilities", {})
        try:
            home_id = int(fixture["home_team_id"])
            away_id = int(fixture["away_team_id"])
            home_name = str(fixture["home_team"])
            away_name = str(fixture["away_team"])
            season = str(fixture["season"])
            one_x_two = (
                float(probabilities["home_win"]),
                float(probabilities["draw"]),
                float(probabilities["away_win"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"prediction row {index} is missing required fields") from exc

        if home_id == away_id:
            raise ValueError(f"prediction row {index} has the same home and away team")
        if any(probability < 0 or probability > 1 for probability in one_x_two):
            raise ValueError(f"prediction row {index} contains an invalid 1X2 probability")
        if abs(sum(one_x_two) - 1.0) > 1e-9:
            raise ValueError(f"prediction row {index} 1X2 probabilities do not sum to 1")

        for team_id, team_name in ((home_id, home_name), (away_id, away_name)):
            previous_name = team_names.setdefault(team_id, team_name)
            if previous_name != team_name:
                raise ValueError(f"team ID {team_id} maps to multiple team names")

        home_counts[home_id] += 1
        away_counts[away_id] += 1
        join_keys.append(fixture_join_key(row))
        seasons.add(season)

    team_count = len(team_names)
    expected_fixture_count = team_count * (team_count - 1)
    expected_side_count = team_count - 1
    if len(rows) != expected_fixture_count:
        raise ValueError(
            f"expected {expected_fixture_count} fixtures for {team_count} teams; "
            f"found {len(rows)}"
        )
    if len(set(join_keys)) != len(join_keys):
        raise ValueError("season/home_team_id/away_team_id join keys are not unique")
    if len(seasons) != 1:
        raise ValueError(f"expected one season; found {sorted(seasons)}")

    for team_id, team_name in team_names.items():
        if home_counts[team_id] != expected_side_count:
            raise ValueError(
                f"{team_name} has {home_counts[team_id]} home fixtures; "
                f"expected {expected_side_count}"
            )
        if away_counts[team_id] != expected_side_count:
            raise ValueError(
                f"{team_name} has {away_counts[team_id]} away fixtures; "
                f"expected {expected_side_count}"
            )

    expected_matches_per_team = 2 * expected_side_count
    if int(summary.get("teams", -1)) != team_count:
        raise ValueError("summary team count does not match predictions")
    if int(summary.get("fixtures", -1)) != len(rows):
        raise ValueError("summary fixture count does not match predictions")
    if int(summary.get("matches_per_team", -1)) != expected_matches_per_team:
        raise ValueError("summary matches-per-team count does not match predictions")

    table = summary.get("league_table")
    if not isinstance(table, list) or len(table) != team_count:
        raise ValueError("summary league table does not contain every team")
    table_names = {str(team.get("team")) for team in table}
    if table_names != set(team_names.values()):
        raise ValueError("summary league table team universe does not match predictions")
    if any(int(team.get("matches", -1)) != expected_matches_per_team for team in table):
        raise ValueError("summary league table contains an invalid match count")

    return {
        "season": next(iter(seasons)),
        "teams": team_count,
        "fixtures": len(rows),
        "matches_per_team": expected_matches_per_team,
        "unique_join_keys": len(set(join_keys)),
        "team_ids": sorted(team_names),
    }


def hash_files(repo_root: Path, relative_paths: Iterable[str]) -> dict[str, str]:
    """Hash repository-relative files and fail when an input is missing."""

    hashes: dict[str, str] = {}
    for relative_path in relative_paths:
        path = repo_root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"archive input is missing: {relative_path}")
        hashes[relative_path] = sha256_file(path)
    return hashes


def verify_hashes(repo_root: Path, expected: dict[str, str]) -> None:
    """Raise if any frozen file is missing or has changed."""

    actual = hash_files(repo_root, expected)
    changed = [path for path, digest in expected.items() if actual[path] != digest]
    if changed:
        raise ValueError("frozen archive integrity failure: " + ", ".join(changed))
