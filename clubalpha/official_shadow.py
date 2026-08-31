"""Validation helpers for immutable official shadow-prediction slates."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Iterable


OUTCOMES = {"home_win", "draw", "away_win"}
CONFIDENCE_LEVELS = {"low", "medium", "high"}


def parse_utc(value: str) -> datetime:
    """Parse an ISO timestamp, requiring an explicit UTC offset."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed


def picked_team(row: dict[str, Any]) -> str:
    """Return the named side for an official 1X2 pick."""

    outcome = row["official_pick"]["outcome"]
    if outcome == "home_win":
        return str(row["fixture"]["home_team"])
    if outcome == "away_win":
        return str(row["fixture"]["away_team"])
    return "Draw"


def validate_predictions(
    predictions: Iterable[dict[str, Any]],
    *,
    expected_round: int,
    expected_fixtures: int,
    as_of_utc: str,
) -> dict[str, Any]:
    """Validate one pre-kickoff official slate and its decision boundaries."""

    rows = list(predictions)
    if len(rows) != expected_fixtures:
        raise ValueError(
            f"expected {expected_fixtures} official fixtures; found {len(rows)}"
        )
    cutoff = parse_utc(as_of_utc)
    match_ids: list[int] = []
    fixtures: list[tuple[int, int]] = []
    confidence = Counter()
    overrides = 0
    for index, row in enumerate(rows, start=1):
        fixture = row.get("fixture") or {}
        model = row.get("model") or {}
        probabilities = model.get("probabilities") or {}
        official_pick = row.get("official_pick") or {}
        try:
            match_id = int(fixture["match_id"])
            home_id = int(fixture["home_team_id"])
            away_id = int(fixture["away_team_id"])
            round_number = int(fixture["round"])
            kickoff = parse_utc(str(fixture["kickoff_utc"]))
            one_x_two = (
                float(probabilities["home_win"]),
                float(probabilities["draw"]),
                float(probabilities["away_win"]),
            )
            outcome = str(official_pick["outcome"])
            confidence_label = str(official_pick["confidence"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"official prediction row {index} is missing required fields"
            ) from exc
        if round_number != expected_round:
            raise ValueError(f"official prediction row {index} has the wrong round")
        if kickoff <= cutoff:
            raise ValueError(f"official prediction row {index} was not frozen pre-kickoff")
        if home_id == away_id:
            raise ValueError(f"official prediction row {index} repeats one team")
        if outcome not in OUTCOMES:
            raise ValueError(f"official prediction row {index} has an invalid outcome")
        if confidence_label not in CONFIDENCE_LEVELS:
            raise ValueError(
                f"official prediction row {index} has invalid confidence"
            )
        if any(value < 0 or value > 1 for value in one_x_two):
            raise ValueError(f"official prediction row {index} has invalid probability")
        if abs(sum(one_x_two) - 1.0) > 1e-9:
            raise ValueError(
                f"official prediction row {index} probabilities do not sum to 1"
            )
        if bool(row.get("decision_boundaries", {}).get("capital_deployment_ready")):
            raise ValueError("official shadow slate cannot authorize capital")
        research = row.get("research_lens") or {}
        if any(
            belief.get("applied_to_forecast")
            for side in ("home", "away")
            for belief in (research.get(side, {}).get("beliefs") or {}).values()
        ):
            raise ValueError("tentative research belief was applied to an official forecast")
        probability_leader = str(row["translation_audit"]["probability_leader"])
        override = outcome != probability_leader
        if override and not str(official_pick.get("override_reason") or "").strip():
            raise ValueError("official model override requires a recorded reason")
        if override:
            overrides += 1
        match_ids.append(match_id)
        fixtures.append((home_id, away_id))
        confidence[confidence_label] += 1
    if len(set(match_ids)) != len(match_ids):
        raise ValueError("official slate contains duplicate match ids")
    if len(set(fixtures)) != len(fixtures):
        raise ValueError("official slate contains duplicate fixtures")
    return {
        "fixtures": len(rows),
        "unique_match_ids": len(set(match_ids)),
        "confidence": dict(sorted(confidence.items())),
        "model_overrides": overrides,
    }


def score_results(
    predictions: Iterable[dict[str, Any]],
    results: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Score append-only outcomes against the exact official 1X2 decisions."""

    rows = list(predictions)
    result_rows = list(results)
    by_match = {int(row["fixture"]["match_id"]): row for row in rows}
    if len(by_match) != len(rows):
        raise ValueError("official predictions contain duplicate match ids")
    seen: set[int] = set()
    hits = 0
    for result in result_rows:
        match_id = int(result["match_id"])
        if match_id in seen:
            raise ValueError("official results contain a duplicate match id")
        seen.add(match_id)
        prediction = by_match.get(match_id)
        if prediction is None:
            raise ValueError("official result does not join to the frozen slate")
        home_goals = int(result["final_home_goals"])
        away_goals = int(result["final_away_goals"])
        actual = (
            "home_win"
            if home_goals > away_goals
            else "away_win" if away_goals > home_goals else "draw"
        )
        if str(result.get("outcome")) != actual:
            raise ValueError("official result outcome does not match final goals")
        if prediction["official_pick"]["outcome"] == actual:
            hits += 1
    settled = len(result_rows)
    return {
        "fixtures": len(rows),
        "settled": settled,
        "pending": len(rows) - settled,
        "hits": hits,
        "misses": settled - hits,
        "hit_rate": round(hits / settled, 6) if settled else None,
    }
