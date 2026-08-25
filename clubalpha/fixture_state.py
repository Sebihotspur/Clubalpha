"""Dated fixture handoff from Clubalpha's three intelligence foundations.

Fixture State v1 deliberately stops before probabilities. It preserves the
competition expected-goal environment as the baseline and materializes the
three confidence-aware component inputs. The 60/30/10 adjustment activates only
with a frozen scale artifact trained from strictly earlier snapshots.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Any, Iterable

from clubalpha.club_form import parse_datetime
from clubalpha.historical_fixtures import aggregate_history


EXPECTED_TEAM_MINUTES = 990.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round(value: float | None, places: int = 6) -> float | None:
    return round(float(value), places) if value is not None else None


def _snapshot_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid or missing Fixture State as-of date: {value}") from exc


def validate_history_rows(
    history_rows: Iterable[dict[str, Any]], as_of: date
) -> list[dict[str, Any]]:
    """Reject historical observations that cannot prove time integrity."""

    validated: list[dict[str, Any]] = []
    for index, row in enumerate(history_rows):
        kickoff = parse_datetime(row.get("kickoff_utc"))
        if kickoff is None:
            raise ValueError(f"Historical row {index} has no valid kickoff_utc")
        if kickoff.date() > as_of:
            raise ValueError(
                f"Historical row {index} occurs after Fixture State as-of {as_of}"
            )
        if row.get("age_days") is None:
            raise ValueError(f"Historical row {index} has no age_days")
        try:
            age_days = int(row["age_days"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Historical row {index} has invalid age_days") from exc
        expected_age = (as_of - kickoff.date()).days
        if age_days < 0 or age_days != expected_age:
            raise ValueError(
                f"Historical row {index} age_days {age_days} does not match "
                f"snapshot age {expected_age}"
            )
        validated.append(row)
    return validated


def validate_scaling_artifact(
    artifact: dict[str, Any] | None,
    as_of: date,
    config: dict[str, Any],
) -> dict[str, float] | None:
    """Accept only a complete component-scale artifact trained in the past."""

    if artifact is None:
        return None
    policy = config["component_scaling"]
    if not str(artifact.get("version") or "").strip():
        raise ValueError("Component scaling artifact requires a version")
    for field in ("training_snapshot_count", "training_fixture_sides"):
        try:
            value = int(artifact.get(field))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Component scaling artifact requires positive {field}"
            ) from exc
        if value <= 0:
            raise ValueError(f"Component scaling artifact requires positive {field}")
    if artifact.get("method") != policy["method"]:
        raise ValueError(
            f"Expected component scaling method {policy['method']}, "
            f"found {artifact.get('method')}"
        )
    trained_through = _snapshot_date(artifact.get("trained_through"))
    if policy.get("require_trained_before_as_of", True) and trained_through >= as_of:
        raise ValueError(
            "Component scaling artifact must be trained strictly before Fixture State as-of"
        )
    required = set(policy["required_components"])
    supplied = artifact.get("scales") or {}
    if set(supplied) != required:
        raise ValueError(
            f"Component scale artifact requires exactly {sorted(required)}"
        )
    scales = {key: float(value) for key, value in supplied.items()}
    if any(value <= 0 for value in scales.values()):
        raise ValueError("Every component scale must be positive")
    return scales


def _pair_signal(
    attack: float | None,
    attack_confidence: float,
    opposing_defense: float | None,
    defense_confidence: float,
) -> tuple[float | None, float]:
    """Combine attack and inverted opponent defence without hiding coverage."""

    available: list[tuple[float, float]] = []
    if attack is not None and attack_confidence > 0:
        available.append((float(attack), float(attack_confidence)))
    if opposing_defense is not None and defense_confidence > 0:
        available.append((-float(opposing_defense), float(defense_confidence)))
    if not available:
        return None, 0.0
    total_confidence = sum(confidence for _, confidence in available)
    value = sum(signal * confidence for signal, confidence in available) / total_confidence
    return value, statistics.mean(confidence for _, confidence in available)


def lineup_quality(selection: dict[str, Any] | None, config: dict[str, Any]) -> dict[str, Any]:
    """Calculate expected-minute Alpha quality before and after availability.

    Players without a grade contribute a neutral zero to the common Alpha
    scale. Their minutes reduce coverage instead of inflating the average of
    the players who happen to be graded.
    """

    if not selection:
        return {
            "available": False,
            "baseline_quality_z": 0.0,
            "projected_quality_z": 0.0,
            "availability_delta_z": 0.0,
            "baseline_alpha_minute_coverage": 0.0,
            "adjusted_alpha_minute_coverage": 0.0,
            "alpha_minute_coverage": 0.0,
            "selection_evidence": 0.0,
            "selection_evidence_maturity": 0.0,
            "confidence": 0.0,
            "lineup_prior_ready": False,
            "fixture_specific": False,
            "confirmed_lineup": False,
            "quality_flags": ["missing_squad_selection_prior"],
        }

    boundaries = selection.get("decision_boundaries") or {}
    expected_minutes = _number(
        boundaries.get("expected_team_minutes"), EXPECTED_TEAM_MINUTES
    )
    if expected_minutes <= 0:
        expected_minutes = EXPECTED_TEAM_MINUTES

    baseline_numerator = 0.0
    adjusted_numerator = 0.0
    baseline_covered = 0.0
    adjusted_covered = 0.0
    for player in selection.get("players") or []:
        alpha = player.get("alpha_ability_z")
        baseline_minutes = _number(player.get("baseline_expected_minutes"))
        adjusted_minutes = _number(player.get("expected_minutes_prior"))
        if alpha is None:
            continue
        alpha_value = float(alpha)
        baseline_numerator += baseline_minutes * alpha_value
        adjusted_numerator += adjusted_minutes * alpha_value
        baseline_covered += baseline_minutes
        adjusted_covered += adjusted_minutes

    baseline_quality = baseline_numerator / expected_minutes
    adjusted_quality = adjusted_numerator / expected_minutes
    baseline_coverage = min(1.0, baseline_covered / expected_minutes)
    adjusted_coverage = min(1.0, adjusted_covered / expected_minutes)
    alpha_coverage = min(baseline_coverage, adjusted_coverage)

    evidence = selection.get("evidence") or {}
    evidence_strength = _number(evidence.get("coverage_adjusted_recent_matches")) + _number(
        evidence.get("historical_prior_strength")
    )
    evidence_prior = float(config["lineup_confidence"]["evidence_prior"])
    evidence_maturity = (
        evidence_strength / (evidence_strength + evidence_prior)
        if evidence_strength > 0
        else 0.0
    )
    ready = bool(boundaries.get("lineup_prior_ready"))
    confidence = alpha_coverage * evidence_maturity if ready else 0.0

    flags = list(selection.get("quality_flags") or [])
    if not ready:
        flags.append("lineup_prior_not_ready")
    if alpha_coverage < 1.0:
        flags.append("partial_alpha_minute_coverage")
    if not boundaries.get("fixture_specific"):
        flags.append("lineup_not_fixture_specific")
    if not boundaries.get("confirmed_lineup"):
        flags.append("lineup_not_confirmed")

    return {
        "available": True,
        "baseline_quality_z": _round(baseline_quality),
        "projected_quality_z": _round(adjusted_quality),
        "availability_delta_z": _round(adjusted_quality - baseline_quality),
        "baseline_alpha_minute_coverage": _round(baseline_coverage, 4),
        "adjusted_alpha_minute_coverage": _round(adjusted_coverage, 4),
        "alpha_minute_coverage": _round(alpha_coverage, 4),
        "selection_evidence": _round(evidence_strength, 4),
        "selection_evidence_maturity": _round(evidence_maturity, 4),
        "confidence": _round(confidence, 4),
        "lineup_prior_ready": ready,
        "fixture_specific": bool(boundaries.get("fixture_specific")),
        "confirmed_lineup": bool(boundaries.get("confirmed_lineup")),
        "quality_flags": sorted(set(flags)),
    }


def form_matchup(
    attack_form: dict[str, Any] | None,
    defense_form: dict[str, Any] | None,
) -> dict[str, Any]:
    """Use released Club Form values, which already contain confidence shrinkage."""

    if not attack_form or not defense_form:
        return {
            "available": False,
            "attack_form_z": None,
            "opponent_defense_form_z": None,
            "raw_matchup_z": 0.0,
            "confidence": 0.0,
            "effective_signal_z": 0.0,
            "source_confidence_already_applied": True,
            "quality_flags": ["missing_club_form"],
        }

    attack = attack_form.get("attack_z")
    defense = defense_form.get("defense_z")
    available = attack is not None and defense is not None
    confidence = statistics.mean(
        [
            _number(attack_form.get("attack_confidence")),
            _number(defense_form.get("defense_confidence")),
        ]
    )
    matchup = float(attack) - float(defense) if available else 0.0
    flags = [
        *list(attack_form.get("quality_flags") or []),
        *list(defense_form.get("quality_flags") or []),
    ]
    if not available:
        flags.append("missing_club_form_dimension")
    return {
        "available": available,
        "attack_form_z": _round(attack),
        "opponent_defense_form_z": _round(defense),
        "raw_matchup_z": _round(matchup),
        "confidence": _round(confidence, 4),
        "effective_signal_z": _round(matchup),
        "source_confidence_already_applied": True,
        "quality_flags": sorted(set(flags)),
    }


def historical_residuals(
    historical_fixture: dict[str, Any],
    history_rows: Iterable[dict[str, Any]],
    historical_config: dict[str, Any],
    as_of: date | None = None,
    *,
    rows_validated: bool = False,
) -> dict[str, dict[str, Any]]:
    """Return side-specific venue and capped direct-matchup residuals."""

    fixture = historical_fixture["fixture"]
    snapshot_date = as_of or _snapshot_date(historical_fixture.get("as_of"))
    home_id = int(fixture["home_team_id"])
    away_id = int(fixture["away_team_id"])
    max_age = int(
        historical_config.get("recency", {}).get("team_max_age_days", 10**9)
    )
    source_rows = (
        list(history_rows)
        if rows_validated
        else validate_history_rows(history_rows, snapshot_date)
    )
    rows = [
        row
        for row in source_rows
        if int(row.get("age_days") or 0) <= max_age
        and int(row.get("team_id") or -1) in {home_id, away_id}
    ]
    home_general = aggregate_history(
        (row for row in rows if int(row["team_id"]) == home_id), historical_config
    )
    away_general = aggregate_history(
        (row for row in rows if int(row["team_id"]) == away_id), historical_config
    )
    home_venue = historical_fixture["venue_history"]["home_team_at_home"]
    away_venue = historical_fixture["venue_history"]["away_team_away"]
    direct = historical_fixture["direct_history"]
    home_direct = direct["home_team_view"]
    away_direct = direct["away_team_view"]
    direct_share = min(
        float(direct.get("signal_share") or 0.0),
        float(historical_config["direct_history"]["maximum_signal_share"]),
    )

    def side(
        venue_attack: dict[str, Any],
        venue_defense: dict[str, Any],
        general_attack: dict[str, Any],
        general_defense: dict[str, Any],
        direct_attack: dict[str, Any],
        direct_defense: dict[str, Any],
    ) -> dict[str, Any]:
        venue_signal, venue_pair_confidence = _pair_signal(
            venue_attack.get("attack_strength_z_raw"),
            _number(venue_attack.get("confidence")),
            venue_defense.get("defense_strength_z_raw"),
            _number(venue_defense.get("confidence")),
        )
        general_signal, general_pair_confidence = _pair_signal(
            general_attack.get("attack_strength_z_raw"),
            _number(general_attack.get("confidence")),
            general_defense.get("defense_strength_z_raw"),
            _number(general_defense.get("confidence")),
        )
        direct_signal, direct_pair_confidence = _pair_signal(
            direct_attack.get("attack_strength_z_raw"),
            _number(direct_attack.get("confidence")),
            direct_defense.get("defense_strength_z_raw"),
            _number(direct_defense.get("confidence")),
        )

        venue_ready = venue_signal is not None and general_signal is not None
        venue_residual = (
            float(venue_signal) - float(general_signal) if venue_ready else 0.0
        )
        venue_confidence = (
            min(venue_pair_confidence, general_pair_confidence) if venue_ready else 0.0
        )
        venue_effective = venue_residual * venue_confidence
        direct_ready = direct_signal is not None and venue_signal is not None
        direct_residual = (
            float(direct_signal) - float(venue_signal) if direct_ready else 0.0
        )
        # Direct confidence controls its blend share (capped at 15%); applying
        # it again to the residual would shrink the same evidence twice.
        effective = (1.0 - direct_share) * venue_effective + direct_share * direct_residual
        evidence_confidence = (
            (1.0 - direct_share) * venue_confidence
            + direct_share * direct_pair_confidence
        )
        flags: list[str] = []
        if not venue_ready:
            flags.append("missing_venue_or_general_history")
        if not direct_ready:
            flags.append("no_usable_direct_history")
        return {
            "available": venue_ready,
            "venue_matchup_z": _round(venue_signal),
            "general_matchup_z": _round(general_signal),
            "venue_residual_z": _round(venue_residual),
            "venue_confidence": _round(venue_confidence, 4),
            "confidence_adjusted_venue_residual_z": _round(venue_effective),
            "direct_matchup_z": _round(direct_signal),
            "direct_residual_z": _round(direct_residual),
            "direct_confidence": _round(direct_pair_confidence, 4),
            "direct_signal_share": _round(direct_share, 4),
            "maximum_direct_signal_share": float(
                historical_config["direct_history"]["maximum_signal_share"]
            ),
            "confidence": _round(evidence_confidence, 4),
            "effective_signal_z": _round(effective),
            "confidence_already_applied": True,
            "quality_flags": flags,
        }

    return {
        "home": side(
            home_venue,
            away_venue,
            home_general,
            away_general,
            home_direct,
            away_direct,
        ),
        "away": side(
            away_venue,
            home_venue,
            away_general,
            home_general,
            away_direct,
            home_direct,
        ),
    }


def build_fixture_state(
    historical_fixture: dict[str, Any],
    forms_by_team: dict[int, dict[str, Any]],
    selections_by_team: dict[int, dict[str, Any]],
    history_rows: Iterable[dict[str, Any]],
    config: dict[str, Any],
    historical_config: dict[str, Any],
    scaling_artifact: dict[str, Any] | None = None,
    *,
    history_rows_validated: bool = False,
) -> dict[str, Any]:
    """Join the three foundations into one auditable fixture state."""

    fixture = historical_fixture["fixture"]
    home_id = int(fixture["home_team_id"])
    away_id = int(fixture["away_team_id"])
    home_form = form_matchup(forms_by_team.get(home_id), forms_by_team.get(away_id))
    away_form = form_matchup(forms_by_team.get(away_id), forms_by_team.get(home_id))
    home_lineup = lineup_quality(selections_by_team.get(home_id), config)
    away_lineup = lineup_quality(selections_by_team.get(away_id), config)
    snapshot_date = _snapshot_date(historical_fixture.get("as_of"))
    history = historical_residuals(
        historical_fixture,
        history_rows,
        historical_config,
        snapshot_date,
        rows_validated=history_rows_validated,
    )
    component_scales = validate_scaling_artifact(
        scaling_artifact, snapshot_date, config
    )

    lineup_pair_ready = bool(
        home_lineup["lineup_prior_ready"] and away_lineup["lineup_prior_ready"]
    )
    home_lineup_raw = float(home_lineup["projected_quality_z"]) - float(
        away_lineup["projected_quality_z"]
    )
    away_lineup_raw = -home_lineup_raw
    home_lineup_effective = (
        float(home_lineup["projected_quality_z"]) * float(home_lineup["confidence"])
        - float(away_lineup["projected_quality_z"])
        * float(away_lineup["confidence"])
        if lineup_pair_ready
        else 0.0
    )
    away_lineup_effective = -home_lineup_effective
    lineup_pair_confidence = (
        statistics.mean(
            [float(home_lineup["confidence"]), float(away_lineup["confidence"])]
        )
        if lineup_pair_ready
        else 0.0
    )

    lineup_components = {
        "home": {
            "available": lineup_pair_ready,
            "home_team": home_lineup,
            "away_team": away_lineup,
            "raw_projected_quality_edge_z": _round(home_lineup_raw),
            "confidence": _round(lineup_pair_confidence, 4),
            "effective_signal_z": _round(home_lineup_effective),
            "team_confidence_applied_independently": True,
        },
        "away": {
            "available": lineup_pair_ready,
            "away_team": away_lineup,
            "home_team": home_lineup,
            "raw_projected_quality_edge_z": _round(away_lineup_raw),
            "confidence": _round(lineup_pair_confidence, 4),
            "effective_signal_z": _round(away_lineup_effective),
            "team_confidence_applied_independently": True,
        },
    }

    weights = config["component_weights"]

    def side_state(
        form: dict[str, Any], lineup: dict[str, Any], historical: dict[str, Any]
    ) -> dict[str, Any]:
        raw_components = {
            "club_form": float(form["effective_signal_z"]),
            "player_quality_lineup": float(lineup["effective_signal_z"]),
            "historical_residual": float(historical["effective_signal_z"]),
        }
        normalized = (
            {
                key: value / float(component_scales[key])
                for key, value in raw_components.items()
            }
            if component_scales is not None
            else None
        )
        contributions = (
            {key: float(weights[key]) * value for key, value in normalized.items()}
            if normalized is not None
            else None
        )
        confidence = sum(
            float(weights[key]) * float(value["confidence"])
            for key, value in (
                ("club_form", form),
                ("player_quality_lineup", lineup),
                ("historical_residual", historical),
            )
        )
        return {
            "components": {
                "club_form": form,
                "player_quality_lineup": lineup,
                "historical_residual": historical,
            },
            "normalized_components_z": (
                {key: _round(value) for key, value in normalized.items()}
                if normalized is not None
                else {key: None for key in raw_components}
            ),
            "weighted_contributions_z": (
                {key: _round(value) for key, value in contributions.items()}
                if contributions is not None
                else {key: None for key in raw_components}
            ),
            "fixture_signal_z": (
                _round(sum(contributions.values()))
                if contributions is not None
                else None
            ),
            "evidence_confidence": _round(confidence, 4),
        }

    home_state = side_state(home_form, lineup_components["home"], history["home"])
    away_state = side_state(away_form, lineup_components["away"], history["away"])

    baseline = historical_fixture.get("competition_baseline") or {}
    baseline_xg = baseline.get("expected_goals") or {}
    home_baseline = baseline_xg.get("home_mean")
    away_baseline = baseline_xg.get("away_mean")
    lineup_fixture_specific = bool(
        home_lineup["fixture_specific"] and away_lineup["fixture_specific"]
    )

    flags = list(historical_fixture.get("quality_flags") or [])
    flags.extend(home_form["quality_flags"])
    flags.extend(away_form["quality_flags"])
    flags.extend(home_lineup["quality_flags"])
    flags.extend(away_lineup["quality_flags"])
    flags.extend(history["home"]["quality_flags"])
    flags.extend(history["away"]["quality_flags"])
    if not baseline_xg or home_baseline is None or away_baseline is None:
        flags.append("missing_competition_xg_baseline")
    if component_scales is None:
        flags.append("component_scaling_artifact_missing")

    input_ready = bool(
        home_baseline is not None
        and away_baseline is not None
        and home_form["available"]
        and away_form["available"]
        and lineup_pair_ready
        and history["home"]["available"]
        and history["away"]["available"]
    )
    return {
        "fixture_state_version": config["version"],
        "as_of": historical_fixture["as_of"],
        "fixture": dict(fixture),
        "component_weights": dict(weights),
        "home": home_state,
        "away": away_state,
        "component_scaling": {
            "method": config["component_scaling"]["method"],
            "ready": component_scales is not None,
            "artifact_version": (
                scaling_artifact.get("version") if scaling_artifact else None
            ),
            "trained_through": (
                scaling_artifact.get("trained_through") if scaling_artifact else None
            ),
            "scales": component_scales,
        },
        "goal_model_handoff": {
            "competition_baseline": {
                "competition_family": baseline.get("competition_family"),
                "proxy_used": baseline.get("proxy_used"),
                "confidence": baseline.get("confidence"),
                "home_xg": home_baseline,
                "away_xg": away_baseline,
                "total_xg": baseline_xg.get("total_mean"),
            },
            "home_fixture_signal_z": home_state["fixture_signal_z"],
            "away_fixture_signal_z": away_state["fixture_signal_z"],
            "calibration_owned_by_separate_layer": True,
        },
        "decision_boundaries": {
            "raw_components_ready_for_scale_fitting": input_ready,
            "component_scaling_ready": component_scales is not None,
            "composite_ready": input_ready and component_scales is not None,
            "lineup_priors_complete": bool(
                home_lineup["lineup_prior_ready"] and away_lineup["lineup_prior_ready"]
            ),
            "lineups_fixture_specific": lineup_fixture_specific,
            "lineups_confirmed": bool(
                home_lineup["confirmed_lineup"] and away_lineup["confirmed_lineup"]
            ),
            **config["decision_boundaries"],
        },
        "quality_flags": sorted(set(flags)),
    }


def build_fixture_states(
    historical_fixtures: Iterable[dict[str, Any]],
    club_forms: Iterable[dict[str, Any]],
    selection_priors: Iterable[dict[str, Any]],
    history_rows: Iterable[dict[str, Any]],
    config: dict[str, Any],
    historical_config: dict[str, Any],
    historical_manifest: dict[str, Any],
    scaling_artifact: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Materialize all fixtures after validating dated source versions."""

    fixtures = list(historical_fixtures)
    forms = list(club_forms)
    selections = list(selection_priors)
    scored_rows = list(history_rows)
    weights = config.get("component_weights") or {}
    required_weights = {
        "club_form",
        "player_quality_lineup",
        "historical_residual",
    }
    if set(weights) != required_weights or any(float(value) < 0 for value in weights.values()):
        raise ValueError("Fixture State requires three non-negative component weights")
    if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
        raise ValueError("Fixture State component weights must sum to 1.0")
    dated_rows = [*fixtures, *forms, *selections]
    if any(row.get("as_of") is None for row in dated_rows):
        raise ValueError("Every Fixture State source row must carry an as-of date")
    dates = {str(row.get("as_of")) for row in dated_rows}
    if len(dates) != 1:
        raise ValueError(f"Fixture State inputs use different as-of dates: {sorted(dates)}")
    as_of = _snapshot_date(next(iter(dates)))

    expected = config.get("source_versions") or {}
    version_fields = (
        (fixtures, "historical_fixtures_version", "historical_fixtures"),
        (forms, "form_version", "club_form"),
        (selections, "selection_prior_version", "squad_selection_prior"),
    )
    for rows, field, source in version_fields:
        versions = {str(row.get(field)) for row in rows}
        if len(versions) > 1:
            raise ValueError(f"Mixed {source} versions: {sorted(versions)}")
        wanted = expected.get(source)
        if wanted and versions and versions != {wanted}:
            raise ValueError(
                f"Expected {source} version {wanted}, found {sorted(versions)}"
            )

    expected_history_version = expected.get("historical_fixtures")
    if historical_config.get("version") != expected_history_version:
        raise ValueError(
            "Historical Fixtures config version does not match Fixture State source version"
        )
    if historical_manifest.get("historical_fixtures_version") != expected_history_version:
        raise ValueError(
            "Historical Fixtures manifest version does not match Fixture State source version"
        )
    if historical_manifest.get("as_of") != as_of.isoformat():
        raise ValueError("Historical Fixtures manifest as-of does not match Fixture State")
    manifest_outputs = historical_manifest.get("outputs") or {}
    if manifest_outputs.get("fixtures") != len(fixtures):
        raise ValueError("Historical Fixtures manifest fixture count does not match rows")
    if manifest_outputs.get("historical_team_match_rows") != len(scored_rows):
        raise ValueError("Historical Fixtures manifest history-row count does not match rows")
    scored_rows = validate_history_rows(scored_rows, as_of)
    validate_scaling_artifact(scaling_artifact, as_of, config)

    def index_unique(rows: list[dict[str, Any]], source: str) -> dict[int, dict[str, Any]]:
        output: dict[int, dict[str, Any]] = {}
        for row in rows:
            team_id = int(row["team_id"])
            if team_id in output:
                raise ValueError(f"Duplicate {source} row for team {team_id}")
            output[team_id] = row
        return output

    forms_by_team = index_unique(forms, "club form")
    selections_by_team = index_unique(selections, "squad selection prior")
    return [
        build_fixture_state(
            fixture,
            forms_by_team,
            selections_by_team,
            scored_rows,
            config,
            historical_config,
            scaling_artifact,
            history_rows_validated=True,
        )
        for fixture in fixtures
    ]
