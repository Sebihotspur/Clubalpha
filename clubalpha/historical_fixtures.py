"""Clubalpha Historical Fixtures.

This layer turns normalized competitive match records into conservative,
fixture-specific historical context. It does not predict a result and it does
not use market prices. Direct head-to-head evidence is deliberately capped so
that a small sample cannot overpower broader venue history.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable

from clubalpha.club_form import parse_datetime


def _mean(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return statistics.mean(present) if present else None


def _weighted_mean(
    rows: Iterable[dict[str, Any]], field: str
) -> tuple[float | None, float]:
    available = [
        (float(row[field]), float(row["history_weight"]))
        for row in rows
        if row.get(field) is not None and float(row.get("history_weight") or 0.0) > 0
    ]
    evidence = sum(weight for _, weight in available)
    if evidence <= 0:
        return None, 0.0
    return sum(value * weight for value, weight in available) / evidence, evidence


def dedupe_team_match_rows(
    *row_sets: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one normalized observation for each team in each match."""

    by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for rows in row_sets:
        for row in rows:
            if row.get("match_id") is None or row.get("team_id") is None:
                continue
            key = (int(row["match_id"]), int(row["team_id"]))
            current = by_key.get(key)
            if current is None or (
                not current.get("cache_detail_available")
                and row.get("cache_detail_available")
            ):
                by_key[key] = dict(row)
    return sorted(
        by_key.values(),
        key=lambda row: (str(row.get("kickoff_utc") or ""), int(row["match_id"]), int(row["team_id"])),
    )


def select_target_fixtures(
    fixtures: Iterable[dict[str, Any]], as_of: date, config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Select unplayed fixtures inside the dated intelligence horizon."""

    scopes = set(config["target_fixtures"]["source_scopes"])
    horizon = as_of + timedelta(days=int(config["target_fixtures"]["horizon_days"]))
    selected: dict[int, dict[str, Any]] = {}
    for fixture in fixtures:
        kickoff = parse_datetime(fixture.get("kickoff_utc"))
        if (
            kickoff is None
            or kickoff.date() <= as_of
            or kickoff.date() > horizon
            or fixture.get("cancelled")
            or fixture.get("finished")
            or str(fixture.get("source_scope")) not in scopes
        ):
            continue
        selected[int(fixture["match_id"])] = dict(fixture)
    return sorted(
        selected.values(),
        key=lambda row: (str(row.get("kickoff_utc") or ""), int(row["match_id"])),
    )


def normalisation_group(
    row: dict[str, Any], config: dict[str, Any] | None = None
) -> str:
    scope = str(row.get("source_scope") or "")
    season = str(row.get("season") or "")
    separate_seasons = bool(
        (config or {}).get("normalisation", {}).get("separate_seasons")
    )
    if scope.startswith("champions_league"):
        base = "champions_league"
    else:
        base = f"competition:{row.get('competition_id') or row.get('competition') or 'unknown'}"
    return f"{base}:season:{season}" if separate_seasons and season else base


def _sample_scale(values: list[float]) -> tuple[float, float] | None:
    if len(values) < 2:
        return None
    spread = statistics.stdev(values)
    if spread <= 1e-12:
        return None
    return statistics.mean(values), spread


def fit_metric_scales(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    metrics = list(config["performance_metrics"])
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    global_values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        group = normalisation_group(row, config)
        for metric in metrics:
            value = row.get(f"{metric}_for")
            if value is not None:
                grouped[group][metric].append(float(value))
                global_values[metric].append(float(value))

    minimum = int(config["normalisation"]["minimum_peer_values"])
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for group, values_by_metric in grouped.items():
        output[group] = {}
        for metric in metrics:
            values = values_by_metric.get(metric, [])
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
                "peer_values": len(values),
                "source": source,
            }
    return output


def league_strength_offset(
    row: dict[str, Any], league_policy: dict[str, Any]
) -> tuple[str, float]:
    scope = str(row.get("source_scope") or "")
    if scope.startswith("champions_league"):
        key = "Champions League"
    else:
        key = league_policy["fotmob_league_id_to_key"].get(
            str(row.get("competition_id")), league_policy["default_key"]
        )
    return key, float(league_policy["offsets"].get(key, league_policy["default_offset"]))


def score_history_rows(
    rows: Iterable[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
    league_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Standardize historical performance and apply the locked league ladder."""

    eligible: list[dict[str, Any]] = []
    for source in dedupe_team_match_rows(rows):
        kickoff = parse_datetime(source.get("kickoff_utc"))
        if kickoff is None or kickoff.date() > as_of:
            continue
        eligible.append(dict(source))

    scales = fit_metric_scales(eligible, config)
    metrics = list(config["performance_metrics"])
    cap = float(config["normalisation"]["z_cap"])
    recency = config["recency"]
    team_half_life = float(
        recency.get("team_half_life_days", recency.get("half_life_days", 180))
    )
    direct_half_life = float(recency.get("direct_half_life_days", team_half_life))
    baseline_half_life = float(
        recency.get("competition_baseline_half_life_days", team_half_life)
    )
    scored: list[dict[str, Any]] = []
    for row in eligible:
        group = normalisation_group(row, config)
        metric_z: dict[str, dict[str, float | None]] = {}
        for metric in metrics:
            scale = (scales.get(group) or {}).get(metric)
            attack = None
            defense = None
            if scale:
                value_for = row.get(f"{metric}_for")
                value_against = row.get(f"{metric}_against")
                if value_for is not None:
                    attack = max(
                        -cap,
                        min(cap, (float(value_for) - scale["mean"]) / scale["sample_sd"]),
                    )
                if value_against is not None:
                    defense = max(
                        -cap,
                        min(cap, -(float(value_against) - scale["mean"]) / scale["sample_sd"]),
                    )
            metric_z[metric] = {"attack_z": attack, "defense_z": defense}

        league_key, offset = league_strength_offset(row, league_policy)
        attack_raw = _mean(value["attack_z"] for value in metric_z.values())
        defense_raw = _mean(value["defense_z"] for value in metric_z.values())
        kickoff = parse_datetime(row.get("kickoff_utc"))
        age_days = max(0, (as_of - kickoff.date()).days) if kickoff else 0
        source_weight = float(
            config["source_weights"].get(
                str(row.get("source_scope")), config["source_weights"]["default"]
            )
        )
        row.update(
            {
                "normalisation_group": group,
                "metric_z": metric_z,
                "league_strength_key": league_key,
                "league_strength_offset_z": offset,
                "attack_strength_z": (
                    round(max(-cap, min(cap, attack_raw + offset)), 6)
                    if attack_raw is not None
                    else None
                ),
                "defense_strength_z": (
                    round(max(-cap, min(cap, defense_raw + offset)), 6)
                    if defense_raw is not None
                    else None
                ),
                "metric_coverage": round(
                    statistics.mean(
                        [
                            sum(value[side] is not None for value in metric_z.values())
                            / len(metrics)
                            for side in ("attack_z", "defense_z")
                        ]
                    ),
                    4,
                ),
                "age_days": age_days,
                "recency_weight": round(0.5 ** (age_days / team_half_life), 8),
                "direct_recency_weight": round(
                    0.5 ** (age_days / direct_half_life), 8
                ),
                "competition_baseline_recency_weight": round(
                    0.5 ** (age_days / baseline_half_life), 8
                ),
                "source_weight": source_weight,
            }
        )
        row["history_weight"] = round(
            row["recency_weight"] * source_weight * row["metric_coverage"], 8
        )
        row["direct_history_weight"] = round(
            row["direct_recency_weight"]
            * source_weight
            * row["metric_coverage"],
            8,
        )
        row["competition_baseline_weight"] = round(
            row["competition_baseline_recency_weight"]
            * source_weight
            * row["metric_coverage"],
            8,
        )
        scored.append(row)
    return scored, scales


def aggregate_history(
    rows: Iterable[dict[str, Any]], config: dict[str, Any], *, direct: bool = False
) -> dict[str, Any]:
    selected = list(rows)
    if direct:
        multiplier = float(config["direct_history"]["same_venue_multiplier"])
        selected = [
            {
                **row,
                "history_weight": float(
                    row.get("direct_history_weight", row["history_weight"])
                )
                * (multiplier if row.get("venue") == row.get("target_venue") else 1.0),
            }
            for row in selected
        ]

    prior = float(
        config["direct_history" if direct else "venue_history"]["prior_weighted_matches"]
    )
    evidence = sum(float(row.get("history_weight") or 0.0) for row in selected)
    confidence = evidence / (evidence + prior) if evidence > 0 else 0.0

    fields = [
        "attack_strength_z",
        "defense_strength_z",
        "goals_for",
        "goals_against",
        "expected_goals_for",
        "expected_goals_against",
        "shots_on_target_for",
        "shots_on_target_against",
        "big_chances_for",
        "big_chances_against",
    ]
    weighted: dict[str, float | None] = {}
    metric_evidence: dict[str, float] = {}
    for field in fields:
        value, field_evidence = _weighted_mean(selected, field)
        weighted[field] = round(value, 4) if value is not None else None
        metric_evidence[field] = round(field_evidence, 4)

    rate_rows = [row for row in selected if row.get("goals_for") is not None and row.get("goals_against") is not None]
    rate_evidence = sum(float(row["history_weight"]) for row in rate_rows)

    def rate(predicate: Any) -> float | None:
        if rate_evidence <= 0:
            return None
        return sum(float(row["history_weight"]) for row in rate_rows if predicate(row)) / rate_evidence

    latest = max((str(row.get("kickoff_utc") or "") for row in selected), default=None)
    return {
        "matches": len(selected),
        "weighted_match_evidence": round(evidence, 4),
        "confidence": round(confidence, 4),
        "latest_match_utc": latest,
        "same_venue_matches": sum(row.get("venue") == row.get("target_venue") for row in selected)
        if direct
        else len(selected),
        "attack_strength_z_raw": weighted["attack_strength_z"],
        "defense_strength_z_raw": weighted["defense_strength_z"],
        "attack_strength_z": (
            round(float(weighted["attack_strength_z"]) * confidence, 4)
            if weighted["attack_strength_z"] is not None
            else None
        ),
        "defense_strength_z": (
            round(float(weighted["defense_strength_z"]) * confidence, 4)
            if weighted["defense_strength_z"] is not None
            else None
        ),
        "weighted_averages": {
            key: value for key, value in weighted.items() if key not in {"attack_strength_z", "defense_strength_z"}
        },
        "empirical_rates": {
            "win": round(value, 4) if (value := rate(lambda row: float(row["goals_for"]) > float(row["goals_against"]))) is not None else None,
            "draw": round(value, 4) if (value := rate(lambda row: float(row["goals_for"]) == float(row["goals_against"]))) is not None else None,
            "loss": round(value, 4) if (value := rate(lambda row: float(row["goals_for"]) < float(row["goals_against"]))) is not None else None,
            "over_2_5": round(value, 4) if (value := rate(lambda row: float(row["goals_for"]) + float(row["goals_against"]) > 2.5)) is not None else None,
            "btts": round(value, 4) if (value := rate(lambda row: float(row["goals_for"]) > 0 and float(row["goals_against"]) > 0)) is not None else None,
        },
        "metric_evidence": metric_evidence,
    }


def _competition_family(row: dict[str, Any]) -> str | None:
    scope = str(row.get("source_scope") or "")
    if scope.startswith("champions_league"):
        return "champions_league"
    if int(row.get("competition_id") or 0) == 47:
        return "premier_league"
    return None


def _weighted_variance(values: list[tuple[float, float]]) -> float | None:
    evidence = sum(weight for _, weight in values)
    if evidence <= 0:
        return None
    mean = sum(value * weight for value, weight in values) / evidence
    return sum(weight * (value - mean) ** 2 for value, weight in values) / evidence


def _weighted_covariance(
    pairs: list[tuple[float, float, float]],
) -> float | None:
    evidence = sum(weight for _, _, weight in pairs)
    if evidence <= 0:
        return None
    left_mean = sum(left * weight for left, _, weight in pairs) / evidence
    right_mean = sum(right * weight for _, right, weight in pairs) / evidence
    return (
        sum(
            weight * (left - left_mean) * (right - right_mean)
            for left, right, weight in pairs
        )
        / evidence
    )


def aggregate_competition_baseline(
    fixture: dict[str, Any], rows: Iterable[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any] | None:
    """Estimate slow-moving score distributions for later simulation work."""

    policy = config.get("competition_baseline") or {}
    if not policy.get("enabled"):
        return None
    family = _competition_family(fixture)
    if family is None:
        return None
    selected = [
        {
            **row,
            "history_weight": float(
                row.get("competition_baseline_weight", row.get("history_weight") or 0.0)
            ),
        }
        for row in rows
        if _competition_family(row) == family and row.get("venue") == "home"
    ]
    if not selected:
        return None

    evidence = sum(float(row["history_weight"]) for row in selected)
    prior = float(policy["prior_weighted_matches"])
    confidence = evidence / (evidence + prior) if evidence > 0 else 0.0

    def mean(field: str) -> float | None:
        value, _ = _weighted_mean(selected, field)
        return round(value, 4) if value is not None else None

    goal_rows = [
        row
        for row in selected
        if row.get("goals_for") is not None and row.get("goals_against") is not None
    ]
    goal_pairs = [
        (
            float(row["goals_for"]),
            float(row["goals_against"]),
            float(row["history_weight"]),
        )
        for row in goal_rows
    ]
    total_goals = [
        (home + away, weight) for home, away, weight in goal_pairs
    ]
    xg_rows = [
        row
        for row in selected
        if row.get("expected_goals_for") is not None
        and row.get("expected_goals_against") is not None
    ]
    xg_pairs = [
        (
            float(row["expected_goals_for"]),
            float(row["expected_goals_against"]),
            float(row["history_weight"]),
        )
        for row in xg_rows
    ]

    def rate(predicate: Any) -> float | None:
        rate_evidence = sum(weight for _, _, weight in goal_pairs)
        if rate_evidence <= 0:
            return None
        value = sum(
            weight for home, away, weight in goal_pairs if predicate(home, away)
        ) / rate_evidence
        return round(value, 4)

    home_goals = mean("goals_for")
    away_goals = mean("goals_against")
    home_xg = mean("expected_goals_for")
    away_xg = mean("expected_goals_against")
    return {
        "competition_family": family,
        "target_competition": fixture.get("competition"),
        "proxy_used": family == "champions_league"
        and str(fixture.get("competition")) != "Champions League",
        "matches": len(selected),
        "seasons": sorted({str(row.get("season") or "current") for row in selected}),
        "weighted_match_evidence": round(evidence, 4),
        "confidence": round(confidence, 4),
        "half_life_days": float(
            config["recency"].get(
                "competition_baseline_half_life_days",
                config["recency"].get("half_life_days", 180),
            )
        ),
        "goals": {
            "home_mean": home_goals,
            "away_mean": away_goals,
            "total_mean": (
                round(float(home_goals) + float(away_goals), 4)
                if home_goals is not None and away_goals is not None
                else None
            ),
            "home_advantage_mean": (
                round(float(home_goals) - float(away_goals), 4)
                if home_goals is not None and away_goals is not None
                else None
            ),
            "total_variance": (
                round(value, 4) if (value := _weighted_variance(total_goals)) is not None else None
            ),
            "home_away_covariance": (
                round(value, 4)
                if (value := _weighted_covariance(goal_pairs)) is not None
                else None
            ),
        },
        "expected_goals": {
            "home_mean": home_xg,
            "away_mean": away_xg,
            "total_mean": (
                round(float(home_xg) + float(away_xg), 4)
                if home_xg is not None and away_xg is not None
                else None
            ),
            "total_variance": (
                round(value, 4)
                if (
                    value := _weighted_variance(
                        [(home + away, weight) for home, away, weight in xg_pairs]
                    )
                )
                is not None
                else None
            ),
        },
        "empirical_rates": {
            "home_win": rate(lambda home, away: home > away),
            "draw": rate(lambda home, away: home == away),
            "away_win": rate(lambda home, away: home < away),
            "over_2_5": rate(lambda home, away: home + away > 2.5),
            "btts": rate(lambda home, away: home > 0 and away > 0),
        },
    }


def _confidence_weighted_mean(items: Iterable[tuple[float | None, float]]) -> tuple[float | None, float]:
    available = [(float(value), float(confidence)) for value, confidence in items if value is not None and confidence > 0]
    if not available:
        return None, 0.0
    total = sum(confidence for _, confidence in available)
    return sum(value * confidence for value, confidence in available) / total, statistics.mean(
        confidence for _, confidence in available
    )


def _blend_optional(left: float | None, right: float | None) -> float | None:
    return _mean([left, right])


def _direct_meetings(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    meetings = []
    for row in sorted(rows, key=lambda item: str(item.get("kickoff_utc") or ""), reverse=True)[:limit]:
        meetings.append(
            {
                "match_id": row["match_id"],
                "kickoff_utc": row.get("kickoff_utc"),
                "competition": row.get("competition"),
                "venue": row.get("venue"),
                "goals_for": row.get("goals_for"),
                "goals_against": row.get("goals_against"),
                "expected_goals_for": row.get("expected_goals_for"),
                "expected_goals_against": row.get("expected_goals_against"),
            }
        )
    return meetings


def build_fixture_history(
    fixture: dict[str, Any],
    history_rows: list[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
) -> dict[str, Any]:
    home_id = int(fixture["home_team_id"])
    away_id = int(fixture["away_team_id"])
    recency = config.get("recency") or {}
    team_max_age = int(recency.get("team_max_age_days", 10**9))
    direct_max_age = int(recency.get("direct_max_age_days", team_max_age))
    home_rows = [
        row
        for row in history_rows
        if int(row["team_id"]) == home_id
        and row.get("venue") == "home"
        and int(row.get("age_days") or 0) <= team_max_age
    ]
    away_rows = [
        row
        for row in history_rows
        if int(row["team_id"]) == away_id
        and row.get("venue") == "away"
        and int(row.get("age_days") or 0) <= team_max_age
    ]
    home_direct_rows = [
        {**row, "target_venue": "home"}
        for row in history_rows
        if int(row["team_id"]) == home_id and int(row.get("opponent_id") or -1) == away_id
        and int(row.get("age_days") or 0) <= direct_max_age
    ]
    away_direct_rows = [
        {**row, "target_venue": "away"}
        for row in history_rows
        if int(row["team_id"]) == away_id and int(row.get("opponent_id") or -1) == home_id
        and int(row.get("age_days") or 0) <= direct_max_age
    ]

    home_context = aggregate_history(home_rows, config)
    away_context = aggregate_history(away_rows, config)
    home_direct = aggregate_history(home_direct_rows, config, direct=True)
    away_direct = aggregate_history(away_direct_rows, config, direct=True)
    competition_baseline = aggregate_competition_baseline(
        fixture, history_rows, config
    )

    home_context_z, home_pair_confidence = _confidence_weighted_mean(
        [
            (home_context["attack_strength_z_raw"], home_context["confidence"]),
            (
                -float(away_context["defense_strength_z_raw"])
                if away_context["defense_strength_z_raw"] is not None
                else None,
                away_context["confidence"],
            ),
        ]
    )
    away_context_z, away_pair_confidence = _confidence_weighted_mean(
        [
            (away_context["attack_strength_z_raw"], away_context["confidence"]),
            (
                -float(home_context["defense_strength_z_raw"])
                if home_context["defense_strength_z_raw"] is not None
                else None,
                home_context["confidence"],
            ),
        ]
    )
    if home_context_z is not None:
        home_context_z *= home_pair_confidence
    if away_context_z is not None:
        away_context_z *= away_pair_confidence

    maximum_direct_share = float(config["direct_history"]["maximum_signal_share"])
    direct_confidence = min(home_direct["confidence"], away_direct["confidence"])
    direct_share = min(maximum_direct_share, direct_confidence)

    def blend_signal(context_value: float | None, direct_raw: float | None) -> float | None:
        if context_value is None:
            return round(float(direct_raw) * direct_share, 4) if direct_raw is not None else None
        if direct_raw is None or direct_share <= 0:
            return round(context_value, 4)
        return round((1.0 - direct_share) * context_value + direct_share * float(direct_raw), 4)

    home_attack_z = blend_signal(home_context_z, home_direct["attack_strength_z_raw"])
    away_attack_z = blend_signal(away_context_z, away_direct["attack_strength_z_raw"])

    home_xg_context = _blend_optional(
        home_context["weighted_averages"]["expected_goals_for"],
        away_context["weighted_averages"]["expected_goals_against"],
    )
    away_xg_context = _blend_optional(
        away_context["weighted_averages"]["expected_goals_for"],
        home_context["weighted_averages"]["expected_goals_against"],
    )
    home_direct_xg = home_direct["weighted_averages"]["expected_goals_for"]
    away_direct_xg = away_direct["weighted_averages"]["expected_goals_for"]

    def blend_baseline(context_value: float | None, direct_value: float | None) -> float | None:
        if context_value is None:
            return round(float(direct_value), 3) if direct_value is not None else None
        if direct_value is None:
            return round(float(context_value), 3)
        return round((1.0 - direct_share) * float(context_value) + direct_share * float(direct_value), 3)

    home_xg = blend_baseline(home_xg_context, home_direct_xg)
    away_xg = blend_baseline(away_xg_context, away_direct_xg)

    def blended_rate(key: str) -> float | None:
        context_rate = _blend_optional(
            home_context["empirical_rates"][key], away_context["empirical_rates"][key]
        )
        direct_rate = _blend_optional(
            home_direct["empirical_rates"][key], away_direct["empirical_rates"][key]
        )
        if context_rate is None:
            return round(float(direct_rate), 4) if direct_rate is not None else None
        if direct_rate is None:
            return round(float(context_rate), 4)
        return round((1.0 - direct_share) * float(context_rate) + direct_share * float(direct_rate), 4)

    flags: list[str] = []
    if not home_direct_rows:
        flags.append("no_direct_head_to_head")
    elif direct_confidence < float(config["quality"]["minimum_direct_confidence"]):
        flags.append("low_direct_head_to_head_confidence")
    if home_context["confidence"] < float(config["quality"]["minimum_venue_confidence"]):
        flags.append("low_home_venue_confidence")
    if away_context["confidence"] < float(config["quality"]["minimum_venue_confidence"]):
        flags.append("low_away_venue_confidence")
    if home_xg is None or away_xg is None:
        flags.append("missing_xg_baseline")
    home_leagues = {str(row.get("league_strength_key")) for row in home_rows}
    away_leagues = {str(row.get("league_strength_key")) for row in away_rows}
    if home_leagues != away_leagues:
        flags.append("raw_xg_mixed_competition_context")
    if competition_baseline and competition_baseline["proxy_used"]:
        flags.append("competition_baseline_proxy")

    total_xg = round(home_xg + away_xg, 3) if home_xg is not None and away_xg is not None else None
    overall_confidence = statistics.mean([home_pair_confidence, away_pair_confidence])
    output = {
        "historical_fixtures_version": config["version"],
        "as_of": as_of.isoformat(),
        "fixture": {
            key: fixture.get(key)
            for key in (
                "match_id",
                "competition_id",
                "competition",
                "source_scope",
                "round",
                "kickoff_utc",
                "home_team_id",
                "home_team",
                "away_team_id",
                "away_team",
            )
        },
        "venue_history": {
            "home_team_at_home": home_context,
            "away_team_away": away_context,
        },
        "direct_history": {
            "meetings": len(home_direct_rows),
            "same_venue_meetings": sum(row.get("venue") == "home" for row in home_direct_rows),
            "confidence": round(direct_confidence, 4),
            "signal_share": round(direct_share, 4),
            "maximum_signal_share": maximum_direct_share,
            "home_team_view": home_direct,
            "away_team_view": away_direct,
            "recent_meetings_home_team_view": _direct_meetings(
                home_direct_rows, int(config["direct_history"]["recent_meetings_limit"])
            ),
        },
        "historical_signals": {
            "home_attack_z": home_attack_z,
            "away_attack_z": away_attack_z,
            "home_edge_z": (
                round(float(home_attack_z) - float(away_attack_z), 4)
                if home_attack_z is not None and away_attack_z is not None
                else None
            ),
            "total_goal_environment_z": (
                round(statistics.mean([float(home_attack_z), float(away_attack_z)]), 4)
                if home_attack_z is not None and away_attack_z is not None
                else None
            ),
            "descriptive_xg_baseline": {
                "home": home_xg,
                "away": away_xg,
                "total": total_xg,
                "league_strength_adjusted": False,
            },
            "empirical_rates": {
                "over_2_5": blended_rate("over_2_5"),
                "btts": blended_rate("btts"),
            },
            "confidence": round(overall_confidence, 4),
        },
        "decision_boundaries": {
            "descriptive_only": True,
            "probability_ready": False,
            "market_ready": False,
            "capital_deployment_ready": False,
            "direct_history_capped": True,
            "raw_xg_baseline_is_competition_adjusted": False,
        },
        "quality_flags": sorted(set(flags)),
    }
    if competition_baseline is not None:
        output["competition_baseline"] = competition_baseline
    return output


def build_historical_fixture_intelligence(
    fixtures: Iterable[dict[str, Any]],
    history_rows: Iterable[dict[str, Any]],
    as_of: date,
    config: dict[str, Any],
    league_policy: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    targets = select_target_fixtures(fixtures, as_of, config)
    scored, scales = score_history_rows(history_rows, as_of, config, league_policy)
    outputs = [build_fixture_history(fixture, scored, as_of, config) for fixture in targets]
    return outputs, scored, scales
