"""Canonical player features and WCALPHA-compatible Alpha Ability grades.

This module is deliberately pure: it reads normalized rows supplied by the
caller, performs calculations, and returns serializable dictionaries. It does
not make network calls or mix short-term form into player quality.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Iterable


MATCH_SOURCE = "FotMob 2025/26 player-match detail"
SEASON_SOURCE = "FotMob 2025/26 season leaderboard"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def primary_position(position: Any) -> str | None:
    parts = [part.strip().upper() for part in str(position or "").split(",") if part.strip()]
    return parts[0] if parts else None


def scoring_position(position: Any, squad_group: Any) -> str | None:
    """Map FotMob's current squad role to a WCALPHA peer population.

    The current squad group is preferred over a player's long list of secondary
    positions. CAM is treated as the WCALPHA attacking-midfielder/forward case.
    Midfielders and goalkeepers are intentionally left for their own formulas.
    """

    primary = primary_position(position)
    group = str(squad_group or "").lower()
    if group == "attackers" or primary == "CAM":
        return "FW"
    if group == "defenders":
        return "FB" if primary in {"LB", "RB", "LWB", "RWB"} else "CB"
    return None


def minutes_reliability_weight(minutes: float, config: dict[str, Any]) -> float:
    bands = sorted(
        config["minutes_reliability_bands"],
        key=lambda row: float(row["minimum_minutes"]),
        reverse=True,
    )
    for band in bands:
        if minutes >= float(band["minimum_minutes"]):
            return float(band["weight"])
    return float(bands[-1]["weight"])


def coverage_reliability_weight(
    coverage_pct: float,
    composite_z: float,
    config: dict[str, Any],
) -> float:
    """Reproduce WCALPHA's positive-only thin-coverage damping."""

    policy = config["coverage"]
    full_at = float(policy["positive_score_full_reliability_pct"])
    if composite_z <= 0 or coverage_pct >= full_at:
        return 1.0
    return max(float(policy["positive_score_minimum_weight"]), coverage_pct / full_at)


def _metric_item(metrics: dict[str, Any], aliases: Iterable[str]) -> dict[str, Any] | None:
    for alias in aliases:
        item = metrics.get(alias)
        if item and _number(item.get("value")) is not None:
            return item
    return None


def _sum_event(rows: list[dict[str, Any]], *aliases: str) -> float:
    total = 0.0
    for row in rows:
        item = _metric_item(row.get("metrics") or {}, aliases)
        if item:
            total += _number(item.get("value")) or 0.0
    return total


def _sum_preferred_event(
    rows: list[dict[str, Any]],
    preferred: str,
    fallback: str,
    preferred_available_competitions: set[tuple[Any, Any]],
    fallback_available_competitions: set[tuple[Any, Any]],
) -> tuple[float, float]:
    total = 0.0
    minutes = 0.0
    for row in rows:
        metrics = row.get("metrics") or {}
        competition_key = (row.get("competition_id"), row.get("competition"))
        if competition_key in preferred_available_competitions:
            aliases = (preferred,)
        elif competition_key in fallback_available_competitions:
            aliases = (fallback,)
        else:
            continue
        item = _metric_item(metrics, aliases)
        if item:
            total += _number(item.get("value")) or 0.0
        minutes += _number((metrics.get("minutes_played") or {}).get("value")) or 0.0
    return total, minutes


def _ratio(rows: list[dict[str, Any]], key: str) -> tuple[float | None, float, float]:
    won = 0.0
    attempted = 0.0
    for row in rows:
        item = (row.get("metrics") or {}).get(key) or {}
        value = _number(item.get("value"))
        total = _number(item.get("total"))
        if value is not None and total is not None:
            won += value
            attempted += total
    pct = 100.0 * won / attempted if attempted > 0 else None
    return pct, won, attempted


def _feature(
    value: float | None,
    *,
    unit: str,
    source: str,
    source_fields: list[str],
    numerator: float | None = None,
    denominator_minutes: float | None = None,
    note: str | None = None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    output: dict[str, Any] = {
        "value": round(float(value), 6),
        "unit": unit,
        "confidence": "calculated",
        "source": source,
        "source_fields": source_fields,
    }
    if numerator is not None:
        output["numerator"] = round(float(numerator), 6)
    if denominator_minutes is not None:
        output["denominator_minutes"] = round(float(denominator_minutes), 3)
    if note:
        output["note"] = note
    return output


def _per90_feature(
    numerator: float,
    minutes: float,
    *,
    source_fields: list[str],
    note: str | None = None,
) -> dict[str, Any] | None:
    if minutes <= 0:
        return None
    return _feature(
        numerator * 90.0 / minutes,
        unit="per90",
        source=MATCH_SOURCE,
        source_fields=source_fields,
        numerator=numerator,
        denominator_minutes=minutes,
        note=note,
    )


def _leaderboard_rate(
    rows: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any] | None:
    selected = [row for row in rows if row.get("metric") == metric]
    weighted_events = 0.0
    minutes = 0.0
    competitions: set[str] = set()
    for row in selected:
        value = _number(row.get("value"))
        row_minutes = _number(row.get("minutes"))
        if value is None or row_minutes is None or row_minutes <= 0:
            continue
        weighted_events += value * row_minutes / 90.0
        minutes += row_minutes
        competitions.add(str(row.get("competition") or "Unknown"))
    if minutes <= 0:
        return None
    return _feature(
        weighted_events * 90.0 / minutes,
        unit="per90",
        source=SEASON_SOURCE,
        source_fields=[metric],
        numerator=weighted_events,
        denominator_minutes=minutes,
        note=f"Minutes-weighted across {', '.join(sorted(competitions))}",
    )


def _league_quality(team: dict[str, Any], config: dict[str, Any]) -> tuple[str, float, bool]:
    policy = config["league_quality"]
    league_id = str(team.get("primary_league_id"))
    key = policy["fotmob_league_id_to_key"].get(league_id, policy["default_key"])
    multiplier = float(policy["tiers"].get(key, policy["default"]))
    return key, multiplier, league_id in policy["fotmob_league_id_to_key"]


def _competition_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        bucket["minutes"] += _number(((row.get("metrics") or {}).get("minutes_played") or {}).get("value")) or 0.0
    return [
        {
            "competition_id": bucket["competition_id"],
            "competition": bucket["competition"],
            "matches": len(bucket["match_ids"]),
            "minutes": round(bucket["minutes"], 3),
        }
        for bucket in sorted(buckets.values(), key=lambda item: str(item["competition"]))
    ]


def _attacker_features(
    rows: list[dict[str, Any]],
    season_rows: list[dict[str, Any]],
    minutes: float,
    metric_competitions: dict[str, set[tuple[Any, Any]]],
) -> tuple[dict[str, Any], list[str]]:
    flags: list[str] = []
    goals = _sum_event(rows, "goals")
    goal_leaderboard = [row for row in season_rows if row.get("metric") == "goals"]
    penalties = sum(_number(row.get("sub_value")) or 0.0 for row in goal_leaderboard)
    listed_goals = sum(_number(row.get("value")) or 0.0 for row in goal_leaderboard)
    goal_totals_mismatch = bool(
        minutes > 0 and goal_leaderboard and abs(listed_goals - goals) > 0.01
    )
    if goal_totals_mismatch:
        flags.append("match_goals_do_not_reconcile_to_season_leaderboard")

    shotmap_npg_rows = [
        row
        for row in rows
        if _number(
            (((row.get("metrics") or {}).get("non_penalty_goals") or {}).get("value"))
        )
        is not None
    ]
    shotmap_npg = _sum_event(shotmap_npg_rows, "non_penalty_goals")
    shotmap_npg_minutes = sum(
        _number((((row.get("metrics") or {}).get("minutes_played") or {}).get("value"))) or 0.0
        for row in shotmap_npg_rows
    )
    unclassified_npg_rows = [
        row
        for row in rows
        if _number(
            (((row.get("metrics") or {}).get("non_penalty_goals") or {}).get("value"))
        )
        is None
    ]
    unclassified_goals = _sum_event(unclassified_npg_rows, "goals")
    if shotmap_npg_minutes > 0 and unclassified_goals <= 0:
        npg = shotmap_npg
        npg_minutes = minutes
        npg_source_fields = [
            "shotmap.eventType/situation",
            "matchFacts.events goalDescriptionKey fallback",
        ]
        npg_note = (
            "Derived from reconciled match shot maps, with match goal events as a "
            "fallback; penalties, own goals, and shoot-out goals are excluded. A "
            "match without a reconciled event source is included only when the "
            "player's official goal count is zero."
        )
    elif shotmap_npg_minutes > 0 and unclassified_goals > 0:
        npg = None
        npg_minutes = 0.0
        npg_source_fields = []
        npg_note = None
        flags.append("non_penalty_goals_unreconciled_match_shotmap")
    elif goals > 0 and not goal_leaderboard:
        npg = None
        npg_minutes = 0.0
        npg_source_fields = []
        npg_note = None
        flags.append("non_penalty_goals_missing_penalty_split")
    elif goal_totals_mismatch:
        npg = None
        npg_minutes = 0.0
        npg_source_fields = []
        npg_note = None
    else:
        npg = max(0.0, goals - penalties)
        npg_minutes = minutes
        npg_source_fields = ["goals", "season goals.sub_value (penalties)"]
        npg_note = (
            "Fallback used only when match shot maps are unavailable and the "
            "match goal total reconciles to FotMob's season leaderboard."
        )

    non_penalty_xg, xg_minutes = _sum_preferred_event(
        rows,
        "expected_goals_non_penalty",
        "expected_goals",
        metric_competitions.get("expected_goals_non_penalty", set()),
        metric_competitions.get("expected_goals", set()),
    )
    assists = _sum_event(rows, "assists")
    xa_competitions = metric_competitions.get("expected_assists", set())
    xa_rows = [
        row
        for row in rows
        if (row.get("competition_id"), row.get("competition")) in xa_competitions
    ]
    expected_assists = _sum_event(xa_rows, "expected_assists")
    xa_minutes = sum(
        _number((((row.get("metrics") or {}).get("minutes_played")) or {}).get("value")) or 0.0
        for row in xa_rows
    )
    assists_per90 = assists * 90.0 / minutes if minutes > 0 else None
    xa_per90 = expected_assists * 90.0 / xa_minutes if xa_minutes > 0 else None
    axa_value = (
        (assists_per90 or 0.0) + (xa_per90 or 0.0)
        if assists_per90 is not None or xa_per90 is not None
        else None
    )
    box_touches = _sum_event(rows, "touches_opp_box")
    shots_on_target = _sum_event(rows, "ShotsOnTarget")
    chances_created = _sum_event(rows, "chances_created")
    successful_dribbles = _sum_event(rows, "dribbles_succeeded")

    event_note = (
        "FotMob omits zero-valued event cards; absent player event keys in a "
        "complete detailed match are calculated as zero."
    )
    return {
        "npg90": (
            _per90_feature(
                npg,
                npg_minutes,
                source_fields=npg_source_fields,
                note=npg_note,
            )
            if npg is not None
            else None
        ),
        "xg90": _per90_feature(
            non_penalty_xg,
            xg_minutes,
            source_fields=["expected_goals_non_penalty", "expected_goals fallback"],
            note=(
                "Non-penalty xG is used when its competition supplies the field; xG is "
                "the fallback only for competitions that supply xG but not non-penalty xG. "
                "Competitions without either field are excluded from this denominator."
            ),
        ),
        "sca90": None,
        "axa90": _feature(
            axa_value,
            unit="per90",
            source=MATCH_SOURCE,
            source_fields=["assists", "expected_assists"],
            note=(
                f"Assists use {round(minutes, 1)} available minutes; xA uses "
                f"{round(xa_minutes, 1)} minutes from competitions where xA is supplied."
            ),
        ),
        "bt90": _per90_feature(
            box_touches,
            minutes,
            source_fields=["touches_opp_box"],
            note=event_note,
        ),
        "sot90": _per90_feature(
            shots_on_target,
            minutes,
            source_fields=["ShotsOnTarget"],
            note=event_note,
        ),
        "kp90": _per90_feature(
            chances_created,
            minutes,
            source_fields=["chances_created"],
            note=event_note,
        ),
        "drib90": _per90_feature(
            successful_dribbles,
            minutes,
            source_fields=["dribbles_succeeded"],
            note=event_note,
        ),
        "pc90": None,
        "press90": _leaderboard_rate(season_rows, "poss_won_att_3rd"),
    }, flags


def _defender_features(
    rows: list[dict[str, Any]],
    minutes: float,
) -> tuple[dict[str, Any], list[str]]:
    errors = _sum_event(rows, "errors_led_to_goal")
    tackles = _sum_event(rows, "matchstats.headers.tackles")
    interceptions = _sum_event(rows, "interceptions")
    dribbled_past = _sum_event(rows, "dribbled_past")
    clearances_blocks = _sum_event(rows, "clearances") + _sum_event(rows, "blocked_shots", "shot_blocks")
    aerial_pct, aerial_won, aerial_total = _ratio(rows, "aerials_won")
    ground_pct, ground_won, ground_total = _ratio(rows, "ground_duels_won")
    pass_pct, passes_complete, passes_attempted = _ratio(rows, "accurate_passes")
    event_note = (
        "FotMob omits zero-valued event cards; absent player event keys in a "
        "complete detailed match are calculated as zero."
    )
    return {
        "err": _per90_feature(
            errors,
            minutes,
            source_fields=["errors_led_to_goal"],
            note=event_note,
        ),
        "v1v1": _per90_feature(
            tackles,
            minutes,
            source_fields=["matchstats.headers.tackles"],
            note="WCALPHA v1 tackle-performance proxy. " + event_note,
        ),
        "aer": _feature(
            aerial_pct,
            unit="percent",
            source=MATCH_SOURCE,
            source_fields=["aerials_won.value", "aerials_won.total"],
            numerator=aerial_won,
            note=f"{int(aerial_total)} recorded aerial-duel attempts.",
        ),
        "int90": _per90_feature(
            interceptions,
            minutes,
            source_fields=["interceptions"],
            note=event_note,
        ),
        "gnd": _feature(
            ground_pct,
            unit="percent",
            source=MATCH_SOURCE,
            source_fields=["ground_duels_won.value", "ground_duels_won.total"],
            numerator=ground_won,
            note=f"{int(ground_total)} recorded ground-duel attempts.",
        ),
        "drp": _per90_feature(
            dribbled_past,
            minutes,
            source_fields=["dribbled_past"],
            note=event_note,
        ),
        "pace": None,
        "clrblk": _per90_feature(
            clearances_blocks,
            minutes,
            source_fields=["clearances", "blocked_shots", "shot_blocks"],
            note=event_note,
        ),
        "passpct": _feature(
            pass_pct,
            unit="percent",
            source=MATCH_SOURCE,
            source_fields=["accurate_passes.value", "accurate_passes.total"],
            numerator=passes_complete,
            note=f"{int(passes_attempted)} recorded pass attempts.",
        ),
        "vers": None,
    }, []


def build_player_features(
    squads: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    historical_rows: list[dict[str, Any]],
    season_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Aggregate previous-season PL/UCL evidence for current squad players."""

    history_by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in historical_rows:
        player_id = row.get("player_id")
        if player_id is not None:
            history_by_player[int(player_id)].append(row)

    season_by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in season_rows:
        player_id = row.get("participant_id")
        if player_id is not None:
            season_by_player[int(player_id)].append(row)

    metric_competitions: dict[str, set[tuple[Any, Any]]] = defaultdict(set)
    for row in historical_rows:
        competition_key = (row.get("competition_id"), row.get("competition"))
        for metric, item in (row.get("metrics") or {}).items():
            if _number((item or {}).get("value")) is not None:
                metric_competitions[metric].add(competition_key)

    teams_by_id = {int(row["team_id"]): row for row in teams}
    output: list[dict[str, Any]] = []
    for squad in squads:
        spos = scoring_position(squad.get("position"), squad.get("squad_group"))
        if not spos:
            continue
        player_id = int(squad["player_id"])
        rows = history_by_player.get(player_id, [])
        minutes = sum(
            _number(((row.get("metrics") or {}).get("minutes_played") or {}).get("value")) or 0.0
            for row in rows
        )
        current_team = teams_by_id.get(int(squad["team_id"]), {})
        league_key, league_multiplier, league_mapped = _league_quality(current_team, config)
        player_season_rows = season_by_player.get(player_id, [])
        if spos == "FW":
            features, flags = _attacker_features(
                rows,
                player_season_rows,
                minutes,
                metric_competitions,
            )
        else:
            features, flags = _defender_features(rows, minutes)
        if not league_mapped:
            flags.append("league_quality_default")

        output.append(
            {
                "formula_version": config["version"],
                "player_id": player_id,
                "player": squad.get("player"),
                "current_team_id": int(squad["team_id"]),
                "current_team": squad.get("team"),
                "current_position": squad.get("position"),
                "primary_position": primary_position(squad.get("position")),
                "squad_group": squad.get("squad_group"),
                "scoring_position": spos,
                "age": squad.get("age"),
                "injury": squad.get("injury"),
                "current_competition_flags": {
                    "premier_league_2026_27": bool(current_team.get("premier_league_2026_27")),
                    "ucl_status": current_team.get("ucl_status"),
                },
                "league_quality": {
                    "key": league_key,
                    "multiplier": league_multiplier,
                    "source_league_id": current_team.get("primary_league_id"),
                    "source_league": current_team.get("primary_league"),
                    "mapped": league_mapped,
                },
                "sample": {
                    "season": "2025/2026",
                    "competitions": _competition_breakdown(rows),
                    "matches": len({row.get("match_id") for row in rows}),
                    "minutes": round(minutes, 3),
                    "historical_team_ids": sorted({int(row["team_id"]) for row in rows if row.get("team_id") is not None}),
                    "historical_teams": sorted({str(row["team"]) for row in rows if row.get("team")}),
                },
                "features": features,
                "quality_flags": sorted(set(flags)),
            }
        )
    return output


def _resolved_formula(scoring_pos: str, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    formula = config["formulas"][scoring_pos]
    if "inherits" in formula:
        formula = config["formulas"][formula["inherits"]]
    return formula


def score_player(
    player: dict[str, Any],
    population: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Score one player with the exact WCALPHA v1 normalization policy."""

    spos = player["scoring_position"]
    formula = _resolved_formula(spos, config)
    peers = [row for row in population if row.get("scoring_position") == spos]
    minimum_population = int(config["peer_method"]["minimum_population"])
    clamp = float(config["peer_method"]["z_score_clamp"])
    multiplier = float(player["league_quality"]["multiplier"])
    weighted_sum = 0.0
    total_weight = 0.0
    confirmed = 0
    metric_scores: dict[str, Any] = {}

    for key, metric_config in formula.items():
        weight = float(metric_config["weight"])
        feature = (player.get("features") or {}).get(key)
        raw = _number((feature or {}).get("value"))
        if raw is None:
            metric_scores[key] = {
                "z": None,
                "confidence": "missing",
                "weight": weight,
                "direction": metric_config["direction"],
            }
            continue

        sign = -1.0 if metric_config["direction"] == "inverted" else 1.0
        adjusted = sign * raw * multiplier
        population_values = []
        for peer in peers:
            peer_feature = (peer.get("features") or {}).get(key)
            peer_raw = _number((peer_feature or {}).get("value"))
            if peer_raw is None:
                continue
            peer_multiplier = float(peer["league_quality"]["multiplier"])
            population_values.append(sign * peer_raw * peer_multiplier)

        if len(population_values) < minimum_population:
            metric_scores[key] = {
                "z": None,
                "confidence": "insufficient_pop",
                "raw": raw,
                "weight": weight,
                "direction": metric_config["direction"],
                "peer_count": len(population_values),
            }
            continue

        mean = statistics.mean(population_values)
        sd = statistics.stdev(population_values) if len(population_values) > 1 else 1.0
        z = 0.0 if sd < 0.001 else max(-clamp, min(clamp, (adjusted - mean) / sd))
        metric_scores[key] = {
            "z": round(z, 3),
            "raw": raw,
            "league_adjusted": round(adjusted, 6),
            "peer_mean": round(mean, 6),
            "peer_sample_sd": round(sd, 6),
            "peer_count": len(population_values),
            "source": feature.get("source"),
            "confidence": feature.get("confidence"),
            "weight": weight,
            "direction": metric_config["direction"],
        }
        weighted_sum += z * weight
        total_weight += weight
        confirmed += 1

    if total_weight <= 0:
        return None

    coverage_pct = confirmed / len(formula) * 100.0
    composite_z = weighted_sum / total_weight
    minutes = float(player["sample"]["minutes"])
    minutes_weight = minutes_reliability_weight(minutes, config)
    coverage_weight = coverage_reliability_weight(coverage_pct, composite_z, config)
    adjusted_z = composite_z * minutes_weight * coverage_weight
    coverage = config["coverage"]
    quality = (
        "HIGH"
        if coverage_pct >= float(coverage["high_minimum_pct"])
        else "MEDIUM"
        if coverage_pct >= float(coverage["medium_minimum_pct"])
        else "LOW"
    )
    eligibility = config["ranking_eligibility"]
    ranking_eligible = (
        minutes >= float(eligibility["minimum_minutes"])
        and coverage_pct >= float(eligibility["minimum_coverage_pct"])
    )
    return {
        "formula_version": config["version"],
        "player_id": player["player_id"],
        "player": player["player"],
        "current_team_id": player["current_team_id"],
        "current_team": player["current_team"],
        "current_position": player["current_position"],
        "scoring_position": spos,
        "league_quality": player["league_quality"],
        "minutes": round(minutes, 3),
        "matches": player["sample"]["matches"],
        "alpha_ability_z": round(composite_z, 3),
        "composite_z": round(composite_z, 3),
        "reliability_adjusted_z": round(adjusted_z, 3),
        "minutes_weight": minutes_weight,
        "coverage_weight": round(coverage_weight, 3),
        "confirmed_metrics": confirmed,
        "total_metrics": len(formula),
        "coverage_pct": round(coverage_pct, 1),
        "quality": quality,
        "ranking_eligible": ranking_eligible,
        "metrics": metric_scores,
        "quality_flags": player.get("quality_flags") or [],
    }


def score_population(
    player_features: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    scores = [score_player(player, player_features, config) for player in player_features]
    return [score for score in scores if score is not None]


def build_quality_audit(
    features: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    by_team: dict[tuple[int, str], dict[str, int]] = {}
    for row in features:
        key = (row["current_team_id"], row["current_team"])
        bucket = by_team.setdefault(key, {"eligible_roles": 0, "with_history": 0, "graded": 0})
        bucket["eligible_roles"] += 1
        if row["sample"]["minutes"] > 0:
            bucket["with_history"] += 1
    for row in grades:
        key = (row["current_team_id"], row["current_team"])
        by_team[key]["graded"] += 1

    def counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
        result: dict[str, int] = defaultdict(int)
        for row in rows:
            result[str(row.get(field))] += 1
        return dict(sorted(result.items()))

    eligible = [row for row in grades if row["ranking_eligible"]]
    leaders: dict[str, list[dict[str, Any]]] = {}
    for spos in ("FW", "CB", "FB"):
        ranked = sorted(
            (row for row in eligible if row["scoring_position"] == spos),
            key=lambda row: row["alpha_ability_z"],
            reverse=True,
        )
        leaders[spos] = [
            {
                "player_id": row["player_id"],
                "player": row["player"],
                "team": row["current_team"],
                "alpha_ability_z": row["alpha_ability_z"],
                "reliability_adjusted_z": row["reliability_adjusted_z"],
                "minutes": row["minutes"],
                "coverage_pct": row["coverage_pct"],
            }
            for row in ranked[:10]
        ]

    team_coverage = [
        {
            "team_id": team_id,
            "team": team,
            **values,
            "missing_history": values["eligible_roles"] - values["with_history"],
        }
        for (team_id, team), values in sorted(by_team.items(), key=lambda item: item[0][1])
    ]
    return {
        "formula_version": config["version"],
        "scope": "Current 2026/27 PL, confirmed UCL, and UCL play-off squads; 2025/26 PL/UCL evidence only",
        "feature_players": len(features),
        "feature_players_by_position": counts(features, "scoring_position"),
        "players_with_historical_minutes": sum(1 for row in features if row["sample"]["minutes"] > 0),
        "players_without_historical_minutes": sum(1 for row in features if row["sample"]["minutes"] <= 0),
        "graded_players": len(grades),
        "graded_players_by_position": counts(grades, "scoring_position"),
        "quality_bands": counts(grades, "quality"),
        "ranking_eligible_players": len(eligible),
        "league_quality_defaulted_players": sum(
            1 for row in features if not row["league_quality"]["mapped"]
        ),
        "goal_reconciliation_flags": sum(
            1
            for row in features
            if "match_goals_do_not_reconcile_to_season_leaderboard" in row["quality_flags"]
        ),
        "known_formula_gaps": {
            "FW": ["sca90", "pc90"],
            "CB_FB": ["pace", "vers"],
            "note": "Gaps remain missing and their weights are excluded, matching WCALPHA v1.",
        },
        "ranking_policy": config["ranking_eligibility"],
        "leaders": leaders,
        "team_coverage": team_coverage,
    }
