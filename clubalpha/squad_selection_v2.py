"""Fixture-specific squad selection challenger.

The v2 policy deliberately keeps manager selection and player quality apart.
Only prior match participation, declared lineups, tactical roles, formation,
competition context, and explicit availability may influence a projection.
Alpha Ability is joined downstream and is never an input to the functions in
this module.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

from clubalpha.squad_selection import (
    MAX_PLAYER_MINUTES,
    SELECTION_ROLE_ORDER,
    _availability_status,
    _capped_minutes,
    _lineup_selection_role,
    _number,
    _squad_selection_role,
)


SELECTION_V2_VERSION = "clubalpha_squad_selection_v2_challenger"


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _target_timestamp(value: date | datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.fromisoformat(f"{value.isoformat()}T23:59:59+00:00")
    parsed = _timestamp(value)
    if parsed is None:
        raise ValueError(f"Invalid target timestamp: {value!r}")
    return parsed


def _minutes(row: dict[str, Any]) -> float:
    value = ((row.get("metrics") or {}).get("minutes_played") or {}).get("value")
    return min(MAX_PLAYER_MINUTES, max(0.0, _number(value)))


def _recent_match_groups(
    rows: Iterable[dict[str, Any]],
    target: datetime,
    maximum_matches: int,
) -> list[tuple[int, list[dict[str, Any]]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        kickoff = _timestamp(row.get("kickoff_utc"))
        if kickoff is None or kickoff >= target:
            continue
        grouped[int(row["match_id"])].append(row)
    ordered = sorted(
        grouped.items(),
        key=lambda item: max(
            _timestamp(row.get("kickoff_utc")) or datetime.min.replace(tzinfo=timezone.utc)
            for row in item[1]
        ),
        reverse=True,
    )
    return ordered[:maximum_matches]


def _match_weight(
    rank: int,
    competition_id: Any,
    target_competition_id: Any,
    config: dict[str, Any],
    selection_source: Any = None,
) -> float:
    decay = float(config["recent_evidence"]["match_rank_decay"])
    same = float(config["recent_evidence"]["same_competition_weight"])
    cross = float(config["recent_evidence"]["cross_competition_weight"])
    competition_weight = (
        same
        if target_competition_id is not None
        and str(competition_id) == str(target_competition_id)
        else cross
    )
    source_weights = config["recent_evidence"].get("source_weights") or {}
    source_weight = float(source_weights.get(str(selection_source), 1.0))
    return (decay**rank) * competition_weight * source_weight


def _weighted_shape(
    matches: list[tuple[int, list[dict[str, Any]], float]],
    config: dict[str, Any],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for match_id, rows, weight in matches:
        starters = [row for row in rows if row.get("is_starter") is True]
        if len(starters) != 11:
            continue
        roles = [_lineup_selection_role(row.get("lineup_position_id")) for row in starters]
        if any(role is None for role in roles) or roles.count("GK") != 1:
            continue
        slots = {role: roles.count(role) for role in SELECTION_ROLE_ORDER}
        formation = next(
            (row.get("team_formation") for row in starters if row.get("team_formation")),
            None,
        )
        candidates.append(
            {
                "match_id": match_id,
                "formation": formation,
                "role_slots": slots,
                "weight": weight,
            }
        )
        if len(candidates) >= int(config["shape"]["maximum_matches"]):
            break

    if not candidates:
        return {
            "formation": None,
            "role_slots": dict(config["default_role_slots"]),
            "source_match_ids": [],
            "used_default_shape": True,
        }

    votes: dict[tuple[str | None, tuple[int, ...]], float] = defaultdict(float)
    for item in candidates:
        key = (
            item["formation"],
            tuple(item["role_slots"][role] for role in SELECTION_ROLE_ORDER),
        )
        votes[key] += float(item["weight"])
    winner = max(votes, key=lambda key: (votes[key], key[0] or ""))
    return {
        "formation": winner[0],
        "role_slots": dict(zip(SELECTION_ROLE_ORDER, winner[1])),
        "source_match_ids": [item["match_id"] for item in candidates],
        "used_default_shape": False,
    }


def _dominant_role(role_weights: dict[str, float], candidate: dict[str, Any]) -> str | None:
    if role_weights:
        return max(
            role_weights,
            key=lambda role: (role_weights[role], -SELECTION_ROLE_ORDER.index(role)),
        )
    role = candidate.get("selection_role")
    if role in SELECTION_ROLE_ORDER:
        return str(role)
    return _squad_selection_role(candidate)


def _select_xi(
    players: list[dict[str, Any]],
    slots: dict[str, int],
    hard_exclusions: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    def rank_key(player: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -float(player["selection_score"]),
            -float(player["expected_minutes"]),
            -float(player["start_probability"]),
            -float(player["appearance_probability"]),
            str(player.get("player") or ""),
        )

    eligible = [
        row
        for row in players
        if row["availability_status"] not in hard_exclusions
    ]
    selected: list[dict[str, Any]] = []
    flags: list[str] = []
    for role in SELECTION_ROLE_ORDER:
        wanted = int(slots.get(role, 0))
        candidates = sorted(
            (row for row in eligible if row["selection_role"] == role),
            key=rank_key,
        )
        selected.extend(candidates[:wanted])
        if len(candidates) < wanted:
            flags.append(f"insufficient_{role.lower()}_depth")

    selected_ids = {row["player_id"] for row in selected}
    if len(selected) < 11:
        fallback = sorted(
            (row for row in eligible if row["player_id"] not in selected_ids),
            key=rank_key,
        )
        selected.extend(fallback[: 11 - len(selected)])
        if fallback:
            flags.append("cross_role_xi_fill")
    selected = sorted(
        selected[:11],
        key=lambda row: (
            SELECTION_ROLE_ORDER.index(row["selection_role"]),
            rank_key(row),
        ),
    )
    return selected, flags


def project_team_selection(
    history_rows: Iterable[dict[str, Any]],
    candidates: Iterable[dict[str, Any]],
    target_kickoff: date | datetime | str,
    target_competition_id: Any,
    config: dict[str, Any],
    *,
    team_id: int | None = None,
    team: str | None = None,
) -> dict[str, Any]:
    """Project one club's XI and minutes using only information before kickoff."""

    target = _target_timestamp(target_kickoff)
    candidate_rows = [
        row
        for row in candidates
        if team_id is None
        or row.get("team_id") is None
        or int(row["team_id"]) == int(team_id)
    ]
    candidate_by_player = {int(row["player_id"]): row for row in candidate_rows}
    source_history = [
        row
        for row in history_rows
        if team_id is None
        or row.get("team_id") is None
        or int(row["team_id"]) == int(team_id)
    ]
    recent = _recent_match_groups(
        source_history,
        target,
        int(config["recent_evidence"]["maximum_matches"]),
    )
    weighted_matches: list[tuple[int, list[dict[str, Any]], float]] = []
    latest_exact_starters: set[int] = set()
    latest_exact_source: str | None = None
    total_match_weight = 0.0
    exact_lineup_weight = 0.0
    starts: dict[int, float] = defaultdict(float)
    appearances: dict[int, float] = defaultdict(float)
    starter_minutes: dict[int, float] = defaultdict(float)
    starter_minute_weight: dict[int, float] = defaultdict(float)
    substitute_minutes: dict[int, float] = defaultdict(float)
    substitute_minute_weight: dict[int, float] = defaultdict(float)
    role_weights: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for rank, (match_id, rows) in enumerate(recent):
        reference = rows[0]
        weight = _match_weight(
            rank,
            reference.get("competition_id"),
            target_competition_id,
            config,
            reference.get("selection_source"),
        )
        total_match_weight += weight
        starters = [row for row in rows if row.get("is_starter") is True]
        exact = len(starters) == 11
        if exact:
            exact_lineup_weight += weight
            if not latest_exact_starters:
                latest_exact_starters = {int(row["player_id"]) for row in starters}
                latest_exact_source = str(reference.get("selection_source") or "default")
        for row in rows:
            player_id = int(row["player_id"])
            if player_id not in candidate_by_player:
                continue
            played = _minutes(row)
            if played > 0:
                appearances[player_id] += weight
            if exact and row.get("is_starter") is True:
                starts[player_id] += weight
                starter_minutes[player_id] += weight * played
                starter_minute_weight[player_id] += weight
            elif played > 0:
                substitute_minutes[player_id] += weight * played
                substitute_minute_weight[player_id] += weight
            role = _lineup_selection_role(row.get("lineup_position_id"))
            if role:
                role_weights[player_id][role] += weight * (
                    1.0 if row.get("is_starter") is True else 0.25
                )
        weighted_matches.append((match_id, rows, weight))

    raw_minutes: dict[int, float] = {}
    player_rows: list[dict[str, Any]] = []
    default_starter = float(config["minutes"]["default_starter_minutes"])
    default_substitute = float(config["minutes"]["default_substitute_minutes"])
    hard_exclusions = set(config["availability"]["hard_exclusion_statuses"])

    for player_id, candidate in candidate_by_player.items():
        start_probability = (
            starts[player_id] / exact_lineup_weight if exact_lineup_weight > 0 else 0.0
        )
        appearance_probability = (
            appearances[player_id] / total_match_weight if total_match_weight > 0 else 0.0
        )
        start_probability = min(1.0, max(0.0, start_probability))
        appearance_probability = min(
            1.0, max(start_probability, appearance_probability)
        )
        mean_starter_minutes = (
            starter_minutes[player_id] / starter_minute_weight[player_id]
            if starter_minute_weight[player_id] > 0
            else default_starter
        )
        mean_substitute_minutes = (
            substitute_minutes[player_id] / substitute_minute_weight[player_id]
            if substitute_minute_weight[player_id] > 0
            else default_substitute
        )
        expected_raw = (
            start_probability * mean_starter_minutes
            + (appearance_probability - start_probability) * mean_substitute_minutes
        )
        availability_status = _availability_status(candidate.get("injury"), config)
        if availability_status in hard_exclusions:
            expected_raw = 0.0
            start_probability = 0.0
            appearance_probability = 0.0
        raw_minutes[player_id] = expected_raw
        role = _dominant_role(role_weights.get(player_id) or {}, candidate)
        if role is None:
            continue
        player_rows.append(
            {
                "player_id": player_id,
                "player": candidate.get("player"),
                "selection_role": role,
                "availability_status": availability_status,
                "start_probability": round(start_probability, 6),
                "appearance_probability": round(appearance_probability, 6),
                "conditional_starter_minutes": round(mean_starter_minutes, 3),
                "conditional_substitute_minutes": round(mean_substitute_minutes, 3),
                "expected_minutes_raw": round(expected_raw, 3),
                "expected_minutes": None,
                "latest_declared_starter": player_id in latest_exact_starters,
                "selection_score": None,
                "evidence": {
                    "weighted_starts": round(starts[player_id], 6),
                    "weighted_appearances": round(appearances[player_id], 6),
                },
            }
        )

    expected_total = float(config["expected_team_minutes"])
    eligible_raw = {
        row["player_id"]: raw_minutes[row["player_id"]]
        for row in player_rows
        if row["availability_status"] not in hard_exclusions
    }
    allocated = _capped_minutes(eligible_raw, expected_total) if recent else {
        row["player_id"]: 0.0 for row in player_rows
    }
    for row in player_rows:
        row["expected_minutes"] = allocated.get(row["player_id"], 0.0)
        default_start_bonus = float(
            config["selection"]["latest_declared_start_bonus_minutes"]
        )
        source_bonuses = config["selection"].get(
            "latest_declared_start_bonus_by_source"
        ) or {}
        start_bonus = float(
            source_bonuses.get(str(latest_exact_source), default_start_bonus)
        )
        row["selection_score"] = round(
            float(row["expected_minutes"])
            + (
                start_bonus
                if row["latest_declared_starter"]
                else 0.0
            ),
            3,
        )

    shape = _weighted_shape(weighted_matches, config)
    xi, xi_flags = _select_xi(player_rows, shape["role_slots"], hard_exclusions) if recent else ([], [])
    xi_ids = {row["player_id"] for row in xi}
    for row in player_rows:
        row["predicted_starter"] = row["player_id"] in xi_ids
    player_rows.sort(
        key=lambda row: (-float(row["expected_minutes"]), str(row.get("player") or ""))
    )

    quality_flags = list(xi_flags)
    if not recent:
        quality_flags.append("no_prior_match_evidence")
    if recent and exact_lineup_weight <= 0:
        quality_flags.append("no_exact_prior_lineup")
    if shape["used_default_shape"]:
        quality_flags.append("default_role_shape")
    if len(xi) != 11 and recent:
        quality_flags.append("incomplete_predicted_xi")
    if candidate_rows and len(player_rows) != len(candidate_rows):
        quality_flags.append("unmapped_selection_roles")

    assigned = sum(float(row["expected_minutes"]) for row in player_rows)
    return {
        "selection_version": config.get("version") or SELECTION_V2_VERSION,
        "target_kickoff": target.isoformat(),
        "target_competition_id": target_competition_id,
        "team_id": team_id,
        "team": team,
        "shape_projection": shape,
        "predicted_starting_xi": [
            {
                key: row[key]
                for key in (
                    "player_id",
                    "player",
                    "selection_role",
                    "start_probability",
                    "appearance_probability",
                    "expected_minutes",
                    "latest_declared_starter",
                    "selection_score",
                )
            }
            for row in xi
        ],
        "players": player_rows,
        "evidence": {
            "prior_matches": len(recent),
            "prior_match_ids": [match_id for match_id, _ in recent],
            "weighted_matches": round(total_match_weight, 6),
            "weighted_exact_lineups": round(exact_lineup_weight, 6),
            "latest_exact_lineup_source": latest_exact_source,
            "candidate_players": len(candidate_rows),
        },
        "decision_boundaries": {
            "alpha_used_to_select_players": False,
            "fixture_specific": True,
            "confirmed_lineup": False,
            "selection_probabilities_calibrated": False,
            "projection_ready": len(xi) == 11 and abs(assigned - expected_total) <= 0.01,
            "expected_team_minutes": expected_total,
            "assigned_team_minutes": round(assigned, 3),
            "maximum_player_minutes": MAX_PLAYER_MINUTES,
        },
        "quality_flags": sorted(set(quality_flags)),
    }


def minutes_only_baseline(
    history_rows: Iterable[dict[str, Any]],
    candidates: Iterable[dict[str, Any]],
    target_kickoff: date | datetime | str,
    target_competition_id: Any,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Comparable v1-style champion: recent weighted minutes plus latest shape.

    This is intentionally a small historical emulation of the current v1
    selection rule, not a claim that every live v1 input existed at every old
    kickoff. It shares v2's candidate pool and evidence window so only the
    selection policy differs.
    """

    target = _target_timestamp(target_kickoff)
    candidate_rows = list(candidates)
    candidate_by_player = {int(row["player_id"]): row for row in candidate_rows}
    recent = _recent_match_groups(
        history_rows,
        target,
        int(config["recent_evidence"]["maximum_matches"]),
    )
    weighted_minutes: dict[int, float] = defaultdict(float)
    weighted_starts: dict[int, float] = defaultdict(float)
    role_weights: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    weighted_matches: list[tuple[int, list[dict[str, Any]], float]] = []
    exact_weight = 0.0
    for rank, (match_id, rows) in enumerate(recent):
        weight = _match_weight(
            rank,
            rows[0].get("competition_id"),
            target_competition_id,
            config,
            rows[0].get("selection_source"),
        )
        exact = len([row for row in rows if row.get("is_starter") is True]) == 11
        if exact:
            exact_weight += weight
        for row in rows:
            player_id = int(row["player_id"])
            if player_id not in candidate_by_player:
                continue
            weighted_minutes[player_id] += weight * _minutes(row)
            if exact and row.get("is_starter") is True:
                weighted_starts[player_id] += weight
            role = _lineup_selection_role(row.get("lineup_position_id"))
            if role:
                role_weights[player_id][role] += weight
        weighted_matches.append((match_id, rows, weight))

    players = []
    for player_id, candidate in candidate_by_player.items():
        role = _dominant_role(role_weights.get(player_id) or {}, candidate)
        if role is None:
            continue
        players.append(
            {
                "player_id": player_id,
                "player": candidate.get("player"),
                "selection_role": role,
                "availability_status": "available",
                "start_probability": round(
                    weighted_starts[player_id] / exact_weight, 6
                )
                if exact_weight > 0
                else 0.0,
                "appearance_probability": 0.0,
                "expected_minutes": None,
            }
        )
    # Normalize only across players whose tactical role can be resolved. The
    # live v1 builder does the same after role mapping; allocating minutes to a
    # subsequently dropped player would give the historical baseline an
    # artificial advantage by predicting fewer than 990 team minutes.
    allocated = (
        _capped_minutes(
            {row["player_id"]: weighted_minutes[row["player_id"]] for row in players},
            float(config["expected_team_minutes"]),
        )
        if recent
        else {}
    )
    for row in players:
        row["expected_minutes"] = allocated.get(row["player_id"], 0.0)
    shape = _weighted_shape(weighted_matches[:1], config)

    def rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (-float(row["expected_minutes"]), -float(row["start_probability"]), str(row.get("player") or ""))

    selected = []
    for role in SELECTION_ROLE_ORDER:
        selected.extend(
            sorted((row for row in players if row["selection_role"] == role), key=rank_key)[
                : int(shape["role_slots"].get(role, 0))
            ]
        )
    selected_ids = {row["player_id"] for row in selected}
    selected.extend(
        sorted((row for row in players if row["player_id"] not in selected_ids), key=rank_key)[
            : 11 - len(selected)
        ]
    )
    return {
        "predicted_starting_xi": selected[:11],
        "players": players,
        "shape_projection": shape,
    }
