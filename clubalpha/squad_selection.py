"""Dated squad hierarchy, expected-minute prior, and baseline XI evidence."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Iterable

from clubalpha.player_quality_v2 import scoring_position


SELECTION_PRIOR_VERSION = "clubalpha_squad_selection_prior_v1"
ROLE_ORDER = ("GK", "CB", "FB", "CM", "FW")


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _availability_status(injury: Any, config: dict[str, Any]) -> str:
    if not injury:
        return "available"
    expected = str((injury or {}).get("expectedReturn") or "").strip().lower()
    if not expected:
        return "unknown"
    if any(term in expected for term in config["availability"]["questionable_terms"]):
        return "questionable"
    return "unavailable"


def _normalized_minutes(values: dict[int, float], total: float) -> dict[int, float]:
    positive = {key: max(0.0, float(value)) for key, value in values.items()}
    denominator = sum(positive.values())
    if denominator <= 0:
        return {key: 0.0 for key in positive}
    result = {key: round(total * value / denominator, 3) for key, value in positive.items()}
    if result:
        largest = max(positive, key=positive.get)
        result[largest] = round(result[largest] + total - sum(result.values()), 3)
    return result


def _recent_rows(
    current_rows: Iterable[dict[str, Any]],
    preseason_rows: Iterable[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source, source_weight, rows in (
        (
            "current_competitive",
            float(config["recent_evidence"]["current_competitive_weight"]),
            current_rows,
        ),
        (
            "preseason",
            float(config["recent_evidence"]["preseason_weight"]),
            preseason_rows,
        ),
    ):
        for row in rows:
            kickoff = _day(row.get("kickoff_utc"))
            if kickoff is None or kickoff > as_of:
                continue
            candidates.append({**row, "selection_source": source, "source_weight": source_weight})

    # The same match can appear in more than one normalized layer. Current
    # competitive evidence wins, followed by the richer row.
    best: dict[tuple[int, int], dict[str, Any]] = {}
    for row in candidates:
        key = (int(row["match_id"]), int(row["player_id"]))
        current = best.get(key)
        priority = (
            row["selection_source"] == "current_competitive",
            len(row.get("metrics") or {}),
        )
        current_priority = (
            current is not None and current["selection_source"] == "current_competitive",
            len((current or {}).get("metrics") or {}),
        )
        if current is None or priority > current_priority:
            best[key] = row
    return list(best.values())


def _match_weight(row: dict[str, Any], as_of: date, config: dict[str, Any]) -> float:
    kickoff = _day(row.get("kickoff_utc")) or as_of
    age_days = max(0, (as_of - kickoff).days)
    half_life = float(config["recent_evidence"]["half_life_days"])
    return float(row["source_weight"]) * (0.5 ** (age_days / half_life))


def _latest_shape(
    match_groups: dict[int, list[dict[str, Any]]],
    squad_by_player: dict[int, dict[str, Any]],
    default_slots: dict[str, int],
) -> tuple[str | None, dict[str, int], int | None, bool]:
    ordered = sorted(
        match_groups.items(),
        key=lambda item: max(str(row.get("kickoff_utc") or "") for row in item[1]),
        reverse=True,
    )
    for match_id, rows in ordered:
        starters = [row for row in rows if row.get("is_starter") is True]
        if len(starters) != 11:
            continue
        roles: list[str] = []
        for row in starters:
            squad = squad_by_player.get(int(row["player_id"]))
            if not squad:
                break
            role = scoring_position(squad.get("position"), squad.get("squad_group"))
            if not role:
                break
            roles.append(role)
        if len(roles) == 11 and roles.count("GK") == 1:
            slots = {role: roles.count(role) for role in ROLE_ORDER}
            formation = next((row.get("team_formation") for row in starters if row.get("team_formation")), None)
            return formation, slots, match_id, False
    return None, dict(default_slots), None, True


def _availability_adjusted(
    players: list[dict[str, Any]],
    baseline: dict[int, float],
    total: float,
    hard_exclusions: set[str],
) -> tuple[dict[int, float], list[str]]:
    adjusted = {player["player_id"]: 0.0 for player in players}
    flags: list[str] = []
    for role in ROLE_ORDER:
        members = [player for player in players if player["scoring_position"] == role]
        target = sum(baseline[player["player_id"]] for player in members)
        eligible = [player for player in members if player["availability_status"] not in hard_exclusions]
        weights = {player["player_id"]: baseline[player["player_id"]] for player in eligible}
        if eligible and sum(weights.values()) <= 0:
            weights = {player["player_id"]: 1.0 for player in eligible}
        allocation = _normalized_minutes(weights, target)
        adjusted.update(allocation)
        if target > 0 and not eligible:
            flags.append(f"no_available_{role.lower()}")

    eligible_all = [
        player for player in players if player["availability_status"] not in hard_exclusions
    ]
    if eligible_all and sum(adjusted.values()) < total - 0.001:
        adjusted = _normalized_minutes(
            {player["player_id"]: adjusted[player["player_id"]] or 1.0 for player in eligible_all},
            total,
        ) | {
            player["player_id"]: 0.0
            for player in players
            if player["availability_status"] in hard_exclusions
        }
    return adjusted, flags


def _select_xi(
    players: list[dict[str, Any]],
    slots: dict[str, int],
    hard_exclusions: set[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    def rank_key(player: dict[str, Any]) -> tuple[Any, ...]:
        return (
            -float(player["expected_minutes_prior"]),
            -float(player["evidence"]["weighted_start_rate"] or 0.0),
            -float(player["evidence"]["previous_season_minutes"]),
            str(player.get("player") or ""),
        )

    eligible = [
        player for player in players if player["availability_status"] not in hard_exclusions
    ]
    selected: list[dict[str, Any]] = []
    flags: list[str] = []
    for role in ROLE_ORDER:
        candidates = sorted(
            (player for player in eligible if player["scoring_position"] == role),
            key=rank_key,
        )
        wanted = int(slots.get(role, 0))
        chosen = candidates[:wanted]
        selected.extend(chosen)
        if len(chosen) < wanted:
            flags.append(f"insufficient_{role.lower()}_depth")

    selected_ids = {player["player_id"] for player in selected}
    if len(selected) < 11:
        fallback = sorted(
            (player for player in eligible if player["player_id"] not in selected_ids),
            key=rank_key,
        )
        selected.extend(fallback[: 11 - len(selected)])
        if fallback:
            flags.append("cross_role_xi_fill")
    selected = sorted(selected[:11], key=lambda player: (ROLE_ORDER.index(player["scoring_position"]), rank_key(player)))
    return [
        {
            "player_id": player["player_id"],
            "player": player["player"],
            "scoring_position": player["scoring_position"],
            "current_position": player["current_position"],
            "availability_status": player["availability_status"],
            "expected_minutes_prior": player["expected_minutes_prior"],
            "weighted_start_rate": player["evidence"]["weighted_start_rate"],
            "alpha_ability_z": player["alpha_ability_z"],
        }
        for player in selected
    ], flags


def build_squad_selection_priors(
    teams: Iterable[dict[str, Any]],
    squads: Iterable[dict[str, Any]],
    grades: Iterable[dict[str, Any]],
    current_rows: Iterable[dict[str, Any]],
    preseason_rows: Iterable[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one conservative, non-fixture-specific selection prior per club."""

    team_rows = list(teams)
    squad_rows = list(squads)
    grades_by_player = {int(row["player_id"]): row for row in grades}
    squads_by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in squad_rows:
        squads_by_team[int(row["team_id"])].append(row)

    recent = _recent_rows(current_rows, preseason_rows, as_of, config)
    recent_by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in recent:
        recent_by_team[int(row["team_id"])].append(row)

    expected_total = float(config["expected_team_minutes"])
    hard_exclusions = set(config["availability"]["hard_exclusion_statuses"])
    prior_matches = float(config["recent_evidence"]["historical_prior_equivalent_matches"])
    output: list[dict[str, Any]] = []

    for team in team_rows:
        team_id = int(team["team_id"])
        members = squads_by_team.get(team_id, [])
        squad_by_player = {int(row["player_id"]): row for row in members}
        match_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in recent_by_team.get(team_id, []):
            match_groups[int(row["match_id"])].append(row)

        weighted_match_count = 0.0
        weighted_lineup_match_count = 0.0
        weighted_minutes: dict[int, float] = defaultdict(float)
        weighted_starts: dict[int, float] = defaultdict(float)
        appearances: dict[int, set[int]] = defaultdict(set)
        exact_lineup_matches = 0
        source_matches: dict[str, set[int]] = defaultdict(set)
        latest_match_utc = None

        for match_id, rows in match_groups.items():
            reference = rows[0]
            weight = _match_weight(reference, as_of, config)
            weighted_match_count += weight
            source = str(reference["selection_source"])
            source_matches[source].add(match_id)
            kickoff = str(reference.get("kickoff_utc") or "")
            latest_match_utc = max(latest_match_utc or kickoff, kickoff)
            starters = [row for row in rows if row.get("is_starter") is True]
            exact = len(starters) == 11
            if exact:
                exact_lineup_matches += 1
                weighted_lineup_match_count += weight
            for row in rows:
                player_id = int(row["player_id"])
                if player_id not in squad_by_player:
                    continue
                minutes = min(90.0, max(0.0, _number(((row.get("metrics") or {}).get("minutes_played") or {}).get("value"))))
                weighted_minutes[player_id] += weight * minutes
                if minutes > 0:
                    appearances[player_id].add(match_id)
                if exact and row.get("is_starter") is True:
                    weighted_starts[player_id] += weight

        recent_distribution = _normalized_minutes(dict(weighted_minutes), expected_total)
        historical_minutes = {
            player_id: _number((grades_by_player.get(player_id) or {}).get("minutes"))
            for player_id in squad_by_player
        }
        historical_distribution = _normalized_minutes(historical_minutes, expected_total)
        recent_strength = weighted_match_count if sum(weighted_minutes.values()) > 0 else 0.0
        historical_strength = prior_matches if sum(historical_minutes.values()) > 0 else 0.0

        has_selection_evidence = bool(recent_strength or historical_strength)
        if has_selection_evidence:
            blended = {
                player_id: (
                    recent_distribution.get(player_id, 0.0) * recent_strength
                    + historical_distribution.get(player_id, 0.0) * historical_strength
                )
                / (recent_strength + historical_strength)
                for player_id in squad_by_player
            }
        else:
            blended = {player_id: 0.0 for player_id in squad_by_player}
        baseline = _normalized_minutes(blended, expected_total)

        player_rows: list[dict[str, Any]] = []
        missing_roles = 0
        for player_id, squad in squad_by_player.items():
            role = scoring_position(squad.get("position"), squad.get("squad_group"))
            if role is None:
                missing_roles += 1
                continue
            grade = grades_by_player.get(player_id) or {}
            player_rows.append(
                {
                    "player_id": player_id,
                    "player": squad.get("player"),
                    "current_position": squad.get("position"),
                    "squad_group": squad.get("squad_group"),
                    "scoring_position": role,
                    "availability_status": _availability_status(squad.get("injury"), config),
                    "expected_return": (squad.get("injury") or {}).get("expectedReturn"),
                    "alpha_ability_z": grade.get("alpha_ability_z"),
                    "baseline_expected_minutes": baseline.get(player_id, 0.0),
                    "expected_minutes_prior": None,
                    "evidence": {
                        "recent_weighted_minutes": round(weighted_minutes.get(player_id, 0.0), 3),
                        "recent_appearances": len(appearances.get(player_id, set())),
                        "weighted_start_rate": round(
                            weighted_starts.get(player_id, 0.0) / weighted_lineup_match_count, 4
                        )
                        if weighted_lineup_match_count > 0
                        else None,
                        "previous_season_minutes": round(historical_minutes.get(player_id, 0.0), 3),
                    },
                }
            )

        if has_selection_evidence:
            adjusted, availability_flags = _availability_adjusted(
                player_rows,
                {row["player_id"]: row["baseline_expected_minutes"] for row in player_rows},
                expected_total,
                hard_exclusions,
            )
        else:
            adjusted = {row["player_id"]: 0.0 for row in player_rows}
            availability_flags = ["no_selection_evidence"]
        for row in player_rows:
            row["expected_minutes_prior"] = adjusted.get(row["player_id"], 0.0)
        player_rows.sort(
            key=lambda row: (
                -float(row["expected_minutes_prior"]),
                str(row.get("player") or ""),
            )
        )

        formation, slots, shape_match_id, used_default_shape = _latest_shape(
            match_groups,
            squad_by_player,
            config["default_role_slots"],
        )
        if has_selection_evidence:
            xi, xi_flags = _select_xi(player_rows, slots, hard_exclusions)
        else:
            xi, xi_flags = [], []
        minute_coverage = (
            sum(weighted_minutes.values()) / (expected_total * weighted_match_count)
            if weighted_match_count > 0
            else 0.0
        )
        grade_coverage = (
            sum(row["alpha_ability_z"] is not None for row in player_rows) / len(player_rows)
            if player_rows
            else 0.0
        )
        quality_flags = [*availability_flags, *xi_flags]
        if not match_groups:
            quality_flags.append("no_recent_match_detail")
        if exact_lineup_matches == 0:
            quality_flags.append("no_exact_recent_lineup")
        if source_matches.get("preseason") and not source_matches.get("current_competitive"):
            quality_flags.append("preseason_only_recent_evidence")
        if used_default_shape:
            quality_flags.append("default_role_shape")
        if grade_coverage < 1.0:
            quality_flags.append("partial_alpha_context")
        if missing_roles:
            quality_flags.append("unmapped_squad_roles")
        if any(row["availability_status"] == "unknown" for row in player_rows):
            quality_flags.append("unknown_availability")

        output.append(
            {
                "selection_prior_version": config.get("version") or SELECTION_PRIOR_VERSION,
                "as_of": as_of.isoformat(),
                "team_id": team_id,
                "team": team.get("name"),
                "premier_league_2026_27": bool(team.get("premier_league_2026_27")),
                "ucl_status": team.get("ucl_status"),
                "shape_prior": {
                    "formation": formation,
                    "role_slots": slots,
                    "source_match_id": shape_match_id,
                    "used_default_shape": used_default_shape,
                },
                "expected_starting_xi_prior": xi,
                "players": player_rows,
                "evidence": {
                    "recent_matches": len(match_groups),
                    "current_competitive_matches": len(source_matches.get("current_competitive", set())),
                    "preseason_matches": len(source_matches.get("preseason", set())),
                    "exact_lineup_matches": exact_lineup_matches,
                    "weighted_recent_matches": round(weighted_match_count, 4),
                    "current_squad_minute_coverage": round(min(1.0, minute_coverage), 4),
                    "alpha_context_coverage": round(grade_coverage, 4),
                    "latest_match_utc": latest_match_utc,
                },
                "decision_boundaries": {
                    "lineup_prior_ready": len(xi) == 11,
                    "expected_team_minutes": expected_total,
                    "availability_adjustment_applied": any(
                        row["availability_status"] in hard_exclusions
                        and row["baseline_expected_minutes"] > 0
                        for row in player_rows
                    ),
                    "questionable_players_assumed_available": True,
                    "alpha_used_to_select_players": False,
                    "fixture_specific": False,
                    "confirmed_lineup": False,
                    "projection_ready": False,
                },
                "quality_flags": sorted(set(quality_flags)),
            }
        )

    output.sort(key=lambda row: (row.get("team") or "", row["team_id"]))
    return output
