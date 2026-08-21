"""Clubalpha Club Form v1.

This layer answers a narrow question: what condition is a club in now? It
turns FotMob match cards into recency-weighted attacking and defensive form.
Player Quality remains separate and is used only to annotate injury risk.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from clubalpha.fotmob import flatten_match_team_stats


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def dedupe_fixtures(*fixture_sets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_match: dict[int, dict[str, Any]] = {}
    for fixtures in fixture_sets:
        for fixture in fixtures:
            if fixture.get("match_id") is None:
                continue
            by_match.setdefault(int(fixture["match_id"]), fixture)
    return sorted(by_match.values(), key=lambda row: (row.get("kickoff_utc") or "", row["match_id"]))


def build_match_observations(
    fixtures: Iterable[dict[str, Any]], cache_dir: Path, as_of: date
) -> tuple[list[dict[str, Any]], list[int]]:
    rows: list[dict[str, Any]] = []
    missing_cache: list[int] = []
    for fixture in fixtures:
        kickoff = parse_datetime(fixture.get("kickoff_utc"))
        if not fixture.get("finished") or kickoff is None or kickoff.date() > as_of:
            continue
        match_id = int(fixture["match_id"])
        cache_path = cache_dir / f"match_{match_id}.json"
        payload: dict[str, Any] = {}
        if cache_path.exists():
            import json

            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            missing_cache.append(match_id)
        rows.extend(flatten_match_team_stats(payload, fixture))
    return rows, missing_cache


def normalisation_group(row: dict[str, Any], config: dict[str, Any]) -> str:
    scope = str(row.get("source_scope") or "")
    policy = config["normalisation"]
    if scope.startswith("champions_league"):
        return str(policy["champions_league_group"])
    if scope == "preseason_2026":
        return str(policy["preseason_group"])
    return f"competition:{row.get('competition_id') or row.get('competition') or 'unknown'}"


def _sample_scale(values: list[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    spread = statistics.stdev(values)
    if spread <= 1e-12:
        return None
    return statistics.mean(values), spread


def fit_peer_scales(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    metrics = [item["key"] for item in config["form_metrics"]]
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    global_values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        group = normalisation_group(row, config)
        for metric in metrics:
            value = row.get(f"{metric}_for")
            if value is not None:
                grouped[group][metric].append(float(value))
                global_values[metric].append(float(value))

    minimum = int(config["normalisation"]["minimum_peer_team_rows"])
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for group, group_metrics in grouped.items():
        output[group] = {}
        for metric in metrics:
            values = group_metrics.get(metric, [])
            scale = _sample_scale(values) if len(values) >= minimum else None
            source = "competition"
            if scale is None:
                scale = _sample_scale(global_values.get(metric, []))
                source = "global_fallback"
            if scale is None:
                continue
            output[group][metric] = {
                "mean": scale[0],
                "sample_sd": scale[1],
                "peer_rows": len(values),
                "source": source,
            }
    return output


def _mean(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return statistics.mean(present) if present else None


def score_match_observations(
    rows: list[dict[str, Any]], as_of: date, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, dict[str, Any]]]]:
    """Competition-normalise match metrics and adjust for opponent strength."""

    metrics = [item["key"] for item in config["form_metrics"]]
    scales = fit_peer_scales(rows, config)
    cap = float(config["normalisation"]["z_cap"])
    scored: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        group = normalisation_group(row, config)
        row["normalisation_group"] = group
        metric_z: dict[str, dict[str, float | None]] = {}
        for metric in metrics:
            scale = (scales.get(group) or {}).get(metric)
            attack_z: float | None = None
            defense_z: float | None = None
            if scale:
                for side in ("for", "against"):
                    value = row.get(f"{metric}_{side}")
                    if value is None:
                        continue
                    z_value = (float(value) - scale["mean"]) / scale["sample_sd"]
                    z_value = max(-cap, min(cap, z_value))
                    if side == "for":
                        attack_z = z_value
                    else:
                        defense_z = -z_value
            metric_z[metric] = {"attack_z": attack_z, "defense_z": defense_z}
        row["metric_z"] = metric_z
        row["attack_match_z_raw"] = _mean(item["attack_z"] for item in metric_z.values())
        row["defense_match_z_raw"] = _mean(item["defense_z"] for item in metric_z.values())
        row["attack_metric_coverage"] = round(
            sum(item["attack_z"] is not None for item in metric_z.values()) / len(metrics), 4
        )
        row["defense_metric_coverage"] = round(
            sum(item["defense_z"] is not None for item in metric_z.values()) / len(metrics), 4
        )
        kickoff = parse_datetime(row.get("kickoff_utc"))
        age_days = max(0, (as_of - kickoff.date()).days) if kickoff else 0
        half_life = float(config["recency"]["half_life_days"])
        source_weight = float(
            config["source_weights"].get(
                str(row.get("source_scope")), config["source_weights"]["default"]
            )
        )
        row["age_days"] = age_days
        row["recency_weight"] = round(0.5 ** (age_days / half_life), 8)
        row["source_weight"] = source_weight
        row["base_match_weight"] = round(row["recency_weight"] * source_weight, 8)
        scored.append(row)

    by_team_group: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in scored:
        by_team_group[(row["normalisation_group"], int(row["team_id"]))].append(row)

    opponent_policy = config["opponent_adjustment"]
    prior = float(opponent_policy["prior_matches"])
    adjustment_cap = float(opponent_policy["adjustment_cap"])
    for row in scored:
        candidates = [
            item
            for item in by_team_group.get(
                (row["normalisation_group"], int(row["opponent_id"])), []
            )
            if item["match_id"] != row["match_id"]
        ]

        def baseline(field: str) -> tuple[float, int]:
            values = [float(item[field]) for item in candidates if item.get(field) is not None]
            if not values:
                return 0.0, 0
            shrunk = statistics.mean(values) * len(values) / (len(values) + prior)
            return max(-adjustment_cap, min(adjustment_cap, shrunk)), len(values)

        opponent_defense, defense_matches = baseline("defense_match_z_raw")
        opponent_attack, attack_matches = baseline("attack_match_z_raw")
        row["opponent_defense_baseline_z"] = round(opponent_defense, 4)
        row["opponent_attack_baseline_z"] = round(opponent_attack, 4)
        row["opponent_baseline_matches"] = {
            "defense": defense_matches,
            "attack": attack_matches,
        }
        attack = row.get("attack_match_z_raw")
        defense = row.get("defense_match_z_raw")
        row["attack_match_z_adjusted"] = (
            round(float(attack) + opponent_defense, 6) if attack is not None else None
        )
        row["defense_match_z_adjusted"] = (
            round(float(defense) + opponent_attack, 6) if defense is not None else None
        )
    return scored, scales


def scope_class(row: dict[str, Any], config: dict[str, Any]) -> str:
    return str(
        config["scope_classes"].get(
            str(row.get("source_scope")), config["scope_classes"]["default"]
        )
    )


def aggregate_form(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    selected = [row for row in rows if predicate is None or predicate(row)]
    if not selected:
        return {
            "attack_z_raw": None,
            "defense_z_raw": None,
            "attack_confidence": 0.0,
            "defense_confidence": 0.0,
            "matches": 0,
            "weighted_match_evidence": 0.0,
            "metric_coverage": 0.0,
            "preseason_weight_share": 0.0,
            "preseason_weight_capped": False,
            "latest_match_utc": None,
        }

    weights = [float(row["base_match_weight"]) for row in selected]
    preseason_indices = [
        index for index, row in enumerate(selected) if scope_class(row, config) == "preseason"
    ]
    competitive_weight = sum(
        weight for index, weight in enumerate(weights) if index not in preseason_indices
    )
    preseason_weight = sum(weights[index] for index in preseason_indices)
    max_share = float(config["preseason"]["maximum_weight_share"])
    capped = False
    if competitive_weight > 0 and preseason_weight > 0 and max_share < 1:
        maximum_preseason_weight = competitive_weight * max_share / (1 - max_share)
        if preseason_weight > maximum_preseason_weight:
            scale = maximum_preseason_weight / preseason_weight
            for index in preseason_indices:
                weights[index] *= scale
            preseason_weight = maximum_preseason_weight
            capped = True

    prior = float(config["reliability"]["prior_weighted_matches"])

    def dimension(name: str) -> tuple[float | None, float, float]:
        weighted_values: list[tuple[float, float]] = []
        for row, base_weight in zip(selected, weights):
            value = row.get(f"{name}_match_z_adjusted")
            coverage = float(row.get(f"{name}_metric_coverage") or 0.0)
            if value is None or coverage <= 0:
                continue
            weighted_values.append((float(value), base_weight * coverage))
        evidence = sum(weight for _, weight in weighted_values)
        raw = (
            sum(value * weight for value, weight in weighted_values) / evidence
            if evidence > 0
            else None
        )
        confidence = evidence / (evidence + prior) if evidence > 0 else 0.0
        return raw, confidence, evidence

    attack, attack_confidence, attack_evidence = dimension("attack")
    defense, defense_confidence, defense_evidence = dimension("defense")
    total_weight = sum(weights)
    coverage = (
        sum(
            weight
            * statistics.mean(
                [
                    float(row.get("attack_metric_coverage") or 0.0),
                    float(row.get("defense_metric_coverage") or 0.0),
                ]
            )
            for row, weight in zip(selected, weights)
        )
        / total_weight
        if total_weight > 0
        else 0.0
    )
    return {
        "attack_z_raw": round(attack, 6) if attack is not None else None,
        "defense_z_raw": round(defense, 6) if defense is not None else None,
        "attack_confidence": round(attack_confidence, 4),
        "defense_confidence": round(defense_confidence, 4),
        "matches": len(selected),
        "current_competitive_matches": sum(
            scope_class(row, config) == "current_competitive" for row in selected
        ),
        "previous_competitive_matches": sum(
            scope_class(row, config) == "previous_competitive" for row in selected
        ),
        "preseason_matches": len(preseason_indices),
        "weighted_match_evidence": round(statistics.mean([attack_evidence, defense_evidence]), 4),
        "metric_coverage": round(coverage, 4),
        "preseason_weight_share": round(preseason_weight / total_weight, 4)
        if total_weight
        else 0.0,
        "preseason_weight_capped": capped,
        "latest_match_utc": max(str(row.get("kickoff_utc") or "") for row in selected),
    }


def classify_availability(injury: Any, config: dict[str, Any]) -> str | None:
    if not injury:
        return None
    expected = str((injury or {}).get("expectedReturn") or "").strip().lower()
    if not expected:
        return "unknown"
    if any(term in expected for term in config["availability"]["questionable_terms"]):
        return "questionable"
    return "unavailable"


def availability_snapshot(
    squad_rows: list[dict[str, Any]],
    grades_by_player: dict[int, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    players: list[dict[str, Any]] = []
    for row in squad_rows:
        status = classify_availability(row.get("injury"), config)
        if status is None:
            continue
        grade = grades_by_player.get(int(row["player_id"]))
        players.append(
            {
                "player_id": int(row["player_id"]),
                "player": row.get("player"),
                "position": row.get("position"),
                "status": status,
                "expected_return": (row.get("injury") or {}).get("expectedReturn"),
                "alpha_ability_z": grade.get("alpha_ability_z") if grade else None,
                "alpha_position": grade.get("scoring_position") if grade else None,
            }
        )
    players.sort(
        key=lambda item: (
            {"unavailable": 0, "questionable": 1, "unknown": 2}[item["status"]],
            -(float(item["alpha_ability_z"]) if item["alpha_ability_z"] is not None else -999),
            str(item.get("player") or ""),
        )
    )
    return {
        "unavailable": sum(item["status"] == "unavailable" for item in players),
        "questionable": sum(item["status"] == "questionable" for item in players),
        "unknown": sum(item["status"] == "unknown" for item in players),
        "players": players,
        "form_score_modifier": None,
        "modifier_note": config["availability"]["note"],
    }


def _standardise_team_values(
    forms: list[dict[str, Any]], field: str, confidence_field: str, cap: float
) -> dict[str, Any]:
    values = [float(row[field]) for row in forms if row.get(field) is not None]
    scale = _sample_scale(values)
    if scale is None:
        for row in forms:
            row[field.replace("_raw", "")] = None
        return {"reference_teams": len(values), "mean": None, "sample_sd": None}
    mean, spread = scale
    output_field = field.replace("_raw", "")
    for row in forms:
        value = row.get(field)
        if value is None:
            row[output_field] = None
            continue
        standardised = max(-cap, min(cap, (float(value) - mean) / spread))
        row[output_field] = round(standardised * float(row[confidence_field]), 4)
    return {
        "reference_teams": len(values),
        "mean": round(mean, 6),
        "sample_sd": round(spread, 6),
    }


def build_club_forms(
    observations: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    squads: list[dict[str, Any]],
    grades: list[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        by_team[int(row["team_id"])].append(row)
    squads_by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in squads:
        squads_by_team[int(row["team_id"])].append(row)
    grades_by_player = {int(row["player_id"]): row for row in grades}

    forms: list[dict[str, Any]] = []
    for team in teams:
        team_id = int(team["team_id"])
        matches = by_team.get(team_id, [])
        overall = aggregate_form(matches, config)
        record = {
            "form_version": config["version"],
            "as_of": as_of.isoformat(),
            "team_id": team_id,
            "team": team.get("name"),
            "premier_league_2026_27": bool(team.get("premier_league_2026_27")),
            "ucl_status": team.get("ucl_status"),
            "attack_z_raw": overall["attack_z_raw"],
            "defense_z_raw": overall["defense_z_raw"],
            "attack_confidence": overall["attack_confidence"],
            "defense_confidence": overall["defense_confidence"],
            "evidence": {key: value for key, value in overall.items() if not key.endswith("_z_raw")},
            "breakdown": {
                "previous_competitive": aggregate_form(
                    matches,
                    config,
                    lambda row: scope_class(row, config) == "previous_competitive",
                ),
                "current_competitive": aggregate_form(
                    matches,
                    config,
                    lambda row: scope_class(row, config) == "current_competitive",
                ),
                "preseason": aggregate_form(
                    matches, config, lambda row: scope_class(row, config) == "preseason"
                ),
                "home_competitive": aggregate_form(
                    matches,
                    config,
                    lambda row: row.get("venue") == "home"
                    and scope_class(row, config) != "preseason",
                ),
                "away_competitive": aggregate_form(
                    matches,
                    config,
                    lambda row: row.get("venue") == "away"
                    and scope_class(row, config) != "preseason",
                ),
            },
            "availability": availability_snapshot(
                squads_by_team.get(team_id, []), grades_by_player, config
            ),
            "quality_flags": [],
        }
        if not matches:
            record["quality_flags"].append("no_match_history")
        if overall["metric_coverage"] < 0.75:
            record["quality_flags"].append("partial_match_detail")
        if overall["preseason_weight_capped"]:
            record["quality_flags"].append("preseason_weight_capped")
        forms.append(record)

    cap = float(config["normalisation"]["z_cap"])
    reference = {
        "attack": _standardise_team_values(forms, "attack_z_raw", "attack_confidence", cap),
        "defense": _standardise_team_values(forms, "defense_z_raw", "defense_confidence", cap),
    }
    for row in forms:
        present = [row.get("attack_z"), row.get("defense_z")]
        row["overall_form_z"] = (
            round(statistics.mean(float(value) for value in present if value is not None), 4)
            if any(value is not None for value in present)
            else None
        )
        if statistics.mean([row["attack_confidence"], row["defense_confidence"]]) < 0.5:
            row["quality_flags"].append("low_form_confidence")
        row["quality_flags"] = sorted(set(row["quality_flags"]))
    forms.sort(key=lambda row: (row.get("team") or "", row["team_id"]))
    return forms, reference
