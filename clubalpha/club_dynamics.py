"""Club Dynamics v1: style, strengths/weaknesses, and club change state."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

from clubalpha.club_form import normalisation_group, parse_datetime
from clubalpha.fotmob import normalize_name


def _divide(numerator: Any, denominator: Any, multiplier: float = 1.0) -> float | None:
    if numerator is None or denominator is None or float(denominator) <= 0:
        return None
    return float(numerator) / float(denominator) * multiplier


def derive_dynamic_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """Derive interpretable style and strength values from one team-match row."""

    output = dict(row)
    half_passes = None
    if row.get("own_half_passes_for") is not None and row.get("opposition_half_passes_for") is not None:
        half_passes = float(row["own_half_passes_for"]) + float(row["opposition_half_passes_for"])
    output["style_raw"] = {
        "control": row.get("possession_pct_for"),
        "territory": _divide(row.get("opposition_half_passes_for"), half_passes, 100.0),
        "directness": _divide(row.get("long_balls_attempted_est_for"), row.get("passes_for"), 100.0),
        "crossing": _divide(
            row.get("crosses_attempted_est_for"), row.get("opposition_half_passes_for"), 100.0
        ),
        "set_piece_reliance": _divide(
            row.get("expected_goals_set_play_for"), row.get("expected_goals_for"), 100.0
        ),
    }
    output["strength_raw"] = {
        "chance_creation": row.get("expected_goals_for"),
        "shot_quality": _divide(row.get("expected_goals_for"), row.get("total_shots_for")),
        "finishing": (
            float(row["goals_for"]) - float(row["expected_goals_for"])
            if row.get("goals_for") is not None and row.get("expected_goals_for") is not None
            else None
        ),
        "box_access": row.get("touches_opp_box_for"),
        "set_piece_attack": row.get("expected_goals_set_play_for"),
        "chance_prevention": row.get("expected_goals_against"),
        "shot_suppression": row.get("total_shots_against"),
        "box_defense": row.get("touches_opp_box_against"),
        "set_piece_defense": row.get("expected_goals_set_play_against"),
    }
    return output


def _sample_scale(values: list[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    spread = statistics.stdev(values)
    if spread <= 1e-12:
        return None
    return statistics.mean(values), spread


def fit_dynamic_scales(
    rows: list[dict[str, Any]], category: str, axes: list[str], config: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    global_values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        group = normalisation_group(row, config)
        for axis in axes:
            value = (row.get(f"{category}_raw") or {}).get(axis)
            if value is not None:
                grouped[group][axis].append(float(value))
                global_values[axis].append(float(value))
    minimum = int(config["normalisation"]["minimum_peer_team_rows"])
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for group, values_by_axis in grouped.items():
        output[group] = {}
        for axis in axes:
            values = values_by_axis.get(axis, [])
            if not values:
                continue
            scale = _sample_scale(values) if len(values) >= minimum else None
            source = "competition"
            if scale is None:
                scale = _sample_scale(global_values.get(axis, []))
                source = "global_fallback"
            if scale:
                output[group][axis] = {
                    "mean": scale[0],
                    "sample_sd": scale[1],
                    "peer_rows": len(values),
                    "source": source,
                }
    return output


def score_dynamic_observations(
    observations: Iterable[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [derive_dynamic_metrics(row) for row in observations]
    axis_specs = {
        "style": [item for item in config["style"]["axes"] if item["key"] != "high_pressing"],
        "strength": config["strengths"]["axes"],
    }
    scales: dict[str, Any] = {}
    cap = float(config["normalisation"]["z_cap"])
    for category, specs in axis_specs.items():
        axes = [item["key"] for item in specs]
        category_scales = fit_dynamic_scales(rows, category, axes, config)
        scales[category] = category_scales
        directions = {item["key"]: item.get("direction", "higher") for item in specs}
        for row in rows:
            group = normalisation_group(row, config)
            row[f"{category}_z"] = {}
            for axis in axes:
                scale = (category_scales.get(group) or {}).get(axis)
                value = (row.get(f"{category}_raw") or {}).get(axis)
                z_value = None
                if scale and value is not None:
                    z_value = (float(value) - scale["mean"]) / scale["sample_sd"]
                    if directions[axis] == "lower":
                        z_value *= -1
                    z_value = max(-cap, min(cap, z_value))
                row[f"{category}_z"][axis] = round(z_value, 6) if z_value is not None else None
    return rows, scales


def _weighted_axis(
    rows: list[dict[str, Any]], category: str, axis: str, as_of: date, policy: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    available: list[tuple[dict[str, Any], float, float]] = []
    half_life = float(policy["half_life_days"])
    for row in rows:
        value = (row.get(f"{category}_z") or {}).get(axis)
        kickoff = parse_datetime(row.get("kickoff_utc"))
        if value is None or kickoff is None or kickoff.date() > as_of:
            continue
        age_days = max(0, (as_of - kickoff.date()).days)
        source_weight = float(
            policy["source_weights"].get(
                str(row.get("source_scope")), policy["source_weights"]["default"]
            )
        )
        available.append((row, float(value), (0.5 ** (age_days / half_life)) * source_weight))
    if not available:
        return {"z": None, "raw_z": None, "confidence": 0.0, "matches": 0, "evidence": 0.0}
    preseason = [
        index
        for index, (row, _, _) in enumerate(available)
        if str(row.get("source_scope")) == "preseason_2026"
    ]
    weights = [weight for _, _, weight in available]
    competitive_weight = sum(weight for index, weight in enumerate(weights) if index not in preseason)
    preseason_weight = sum(weights[index] for index in preseason)
    maximum_share = float(policy["maximum_preseason_weight_share"])
    if competitive_weight > 0 and preseason_weight > 0:
        maximum = competitive_weight * maximum_share / (1.0 - maximum_share)
        if preseason_weight > maximum:
            factor = maximum / preseason_weight
            for index in preseason:
                weights[index] *= factor
    evidence = sum(weights)
    raw = sum(value * weight for (_, value, _), weight in zip(available, weights)) / evidence
    prior = float(policy["prior_weighted_matches"])
    confidence = evidence / (evidence + prior)
    return {
        "z": round(raw * confidence, 4),
        "raw_z": round(raw, 4),
        "confidence": round(confidence, 4),
        "matches": len(available),
        "evidence": round(evidence, 4),
    }


def _style_label(value: float | None, spec: dict[str, Any], threshold: float) -> str | None:
    if value is None:
        return None
    if value >= threshold:
        return spec["high"]
    if value <= -threshold:
        return spec["low"]
    return spec["neutral"]


def _season_high_pressing(
    team: dict[str, Any], season_stats: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    metric_rows = [row for row in season_stats if row.get("metric") == "poss_won_att_3rd_team"]
    by_competition: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in metric_rows:
        if row.get("competition_id") is not None and row.get("value") is not None:
            by_competition[int(row["competition_id"])].append(row)
    candidates = [
        row
        for row in metric_rows
        if normalize_name(row.get("participant")) == normalize_name(team.get("name"))
    ]
    preferred = int(team.get("primary_league_id") or 0)
    selected = next((row for row in candidates if int(row.get("competition_id") or 0) == preferred), None)
    if selected is None:
        selected = next((row for row in candidates if int(row.get("competition_id") or 0) == 42), None)
    if selected is None and candidates:
        selected = candidates[0]
    if selected is None:
        return {"z": None, "raw_z": None, "confidence": 0.0, "matches": 0, "evidence": 0.0, "source": "missing"}
    peers = [float(row["value"]) for row in by_competition[int(selected["competition_id"])] if row.get("value") is not None]
    scale = _sample_scale(peers)
    if scale is None:
        return {"z": None, "raw_z": None, "confidence": 0.0, "matches": 0, "evidence": 0.0, "source": "missing_scale"}
    raw = (float(selected["value"]) - scale[0]) / scale[1]
    raw = max(-float(config["normalisation"]["z_cap"]), min(float(config["normalisation"]["z_cap"]), raw))
    matches = int(selected.get("matches") or 0)
    confidence = matches / (matches + float(config["style"]["prior_weighted_matches"])) if matches else 0.0
    return {
        "z": round(raw * confidence, 4),
        "raw_z": round(raw, 4),
        "confidence": round(confidence, 4),
        "matches": matches,
        "evidence": float(matches),
        "source": "previous_season_team_stat",
        "competition": selected.get("competition"),
        "raw_value": selected.get("value"),
    }


def build_style_profile(
    team: dict[str, Any], rows: list[dict[str, Any]], season_stats: list[dict[str, Any]], as_of: date, config: dict[str, Any]
) -> dict[str, Any]:
    threshold = float(config["style"]["descriptor_threshold_z"])
    output: dict[str, Any] = {}
    for spec in config["style"]["axes"]:
        axis = spec["key"]
        result = (
            _season_high_pressing(team, season_stats, config)
            if axis == "high_pressing"
            else _weighted_axis(rows, "style", axis, as_of, config["style"], config)
        )
        result["label"] = spec["label"]
        result["descriptor"] = _style_label(result.get("z"), spec, threshold)
        output[axis] = result
    available = [item for item in output.values() if item.get("z") is not None]
    current_scopes = set(config["change_state"]["integration_match_scopes"])
    current_rows = [row for row in rows if str(row.get("source_scope")) in current_scopes]
    previous_rows = [row for row in rows if str(row.get("source_scope")) not in current_scopes]
    shift_axes: dict[str, Any] = {}
    for spec in config["style"]["axes"]:
        axis = spec["key"]
        if axis == "high_pressing":
            continue
        current = _weighted_axis(current_rows, "style", axis, as_of, config["style"], config)
        previous = _weighted_axis(previous_rows, "style", axis, as_of, config["style"], config)
        delta = (
            float(current["raw_z"]) - float(previous["raw_z"])
            if current.get("raw_z") is not None and previous.get("raw_z") is not None
            else None
        )
        shift_confidence = min(float(previous["confidence"]), float(current["confidence"]))
        direction = None
        if delta is not None:
            direction = (
                "insufficient evidence"
                if shift_confidence < float(config["style"]["minimum_shift_confidence"])
                else f"moving toward {spec['high']}" if delta >= threshold
                else f"moving toward {spec['low']}" if delta <= -threshold
                else "broadly stable"
            )
        shift_axes[axis] = {
            "previous_raw_z": previous.get("raw_z"),
            "post_season_boundary_raw_z": current.get("raw_z"),
            "delta_raw_z": round(delta, 4) if delta is not None else None,
            "confidence": round(shift_confidence, 4),
            "direction": direction,
        }
    return {
        "axes": output,
        "coverage": round(len(available) / len(output), 4),
        "identity": [
            {"axis": key, "descriptor": item["descriptor"], "z": item["z"]}
            for key, item in sorted(output.items(), key=lambda pair: abs(float(pair[1].get("z") or 0)), reverse=True)
            if item.get("z") is not None
        ][:3],
        "season_boundary_shift": {
            "axes": shift_axes,
            "manager_causality_claimed": False,
            "note": "This compares previous competitive evidence with preseason/current evidence; it does not prove the manager caused the change.",
        },
        "composite_score": None,
    }


def build_strength_profile(
    rows: list[dict[str, Any]], as_of: date, config: dict[str, Any]
) -> dict[str, Any]:
    threshold = float(config["strengths"]["classification_threshold_z"])
    axes: dict[str, Any] = {}
    for spec in config["strengths"]["axes"]:
        result = _weighted_axis(rows, "strength", spec["key"], as_of, config["strengths"], config)
        result.update({"label": spec["label"], "unit": spec["unit"]})
        # Classification uses the underlying signal while the published z is
        # reliability-shrunk. This keeps a clear strength visible without
        # pretending that thin evidence has the same certainty as a full sample.
        value = result.get("raw_z")
        enough_evidence = float(result["confidence"]) >= float(
            config["strengths"]["minimum_classification_confidence"]
        )
        result["classification"] = (
            "insufficient_evidence" if value is not None and not enough_evidence
            else "strength" if value is not None and value >= threshold
            else "weakness" if value is not None and value <= -threshold
            else "neutral" if value is not None else None
        )
        axes[spec["key"]] = result
    ranked = sorted(
        ((key, value) for key, value in axes.items() if value.get("z") is not None),
        key=lambda pair: float(pair[1]["z"]),
        reverse=True,
    )
    return {
        "axes": axes,
        "strengths": [
            {"axis": key, "label": item["label"], "z": item["z"]}
            for key, item in ranked if item["classification"] == "strength"
        ][:3],
        "weaknesses": [
            {"axis": key, "label": item["label"], "z": item["z"]}
            for key, item in reversed(ranked) if item["classification"] == "weakness"
        ][:3],
        "coverage": round(sum(item.get("z") is not None for item in axes.values()) / len(axes), 4),
        "composite_score": None,
    }


def _player_minutes(row: dict[str, Any]) -> float:
    value = ((row.get("metrics") or {}).get("minutes_played") or {}).get("value")
    return float(value or 0.0)


def build_change_state(
    team: dict[str, Any],
    snapshot: dict[str, Any] | None,
    previous_snapshot: dict[str, Any] | None,
    manager_history: list[dict[str, Any]],
    transfers: list[dict[str, Any]],
    grades_by_player: dict[int, dict[str, Any]],
    player_matches: list[dict[str, Any]],
    team_matches: list[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
) -> dict[str, Any]:
    team_id = int(team["team_id"])
    current_coach = (snapshot or {}).get("current_coach")
    previous_coaches = [
        row for row in manager_history
        if int(row.get("team_id") or 0) == team_id and row.get("season") == config["previous_season"]
    ]
    previous_ids = {int(row["coach_id"]) for row in previous_coaches if row.get("coach_id") is not None}
    manager_changed = (
        int(current_coach["coach_id"]) not in previous_ids
        if current_coach and previous_ids else None
    )
    integration_scopes = set(config["change_state"]["integration_match_scopes"])
    regime_matches = {
        int(row["match_id"])
        for row in team_matches
        if int(row["team_id"]) == team_id
        and str(row.get("source_scope")) in integration_scopes
        and parse_datetime(row.get("kickoff_utc"))
        and parse_datetime(row.get("kickoff_utc")).date() <= as_of
    }
    manager_prior = float(config["change_state"]["manager_evidence_prior_matches"])
    manager_stability = (
        1.0 if manager_changed is False
        else len(regime_matches) / (len(regime_matches) + manager_prior) if manager_changed is True
        else None
    )
    manager_state = (
        "continuity" if manager_changed is False
        else "early_transition" if manager_stability is not None and manager_stability < 0.4
        else "developing_transition" if manager_stability is not None and manager_stability < 0.7
        else "established_transition" if manager_changed is True
        else "unknown"
    )

    window_start = date.fromisoformat(config["change_window_start"])
    eligible_transfers = [
        row for row in transfers
        if int(row.get("team_id") or 0) == team_id
        and row.get("effective_date")
        and window_start <= date.fromisoformat(row["effective_date"]) <= as_of
        and (not row.get("reported_at_utc") or str(row["reported_at_utc"])[:10] <= as_of.isoformat())
    ]
    # FotMob can retain an earlier transfer report after publishing an updated
    # destination or loan record. Keep the latest report known by the snapshot
    # for each club/player/direction/effective-date event.
    transfer_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in eligible_transfers:
        key = (str(row.get("direction")), int(row["player_id"]), str(row["effective_date"]))
        existing = transfer_index.get(key)
        if existing is None or str(row.get("reported_at_utc") or "") > str(existing.get("reported_at_utc") or ""):
            transfer_index[key] = row
    selected_transfers = list(transfer_index.values())
    detailed_team_matches = {
        (int(row["team_id"]), int(row["match_id"])) for row in player_matches
        if row.get("team_id") is not None and row.get("match_id") is not None
    }
    match_lookup = {
        (int(row["team_id"]), int(row["match_id"])): row for row in team_matches
        if row.get("team_id") is not None and row.get("match_id") is not None
    }
    transfer_details: list[dict[str, Any]] = []
    for transfer in selected_transfers:
        item = dict(transfer)
        grade = grades_by_player.get(int(item["player_id"]))
        item["alpha_ability_z"] = grade.get("alpha_ability_z") if grade else None
        item["alpha_position"] = grade.get("scoring_position") if grade else None
        item["integration"] = None
        if item["direction"] == "in":
            effective = date.fromisoformat(item["effective_date"])
            eligible_ids = {
                match_id for candidate_team, match_id in detailed_team_matches
                if candidate_team == team_id
                and (match_lookup.get((team_id, match_id)) or {}).get("source_scope") in integration_scopes
                and parse_datetime((match_lookup.get((team_id, match_id)) or {}).get("kickoff_utc"))
                and effective <= parse_datetime(match_lookup[(team_id, match_id)]["kickoff_utc"]).date() <= as_of
            }
            appearances = [
                row for row in player_matches
                if int(row.get("team_id") or 0) == team_id
                and int(row.get("player_id") or 0) == int(item["player_id"])
                and int(row.get("match_id") or 0) in eligible_ids
            ]
            available_minutes = 90.0 * len(eligible_ids)
            minutes = sum(_player_minutes(row) for row in appearances)
            item["integration"] = {
                "detailed_team_matches_available": len(eligible_ids),
                "appearances": sum(_player_minutes(row) > 0 for row in appearances),
                "minutes": round(minutes, 1),
                "minute_share": round(min(1.0, minutes / available_minutes), 4) if available_minutes else None,
            }
            share = item["integration"]["minute_share"]
            item["impact_state"] = (
                "quality_unknown" if item.get("alpha_ability_z") is None
                else "integration_unobserved" if share is None
                else "potential_unintegrated" if share < 0.1
                else "partially_integrated" if share < 0.6
                else "integrated"
            )
        else:
            item["impact_state"] = "departed_quality_known" if item.get("alpha_ability_z") is not None else "departed_quality_unknown"
        transfer_details.append(item)

    incoming = [row for row in transfer_details if row["direction"] == "in"]
    outgoing = [row for row in transfer_details if row["direction"] == "out"]
    incoming_shares = [
        float(row["integration"]["minute_share"])
        for row in incoming
        if row.get("integration") and row["integration"].get("minute_share") is not None
    ]
    known_in = [float(row["alpha_ability_z"]) for row in incoming if row.get("alpha_ability_z") is not None]
    known_out = [float(row["alpha_ability_z"]) for row in outgoing if row.get("alpha_ability_z") is not None]
    minutes_weighted_known_in = [
        float(row["alpha_ability_z"]) * float(row["integration"]["minute_share"])
        for row in incoming
        if row.get("alpha_ability_z") is not None
        and row.get("integration")
        and row["integration"].get("minute_share") is not None
    ]

    continuity = None
    if snapshot and previous_snapshot:
        current_players = set(snapshot.get("squad_player_ids") or [])
        previous_players = set(previous_snapshot.get("squad_player_ids") or [])
        continuity = {
            "previous_snapshot_date": previous_snapshot.get("snapshot_date"),
            "retained_share": round(len(current_players & previous_players) / len(previous_players), 4) if previous_players else None,
            "added_since_snapshot": len(current_players - previous_players),
            "removed_since_snapshot": len(previous_players - current_players),
        }
    return {
        "manager": {
            "current": current_coach,
            "previous_season": [
                {"coach_id": row["coach_id"], "coach": row.get("coach"), "matches": sum(int(row.get(key) or 0) for key in ("wins", "draws", "losses"))}
                for row in previous_coaches
            ],
            "changed_since_previous_season": manager_changed,
            "state": manager_state,
            "detection_method": "current coach compared with previous-season FotMob coach history",
            "post_season_boundary_matches": len(regime_matches),
            "stability_confidence": round(manager_stability, 4) if manager_stability is not None else None,
            "appointment_date": None,
        },
        "transfers": {
            "window_start": window_start.isoformat(),
            "incoming": len(incoming),
            "outgoing": len(outgoing),
            "alpha_coverage": round((len(known_in) + len(known_out)) / len(transfer_details), 4) if transfer_details else 1.0,
            "incoming_alpha_z_sum": round(sum(known_in), 4),
            "outgoing_alpha_z_sum": round(sum(known_out), 4),
            "net_known_alpha_z": round(sum(known_in) - sum(known_out), 4),
            "minutes_weighted_known_incoming_alpha_z": round(sum(minutes_weighted_known_in), 4),
            "incoming_integration_confidence": round(statistics.mean(incoming_shares), 4) if incoming_shares else (1.0 if not incoming else None),
            "incoming_integration_coverage": round(len(incoming_shares) / len(incoming), 4) if incoming else 1.0,
            "events": transfer_details,
            "fee_and_market_value_used_in_model": False,
        },
        "squad_continuity": continuity,
        "score_modifier": None,
        "modifier_note": config["change_state"]["note"],
    }


def build_club_dynamics(
    observations: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    snapshot_history: list[dict[str, Any]],
    manager_history: list[dict[str, Any]],
    transfers: list[dict[str, Any]],
    season_stats: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    player_matches: list[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    eligible_observations = [
        row
        for row in observations
        if parse_datetime(row.get("kickoff_utc"))
        and parse_datetime(row.get("kickoff_utc")).date() <= as_of
    ]
    scored, scales = score_dynamic_observations(eligible_observations, config)
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        by_team[int(row["team_id"])].append(row)
    snapshots_by_team = {int(row["team_id"]): row for row in snapshots}
    grades_by_player = {int(row["player_id"]): row for row in grades}
    profiles: list[dict[str, Any]] = []
    for team in teams:
        team_id = int(team["team_id"])
        current_snapshot = snapshots_by_team.get(team_id)
        prior_candidates = sorted(
            (
                row for row in snapshot_history
                if int(row.get("team_id") or 0) == team_id and str(row.get("snapshot_date") or "") < as_of.isoformat()
            ),
            key=lambda row: str(row.get("snapshot_date") or ""),
        )
        change = build_change_state(
            team,
            current_snapshot,
            prior_candidates[-1] if prior_candidates else None,
            manager_history,
            transfers,
            grades_by_player,
            player_matches,
            by_team.get(team_id, []),
            as_of,
            config,
        )
        style = build_style_profile(team, by_team.get(team_id, []), season_stats, as_of, config)
        if change["manager"]["changed_since_previous_season"] is True and style["axes"]["high_pressing"].get("z") is not None:
            style["axes"]["high_pressing"]["quality_flag"] = "predates_current_manager"
        profiles.append(
            {
                "dynamics_version": config["version"],
                "as_of": as_of.isoformat(),
                "team_id": team_id,
                "team": team.get("name"),
                "premier_league_2026_27": bool(team.get("premier_league_2026_27")),
                "ucl_status": team.get("ucl_status"),
                "style": style,
                "strengths_weaknesses": build_strength_profile(by_team.get(team_id, []), as_of, config),
                "change_state": change,
                "quality_flags": sorted(
                    flag for flag, present in (
                        ("no_style_profile", style["coverage"] == 0),
                        ("partial_style_profile", 0 < style["coverage"] < 1),
                        ("manager_identity_missing", change["manager"]["current"] is None),
                        ("first_squad_snapshot", change["squad_continuity"] is None),
                    ) if present
                ),
            }
        )
    profiles.sort(key=lambda row: (row.get("team") or "", row["team_id"]))
    return profiles, scored, scales
