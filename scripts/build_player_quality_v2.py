#!/usr/bin/env python3
"""Build Clubalpha v2 Alpha Ability grades and team attack/defence ratings.

Reads the normalized foundation and domestic-history layers, aggregates each
current squad player's previous-season evidence, scores all five positions, and
writes a compact audit. Where v1 grades are present it also emits a
side-by-side comparison so no rating changes without an attributable reason.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.player_quality_v2 import (  # noqa: E402
    build_features,
    build_match_index,
    player_league_offset,
    resolved_formula,
    score_population,
    scoring_position,
    team_ratings,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(materialized)


def competition_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("competition_id"), row.get("competition"))
        bucket = buckets.setdefault(
            key,
            {
                "competition_id": row.get("competition_id"),
                "competition": row.get("competition"),
                "match_ids": set(),
                "minutes": 0.0,
            },
        )
        bucket["match_ids"].add(row.get("match_id"))
        minutes = ((row.get("metrics") or {}).get("minutes_played") or {}).get("value")
        bucket["minutes"] += float(minutes or 0.0)
    return [
        {
            "competition_id": bucket["competition_id"],
            "competition": bucket["competition"],
            "matches": len(bucket["match_ids"]),
            "minutes": round(bucket["minutes"], 3),
        }
        for bucket in sorted(buckets.values(), key=lambda item: str(item["competition"]))
    ]


def duplicate_match_player_keys(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A player must not appear twice for the same match.

    The domestic collector and the foundation collector can both hold a fixture
    when a target club plays in a competition both layers cover.
    """

    seen: dict[tuple[Any, Any], int] = defaultdict(int)
    for row in rows:
        seen[(row.get("match_id"), row.get("player_id"))] += 1
    return [
        {"match_id": match_id, "player_id": player_id, "rows": count}
        for (match_id, player_id), count in sorted(seen.items(), key=lambda item: -item[1])
        if count > 1
    ]


def dedupe_match_player_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep the first row per (match, player), preferring the richer metric set."""

    best: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in rows:
        key = (row.get("match_id"), row.get("player_id"))
        current = best.get(key)
        if current is None or len(row.get("metrics") or {}) > len(current.get("metrics") or {}):
            best[key] = row
    return list(best.values()), len(rows) - len(best)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foundation-dir", type=Path, default=ROOT / "data/processed/foundation")
    parser.add_argument("--domestic-dir", type=Path, default=ROOT / "data/processed/domestic_history")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/player_quality_v2")
    parser.add_argument("--config", type=Path, default=ROOT / "config/player-quality-clubalpha-v2.json")
    parser.add_argument("--audit", type=Path, default=ROOT / "reports/player-quality-v2-audit.json")
    parser.add_argument(
        "--v1-grades",
        type=Path,
        default=ROOT / "data/processed/player_quality/player_grades.jsonl",
        help="Optional v1 output for the side-by-side comparison.",
    )
    args = parser.parse_args()

    required = {
        "squads": args.foundation_dir / "squads.jsonl",
        "teams": args.foundation_dir / "teams.json",
        "fixtures": args.foundation_dir / "fixtures.jsonl",
        "historical player-match stats": args.foundation_dir / "historical_match_player_stats.jsonl",
    }
    missing = [f"{label}: {path}" for label, path in required.items() if not path.exists()]
    if missing:
        raise SystemExit(
            "Missing foundation inputs. Run pull_fotmob_foundation.py first:\n" + "\n".join(missing)
        )

    print("[1/6] Load normalized layers")
    config = load_json(args.config)
    squads = load_jsonl(required["squads"])
    teams = load_json(required["teams"])
    foundation_rows = load_jsonl(required["historical player-match stats"])
    foundation_fixtures = load_jsonl(required["fixtures"])
    domestic_rows = load_jsonl(args.domestic_dir / "match_player_stats.jsonl")
    domestic_fixtures = load_jsonl(args.domestic_dir / "fixtures.jsonl")
    season_rows = [
        *load_jsonl(args.foundation_dir / "season_player_stats.jsonl"),
        *load_jsonl(args.domestic_dir / "season_player_stats.jsonl"),
    ]

    raw_rows = [*foundation_rows, *domestic_rows]
    duplicates = duplicate_match_player_keys(raw_rows)
    historical_rows, dropped = dedupe_match_player_rows(raw_rows)
    if dropped:
        print(f"      Dropped {dropped} duplicate match-player rows across layers")

    match_index = build_match_index([*foundation_fixtures, *domestic_fixtures])
    team_leagues = {
        int(team["team_id"]): team.get("primary_league_id")
        for team in teams
        if team.get("team_id") is not None
    }
    print(
        f"      {len(squads)} squad rows, {len(historical_rows)} player-match rows, "
        f"{len(match_index)} indexed fixtures"
    )

    print("[2/6] Aggregate features for the five populations")
    rows_by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in historical_rows:
        if row.get("player_id") is not None:
            rows_by_player[int(row["player_id"])].append(row)
    season_by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in season_rows:
        if row.get("participant_id") is not None:
            season_by_player[int(row["participant_id"])].append(row)

    teams_by_id = {int(team["team_id"]): team for team in teams}
    features: list[dict[str, Any]] = []
    unmapped_roles: dict[str, int] = defaultdict(int)

    for squad in squads:
        spos = scoring_position(squad.get("position"), squad.get("squad_group"))
        if not spos:
            unmapped_roles[str(squad.get("squad_group"))] += 1
            continue
        player_id = int(squad["player_id"])
        rows = rows_by_player.get(player_id, [])
        league = player_league_offset(rows, match_index, team_leagues, config)
        feature_values, flags = build_features(
            rows, season_by_player.get(player_id, []), spos, config
        )
        current_team = teams_by_id.get(int(squad["team_id"]), {})
        features.append(
            {
                "formula_version": config["version"],
                "player_id": player_id,
                "player": squad.get("player"),
                "current_team_id": int(squad["team_id"]),
                "current_team": squad.get("team"),
                "current_position": squad.get("position"),
                "squad_group": squad.get("squad_group"),
                "scoring_position": spos,
                "age": squad.get("age"),
                "current_competition_flags": {
                    "premier_league_2026_27": bool(current_team.get("premier_league_2026_27")),
                    "ucl_status": current_team.get("ucl_status"),
                },
                "league_quality": league,
                "sample": {
                    "season": "2025/2026",
                    "competitions": competition_breakdown(rows),
                    "matches": len({row.get("match_id") for row in rows}),
                    "minutes": league["minutes"],
                    "historical_team_ids": sorted(
                        {int(row["team_id"]) for row in rows if row.get("team_id") is not None}
                    ),
                },
                "features": feature_values,
                "quality_flags": sorted(set(flags)),
            }
        )

    feature_count = write_jsonl(args.output_dir / "player_features.jsonl", features)

    print("[3/6] Score, standardise, and shrink")
    grades = score_population(features, config)
    grades.sort(key=lambda row: (row["scoring_position"], -row["alpha_ability_z"], row["player"]))
    grade_count = write_jsonl(args.output_dir / "player_grades.jsonl", grades)

    print("[4/6] Team attack and defence ratings")
    ratings = team_ratings(grades, config)
    rating_count = write_jsonl(args.output_dir / "team_ratings.jsonl", ratings)

    print("[5/6] Compare against the WCALPHA v1 baseline")
    comparison = build_comparison(grades, load_jsonl(args.v1_grades))

    print("[6/6] Audit")
    audit = build_audit(features, grades, ratings, config, comparison)
    audit["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    audit["inputs"] = {
        "squad_rows": len(squads),
        "foundation_match_player_rows": len(foundation_rows),
        "domestic_match_player_rows": len(domestic_rows),
        "match_player_rows_after_dedupe": len(historical_rows),
        "duplicate_match_player_keys": len(duplicates),
        "duplicate_sample": duplicates[:10],
        "season_player_stat_rows": len(season_rows),
        "indexed_fixtures": len(match_index),
        "squad_rows_without_scoring_role": dict(sorted(unmapped_roles.items())),
    }
    write_json(args.audit, audit)

    print(f"Features: {feature_count}")
    print(f"Grades: {grade_count}")
    print(f"Team ratings: {rating_count}")
    print(f"Duplicate match-player keys: {len(duplicates)}")
    print(f"Audit: {args.audit}")
    return 0


def build_comparison(
    grades: list[dict[str, Any]],
    v1_grades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rank-and-score movement between the v1 baseline and v2."""

    if not v1_grades:
        return {"available": False, "note": "No v1 grade file found; run build_player_quality.py to enable."}

    v1_by_player = {int(row["player_id"]): row for row in v1_grades}
    shared = [row for row in grades if int(row["player_id"]) in v1_by_player]
    if not shared:
        return {"available": False, "note": "No overlapping players between v1 and v2."}

    movements = []
    for row in shared:
        old = v1_by_player[int(row["player_id"])]
        movements.append(
            {
                "player_id": row["player_id"],
                "player": row["player"],
                "team": row["current_team"],
                "scoring_position": row["scoring_position"],
                "v1_alpha_ability_z": old.get("alpha_ability_z"),
                "v2_alpha_ability_z": row["alpha_ability_z"],
                "delta": round(row["alpha_ability_z"] - float(old.get("alpha_ability_z") or 0.0), 3),
                "minutes": row["minutes"],
                "v1_league_multiplier": (old.get("league_quality") or {}).get("multiplier"),
                "v2_league_offset": (row.get("league_quality") or {}).get("offset"),
            }
        )
    movements.sort(key=lambda item: abs(item["delta"]), reverse=True)
    deltas = [item["delta"] for item in movements]
    return {
        "available": True,
        "compared_players": len(movements),
        "v1_only_players": len(v1_by_player) - len(shared),
        "v2_only_players": len(grades) - len(shared),
        "mean_absolute_delta": round(statistics.mean(abs(value) for value in deltas), 4),
        "median_absolute_delta": round(statistics.median(abs(value) for value in deltas), 4),
        "largest_moves": movements[:25],
        "note": (
            "v1 and v2 are on different scales by design: v2 standardises each position to "
            "mean 0 and SD 1, so a delta reflects both the formula change and the rescaling."
        ),
    }


def build_audit(
    features: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    ratings: list[dict[str, Any]],
    config: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
        result: dict[str, int] = defaultdict(int)
        for row in rows:
            result[str(row.get(field))] += 1
        return dict(sorted(result.items()))

    leaders: dict[str, list[dict[str, Any]]] = {}
    position_scales: dict[str, Any] = {}
    for spos in ("FW", "CM", "CB", "FB", "GK"):
        members = [row for row in grades if row["scoring_position"] == spos]
        if not members:
            continue
        ranked = sorted(members, key=lambda row: row["alpha_ability_z"], reverse=True)
        leaders[spos] = [
            {
                "player_id": row["player_id"],
                "player": row["player"],
                "team": row["current_team"],
                "alpha_ability_z": row["alpha_ability_z"],
                "standardised_z": row["standardised_z"],
                "shrinkage_weight": row["shrinkage_weight"],
                "minutes": row["minutes"],
                "coverage_pct": row["coverage_pct"],
                "league_offset": (row.get("league_quality") or {}).get("offset"),
            }
            for row in ranked[:10]
        ]
        standardised = [row["standardised_z"] for row in members]
        position_scales[spos] = {
            "graded": len(members),
            "reference_players": members[0]["reference_players"],
            "standardised_min": round(min(standardised), 3),
            "standardised_max": round(max(standardised), 3),
            "graded_min": round(min(row["alpha_ability_z"] for row in members), 3),
            "graded_max": round(max(row["alpha_ability_z"] for row in members), 3),
        }

    metric_availability: dict[str, dict[str, Any]] = {}
    for spos in ("FW", "CM", "CB", "FB", "GK"):
        members = [row for row in features if row["scoring_position"] == spos]
        if not members:
            continue
        formula = resolved_formula(spos, config)
        metric_availability[spos] = {
            key: {
                "players_with_value": sum(
                    1 for row in members if (row["features"] or {}).get(key) is not None
                ),
                "players": len(members),
            }
            for key in formula
        }

    flag_counts: dict[str, int] = defaultdict(int)
    for row in features:
        for flag in row.get("quality_flags") or []:
            flag_counts[flag] += 1

    league_resolution: dict[str, int] = defaultdict(int)
    for row in features:
        for source in (row["league_quality"].get("resolution") or {}):
            league_resolution[source] += 1

    rated = [row for row in ratings if row.get("attack_rating") is not None]
    return {
        "formula_version": config["version"],
        "scope": (
            "Current 2026/27 PL, confirmed UCL, and UCL play-off squads; 2025/26 PL/UCL plus "
            "club-filtered domestic evidence"
        ),
        "feature_players": len(features),
        "feature_players_by_position": counts(features, "scoring_position"),
        "graded_players": len(grades),
        "graded_players_by_position": counts(grades, "scoring_position"),
        "players_without_historical_minutes": sum(
            1 for row in features if row["sample"]["minutes"] <= 0
        ),
        "position_scales": position_scales,
        "metric_availability": metric_availability,
        "quality_flags": dict(sorted(flag_counts.items())),
        "league_offset_resolution_players": dict(sorted(league_resolution.items())),
        "league_offset_unresolved_players": sum(
            1 for row in features if not row["league_quality"].get("fully_resolved")
        ),
        "policy": {
            "weighting": config["weighting_policy"]["mode"],
            "standardisation": config["standardisation"]["scope"],
            "shrinkage_constant": config["shrinkage"]["constant"],
            "peer_minimum_minutes": config["peer_method"]["peer_minimum_minutes"],
            "minimum_attempts": config["minimum_attempts"],
            "league_quality_method": config["league_quality"]["method"],
        },
        "leaders": leaders,
        "team_ratings": {
            "teams": len(ratings),
            "teams_with_ratings": len(rated),
            "top_attack": sorted(
                (
                    {"team": row["team"], "attack_rating": row["attack_rating"]}
                    for row in rated
                ),
                key=lambda row: row["attack_rating"],
                reverse=True,
            )[:10],
            "top_defence": sorted(
                (
                    {"team": row["team"], "defence_rating": row["defence_rating"]}
                    for row in rated
                    if row.get("defence_rating") is not None
                ),
                key=lambda row: row["defence_rating"],
                reverse=True,
            )[:10],
        },
        "v1_comparison": comparison,
    }


if __name__ == "__main__":
    raise SystemExit(main())
