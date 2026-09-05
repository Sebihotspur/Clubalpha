"""Normalize frozen prediction slates for cumulative research learning.

The first Clubalpha research slate stored the native Contextual Interaction
shape. Official slates deliberately store a smaller public/audit shape. This
module provides a lossless, read-only bridge so both can feed the same research
loop without mutating either frozen archive.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

from clubalpha.contextual_backtest import RESULT_VERSION


PREDICTION_FORMATS = {"contextual", "official_shadow"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _official_probabilities(probabilities: dict[str, Any]) -> dict[str, Any]:
    over_2_5 = float(probabilities["over_2_5"])
    over_3_5 = float(probabilities["over_3_5"])
    btts_yes = float(probabilities["btts_yes"])
    return {
        "home_win": float(probabilities["home_win"]),
        "draw": float(probabilities["draw"]),
        "away_win": float(probabilities["away_win"]),
        "over": {"2.5": over_2_5, "3.5": over_3_5},
        "under": {"2.5": 1.0 - over_2_5, "3.5": 1.0 - over_3_5},
        "btts_yes": btts_yes,
        "btts_no": 1.0 - btts_yes,
    }


def _mapped_base_prediction(
    official: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    fixture = official["fixture"]
    source_fixture = source["fixture"]
    if (
        source_fixture["home_team"] != fixture["home_team"]
        or source_fixture["away_team"] != fixture["away_team"]
    ):
        raise ValueError("official prediction changes its source fixture identity")
    mapped = copy.deepcopy(source)
    mapped["fixture"] = {
        **source_fixture,
        **fixture,
        "source_scope": source_fixture.get(
            "source_scope", "premier_league_current"
        ),
        "finished": False,
        "cancelled": False,
    }
    mapped["predicted_xg"] = copy.deepcopy(
        official["model"]["base_predicted_xg"]
    )
    mapped["fixture_intelligence"] = copy.deepcopy(
        official["model"]["fixture_intelligence"]
    )
    return mapped


def normalize_official_cycle(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    source_base_predictions: Iterable[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Adapt an official slate to the immutable contextual research contract."""

    official_rows = list(predictions)
    result_rows = list(results)
    source_rows = list(source_base_predictions)
    source_by_id = {
        int(row["fixture"]["match_id"]): row for row in source_rows
    }
    if len(source_by_id) != len(source_rows):
        raise ValueError("source base predictions contain duplicate match ids")

    normalized_predictions = []
    mapped_base_predictions = []
    for row in official_rows:
        model = row["model"]
        source_id = int(model["source_prediction_match_id"])
        source = source_by_id.get(source_id)
        if source is None:
            raise ValueError(
                f"official prediction has no source base match {source_id}"
            )
        mapped = _mapped_base_prediction(row, source)
        mapped_base_predictions.append(mapped)
        normalized_predictions.append(
            {
                "contextual_interaction_version": (
                    "clubalpha_official_research_adapter_v1"
                ),
                "status": "official_shadow_adapted_for_research",
                "fixture": copy.deepcopy(mapped["fixture"]),
                "baseline": {
                    "prediction_version": source.get("prediction_version"),
                    "predicted_xg": copy.deepcopy(model["base_predicted_xg"]),
                    "probabilities": copy.deepcopy(source["probabilities"]),
                },
                "directional_context": {
                    "home_attack": copy.deepcopy(model["context"]["home_attack"]),
                    "away_attack": copy.deepcopy(model["context"]["away_attack"]),
                },
                "contextual": {
                    "predicted_xg": copy.deepcopy(model["predicted_xg"]),
                    "probabilities": _official_probabilities(
                        model["probabilities"]
                    ),
                    "most_likely_scorelines": copy.deepcopy(
                        model["most_likely_scorelines"]
                    ),
                },
                "decision_boundaries": {
                    "source_prediction_mutated": False,
                    "official_pick_used_as_research_target": False,
                    "capital_deployment_ready": False,
                },
                "source_official_pick": copy.deepcopy(row["official_pick"]),
            }
        )

    normalized_results = []
    for row in result_rows:
        normalized = copy.deepcopy(row)
        normalized["result_version"] = RESULT_VERSION
        normalized_results.append(normalized)
    return normalized_predictions, normalized_results, mapped_base_predictions


def bind_lineups_to_fixtures(
    snapshot: dict[str, Any], predictions: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Bind each dated lineup projection to its cycle fixture explicitly."""

    clubs_by_team = {
        int(club["team_id"]): club for club in snapshot.get("clubs") or []
    }
    bound = []
    for prediction in predictions:
        fixture = prediction["fixture"]
        match_id = int(fixture["match_id"])
        for side, opponent_side in (("home", "away"), ("away", "home")):
            team_id = int(fixture[f"{side}_team_id"])
            club = clubs_by_team.get(team_id)
            if club is None:
                raise ValueError(
                    f"lineup snapshot has no club for fixture team {team_id}"
                )
            row = copy.deepcopy(club)
            row["next_fixture"] = {
                "match_id": match_id,
                "kickoff_utc": fixture["kickoff_utc"],
                "venue": side,
                "opponent": fixture[f"{opponent_side}_team"],
            }
            bound.append(row)
    return {
        "snapshot_version": (
            f"{snapshot.get('snapshot_version', 'unknown')}_fixture_bound"
        ),
        "clubs": bound,
    }


def normalize_cycle_data(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
    source_base_predictions: Iterable[dict[str, Any]],
    lineup_snapshot: dict[str, Any],
    *,
    prediction_format: str,
) -> dict[str, Any]:
    if prediction_format not in PREDICTION_FORMATS:
        raise ValueError(f"unsupported research prediction format: {prediction_format}")
    prediction_rows = list(predictions)
    result_rows = list(results)
    base_rows = list(source_base_predictions)
    if prediction_format == "official_shadow":
        prediction_rows, result_rows, base_rows = normalize_official_cycle(
            prediction_rows, result_rows, base_rows
        )
    return {
        "prediction_format": prediction_format,
        "predictions": prediction_rows,
        "results": result_rows,
        "base_predictions": base_rows,
        "lineup_snapshot": bind_lineups_to_fixtures(
            lineup_snapshot, prediction_rows
        ),
    }


def load_registered_cycle(root: Path, cycle: dict[str, Any]) -> dict[str, Any]:
    prediction_format = str(cycle.get("prediction_format") or "contextual")
    archive_value = cycle.get("archive") or cycle.get("contextual_archive")
    if not archive_value:
        raise ValueError("research cycle has no archive")
    archive = root / str(archive_value)
    normalized = normalize_cycle_data(
        load_jsonl(archive / "predictions.jsonl"),
        load_jsonl(archive / "results.jsonl"),
        load_jsonl(root / cycle["base_predictions"]),
        load_json(root / cycle["lineup_snapshot"]),
        prediction_format=prediction_format,
    )
    normalized.update(
        {
            "cycle_id": str(cycle["cycle_id"]),
            "archive": archive,
            "goal_model": load_json(root / cycle["goal_model_artifact"]),
        }
    )
    return normalized
