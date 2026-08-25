"""Market-relevant Alpha context after a lineup projection exists.

This module does not alter the locked Alpha Ability formula. It reuses the
already-oriented metric z-scores inside that grade to describe three narrower
jobs: scoring threat, chance creation, and defensive prevention. Each job is
standardised only against the same Alpha position, reliability-shrunk, and
then weighted by the fixture-specific expected minutes supplied by Squad
Selection v2.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Iterable


ROLE_ALPHA_VERSION = "clubalpha_role_aware_alpha_v1"

PILLAR_METRICS: dict[str, dict[str, tuple[str, ...]]] = {
    "scoring_threat": {
        "FW": ("npg90", "xg90", "bt90", "sot90"),
        "CM": ("gxg90", "bt90"),
        "FB": ("gxg90",),
        "CB": ("ga90",),
        "GK": (),
    },
    "chance_creation": {
        "FW": ("kp90", "axa90", "pf390", "lbp90", "drib90"),
        "CM": ("axa90", "kp90", "pf390", "lbp90", "drib90"),
        "FB": ("axa90", "kp90", "lbp90", "drib90", "crosspct"),
        "CB": ("passpct", "lbp90"),
        "GK": ("dist",),
    },
    "defensive_prevention": {
        "FW": ("press90",),
        "CM": ("gnd", "aer", "rec90", "disp90"),
        "FB": ("err90", "tkl90", "gnd", "int90", "drp90", "aer"),
        "CB": ("err90", "aer", "tkl90", "int90", "gnd", "drp90", "clrblk90"),
        "GK": ("gprev90", "claims90", "sweep90", "dist", "err90"),
    },
}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pillar_raw(grade: dict[str, Any], pillar: str) -> tuple[float | None, list[str]]:
    position = str(grade.get("scoring_position") or "")
    allowed = PILLAR_METRICS[pillar].get(position, ())
    values = []
    supplied = []
    metrics = grade.get("metrics") or {}
    for key in allowed:
        value = _number((metrics.get(key) or {}).get("z"))
        if value is None:
            continue
        values.append(value)
        supplied.append(key)
    return (sum(values) / len(values), supplied) if values else (None, [])


def _reference_distributions(
    grades: list[dict[str, Any]], minimum_minutes: float
) -> dict[tuple[str, str], dict[str, float]]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for grade in grades:
        if float(_number(grade.get("minutes")) or 0.0) < minimum_minutes:
            continue
        position = str(grade.get("scoring_position") or "")
        for pillar in PILLAR_METRICS:
            raw, _ = _pillar_raw(grade, pillar)
            if raw is not None:
                values[(position, pillar)].append(raw)
    output = {}
    for key, population in values.items():
        if len(population) < 2:
            continue
        sample_sd = statistics.stdev(population)
        if sample_sd <= 0:
            continue
        output[key] = {
            "mean": statistics.mean(population),
            "sample_sd": sample_sd,
            "players": len(population),
        }
    return output


def build_role_aware_alpha(
    grades: Iterable[dict[str, Any]],
    projected_players: Iterable[dict[str, Any]],
    *,
    minimum_reference_minutes: float = 700.0,
) -> dict[str, Any]:
    """Join locked player grades to projected minutes and aggregate their roles."""

    grade_rows = list(grades)
    grades_by_player = {int(row["player_id"]): row for row in grade_rows}
    references = _reference_distributions(grade_rows, minimum_reference_minutes)
    players = []
    for projected in projected_players:
        player_id = int(projected["player_id"])
        grade = grades_by_player.get(player_id)
        if grade is None:
            players.append(
                {
                    "player_id": player_id,
                    "player": projected.get("player"),
                    "expected_minutes": float(projected.get("expected_minutes") or 0.0),
                    "selection_role": projected.get("selection_role"),
                    "alpha_available": False,
                    "alpha_ability_z": None,
                    "pillars": {},
                }
            )
            continue

        position = str(grade.get("scoring_position") or "")
        reliability = min(1.0, max(0.0, float(_number(grade.get("shrinkage_weight")) or 0.0)))
        pillars = {}
        for pillar in PILLAR_METRICS:
            raw, supplied = _pillar_raw(grade, pillar)
            reference = references.get((position, pillar))
            if raw is None or reference is None:
                pillars[pillar] = {
                    "z": None,
                    "metrics": supplied,
                    "metric_count": len(supplied),
                    "reference_players": (reference or {}).get("players", 0),
                }
                continue
            z_before_reliability = (raw - reference["mean"]) / reference["sample_sd"]
            z_before_reliability = min(3.0, max(-3.0, z_before_reliability))
            pillars[pillar] = {
                "z": round(z_before_reliability * reliability, 6),
                "z_before_reliability": round(z_before_reliability, 6),
                "metrics": supplied,
                "metric_count": len(supplied),
                "reference_players": int(reference["players"]),
            }
        players.append(
            {
                "player_id": player_id,
                "player": projected.get("player") or grade.get("player"),
                "expected_minutes": float(projected.get("expected_minutes") or 0.0),
                "selection_role": projected.get("selection_role"),
                "alpha_position": position,
                "alpha_available": _number(grade.get("alpha_ability_z")) is not None,
                "alpha_ability_z": _number(grade.get("alpha_ability_z")),
                "shrinkage_weight": reliability,
                "pillars": pillars,
            }
        )

    def aggregate_value(value_getter, eligible_getter=lambda row: True) -> dict[str, Any]:
        weighted = 0.0
        covered_minutes = 0.0
        eligible_minutes = 0.0
        for row in players:
            if not eligible_getter(row):
                continue
            player_minutes = float(row["expected_minutes"])
            eligible_minutes += player_minutes
            value = value_getter(row)
            if value is None:
                continue
            weighted += player_minutes * float(value)
            covered_minutes += player_minutes
        return {
            # Missing player context is neutral on the shared team scale; it
            # must reduce coverage rather than inflate the average of whichever
            # players happen to be graded.
            "z": round(weighted / eligible_minutes, 6) if eligible_minutes > 0 else None,
            "covered_expected_minutes": round(covered_minutes, 3),
            "eligible_expected_minutes": round(eligible_minutes, 3),
            "coverage": round(covered_minutes / eligible_minutes, 4)
            if eligible_minutes > 0
            else 0.0,
        }

    aggregates = {
        "overall_alpha_ability": aggregate_value(lambda row: row.get("alpha_ability_z")),
        "attacking_unit_alpha_ability": aggregate_value(
            lambda row: row.get("alpha_ability_z"),
            lambda row: row.get("selection_role") in {"MID", "FWD"},
        ),
        "defensive_unit_alpha_ability": aggregate_value(
            lambda row: row.get("alpha_ability_z"),
            lambda row: row.get("selection_role") in {"GK", "DEF", "MID"},
        ),
    }
    for pillar in PILLAR_METRICS:
        aggregates[pillar] = aggregate_value(
            lambda row, key=pillar: (row.get("pillars", {}).get(key) or {}).get("z"),
            lambda row, key=pillar: (
                bool(PILLAR_METRICS[key].get(str(row.get("alpha_position") or ""), ()))
                if row.get("alpha_position")
                else (
                    row.get("selection_role") != "GK"
                    if key == "scoring_threat"
                    else True
                )
            ),
        )

    total_minutes = sum(float(row["expected_minutes"]) for row in players)
    return {
        "version": ROLE_ALPHA_VERSION,
        "players": players,
        "team_aggregates": aggregates,
        "coverage": {
            "projected_players": len(players),
            "players_with_alpha": sum(row["alpha_available"] for row in players),
            "projected_expected_minutes": round(total_minutes, 3),
            "alpha_expected_minute_coverage": aggregates["overall_alpha_ability"]["coverage"],
        },
        "decision_boundaries": {
            "changes_locked_alpha_ability": False,
            "used_to_select_players": False,
            "uses_fixture_expected_minutes": True,
            "market_probabilities_created": False,
        },
    }


def attach_role_aware_alpha(
    projection: dict[str, Any],
    grades: Iterable[dict[str, Any]],
    *,
    minimum_reference_minutes: float = 700.0,
) -> dict[str, Any]:
    """Return a selection projection enriched after its XI has been frozen."""

    context = build_role_aware_alpha(
        grades,
        projection.get("players") or [],
        minimum_reference_minutes=minimum_reference_minutes,
    )
    alpha_by_player = {row["player_id"]: row for row in context["players"]}
    enriched_players = []
    for player in projection.get("players") or []:
        alpha = alpha_by_player[int(player["player_id"])]
        enriched_players.append(
            {
                **player,
                "alpha_position": alpha.get("alpha_position"),
                "alpha_ability_z": alpha.get("alpha_ability_z"),
                "alpha_pillars": alpha.get("pillars") or {},
            }
        )
    return {
        **projection,
        "players": enriched_players,
        "role_aware_alpha": {
            "version": context["version"],
            "team_aggregates": context["team_aggregates"],
            "coverage": context["coverage"],
            "decision_boundaries": context["decision_boundaries"],
        },
    }
