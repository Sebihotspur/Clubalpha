"""Opponent-archetype memory built from immutable Match Learning Cards."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


VERSION = "clubalpha_archetype_memory_v1"


def evidence_tier(observations: int) -> str:
    if observations < 3:
        return "descriptive"
    if observations < 5:
        return "tentative"
    if observations < 8:
        return "challenger_eligible"
    return "human_promotion_review"


def _score_pair(value: Any) -> tuple[int | None, int | None]:
    parts = [part.strip() for part in str(value or "").replace(":", "-").split("-")]
    if len(parts) < 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def extract_archetype_observations(
    cards: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return two team-perspective observations per learning card."""

    output: list[dict[str, Any]] = []
    for card in cards:
        context = card["pre_match_fingerprint"]["directional_context"]
        actual_xg = card["observed"]["actual_xg"]
        predicted_xg = card["pre_match_fingerprint"]["contextual_predicted_xg"]
        home_goals, away_goals = _score_pair(card["observed"].get("score"))
        signals = {row["venue"]: row for row in card["team_memory_signals"]}
        sides = {
            "home": {
                "attack": context["home_attack"],
                "opponent_attack": context["away_attack"],
                "goals_for": home_goals,
                "goals_against": away_goals,
            },
            "away": {
                "attack": context["away_attack"],
                "opponent_attack": context["home_attack"],
                "goals_for": away_goals,
                "goals_against": home_goals,
            },
        }
        for venue, side in sides.items():
            signal = signals[venue]
            attack = side["attack"]
            opponent_attack = side["opponent_attack"]
            goals_for = side["goals_for"]
            goals_against = side["goals_against"]
            result = None
            if goals_for is not None and goals_against is not None:
                result = (
                    "W"
                    if goals_for > goals_against
                    else "L"
                    if goals_for < goals_against
                    else "D"
                )
            preferred = attack.get("preferred_route") or {}
            output.append(
                {
                    "match_id": int(card["match_id"]),
                    "kickoff_utc": card["kickoff_utc"],
                    "team_id": int(signal["team_id"]),
                    "team": signal["team"],
                    "opponent": signal["opponent"],
                    "venue": venue,
                    "team_archetype": attack.get("attacker_archetype"),
                    "opponent_archetype": attack.get("defender_archetype"),
                    "preferred_route": preferred.get("key"),
                    "route_verdict": preferred.get("verdict"),
                    "route_signal_z": preferred.get("challenger_signal_z"),
                    "projected_xg_for": float(predicted_xg[venue]),
                    "actual_xg_for": float(actual_xg[venue]),
                    "actual_xg_against": float(
                        actual_xg["away" if venue == "home" else "home"]
                    ),
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "result": result,
                    "process_learning_weight": float(
                        signal.get("process_learning_weight") or 0.0
                    ),
                    "xi_hit_rate": float(signal.get("xi_hit_rate") or 0.0),
                    "opponent_preferred_route": (
                        (opponent_attack.get("preferred_route") or {}).get("key")
                    ),
                }
            )
    return output


def _aggregate(
    observations: list[dict[str, Any]],
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        grouped[tuple(row.get(key) for key in keys)].append(row)

    output = []
    for values, rows in grouped.items():
        count = len(rows)
        total_weight = sum(row["process_learning_weight"] for row in rows)

        def weighted(field: str) -> float | None:
            if total_weight <= 0:
                return None
            return sum(
                float(row[field]) * row["process_learning_weight"] for row in rows
            ) / total_weight

        xg_for = weighted("actual_xg_for")
        xg_against = weighted("actual_xg_against")
        projected_xg = weighted("projected_xg_for")
        route_counts: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.get("preferred_route"):
                route_counts[str(row["preferred_route"])] += 1
        result = {key: value for key, value in zip(keys, values)}
        result.update(
            {
                "observations": count,
                "effective_process_evidence": round(total_weight, 6),
                "evidence_tier": evidence_tier(count),
                "record": {
                    "wins": sum(row.get("result") == "W" for row in rows),
                    "draws": sum(row.get("result") == "D" for row in rows),
                    "losses": sum(row.get("result") == "L" for row in rows),
                },
                "weighted_process": {
                    "xg_for": round(xg_for, 4) if xg_for is not None else None,
                    "xg_against": (
                        round(xg_against, 4) if xg_against is not None else None
                    ),
                    "xg_difference": (
                        round(xg_for - xg_against, 4)
                        if xg_for is not None and xg_against is not None
                        else None
                    ),
                    "projected_xg_for": (
                        round(projected_xg, 4) if projected_xg is not None else None
                    ),
                    "attack_xg_residual": (
                        round(xg_for - projected_xg, 4)
                        if xg_for is not None and projected_xg is not None
                        else None
                    ),
                },
                "mean_xi_hit_rate": round(
                    sum(row["xi_hit_rate"] for row in rows) / count, 4
                ),
                "preferred_route_counts": dict(sorted(route_counts.items())),
                "match_ids": sorted(int(row["match_id"]) for row in rows),
            }
        )
        output.append(result)
    return sorted(
        output,
        key=lambda row: (
            -int(row["observations"]),
            *(str(row.get(key) or "") for key in keys),
        ),
    )


def build_archetype_memory(cards: Iterable[dict[str, Any]], *, as_of: str) -> dict[str, Any]:
    observations = extract_archetype_observations(cards)
    return {
        "version": VERSION,
        "status": "research_context_zero_probability_weight",
        "as_of": as_of,
        "observations": observations,
        "direct_opponent": _aggregate(observations, ("team", "opponent")),
        "team_vs_opponent_archetype": _aggregate(
            observations, ("team", "opponent_archetype")
        ),
        "archetype_vs_archetype": _aggregate(
            observations, ("team_archetype", "opponent_archetype")
        ),
        "decision_boundaries": {
            "fewer_than_3": "descriptive_only",
            "3_to_4": "tentative",
            "5_to_7": "challenger_eligible",
            "8_or_more": "human_promotion_review",
            "automatic_probability_weight": 0,
            "automatic_player_alpha_change": False,
            "automatic_club_form_change": False,
            "capital_deployment_ready": False,
        },
    }

