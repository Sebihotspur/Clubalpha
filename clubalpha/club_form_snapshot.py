"""Joined, non-blended Club Form intelligence snapshot."""

from __future__ import annotations

import statistics
from typing import Any, Iterable


SNAPSHOT_VERSION = "clubalpha_club_form_snapshot_v1"


def _unique_by_team(rows: Iterable[dict[str, Any]], label: str) -> dict[int, dict[str, Any]]:
    output: dict[int, dict[str, Any]] = {}
    for row in rows:
        team_id = int(row["team_id"])
        if team_id in output:
            raise ValueError(f"Duplicate {label} row for team_id={team_id}")
        output[team_id] = row
    return output


def _performance_section(row: dict[str, Any]) -> dict[str, Any]:
    confidence_values = [
        float(value)
        for value in (row.get("attack_confidence"), row.get("defense_confidence"))
        if value is not None
    ]
    return {
        "version": row.get("form_version"),
        "overall_form_z": row.get("overall_form_z"),
        "attack_form_z": row.get("attack_z"),
        "defense_form_z": row.get("defense_z"),
        "confidence": {
            "attack": row.get("attack_confidence"),
            "defense": row.get("defense_confidence"),
            "average": round(statistics.mean(confidence_values), 4)
            if confidence_values
            else 0.0,
        },
        "evidence": row.get("evidence"),
        "breakdown": row.get("breakdown"),
    }


def _dynamics_section(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": row.get("dynamics_version"),
        "style": row.get("style"),
        "strengths_weaknesses": row.get("strengths_weaknesses"),
        "change_state": row.get("change_state"),
    }


def _selection_section(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": row.get("selection_prior_version"),
        "shape_prior": row.get("shape_prior"),
        "expected_starting_xi_prior": row.get("expected_starting_xi_prior"),
        "players": row.get("players"),
        "evidence": row.get("evidence"),
        "decision_boundaries": row.get("decision_boundaries"),
    }


def join_club_form_snapshots(
    forms: Iterable[dict[str, Any]],
    dynamics: Iterable[dict[str, Any]],
    selection_priors: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join Club Form components without calculating another score."""

    forms_by_team = _unique_by_team(forms, "performance form")
    dynamics_by_team = _unique_by_team(dynamics, "club dynamics")
    selection_by_team = _unique_by_team(selection_priors, "squad selection prior")
    if (
        set(forms_by_team) != set(dynamics_by_team)
        or set(forms_by_team) != set(selection_by_team)
    ):
        missing_dynamics = sorted(set(forms_by_team) - set(dynamics_by_team))
        extra_dynamics = sorted(set(dynamics_by_team) - set(forms_by_team))
        missing_selection = sorted(set(forms_by_team) - set(selection_by_team))
        extra_selection = sorted(set(selection_by_team) - set(forms_by_team))
        raise ValueError(
            "Club Form component universes differ: "
            f"missing dynamics={missing_dynamics}; extra dynamics={extra_dynamics}; "
            f"missing selection={missing_selection}; extra selection={extra_selection}"
        )

    snapshots: list[dict[str, Any]] = []
    for team_id, form in forms_by_team.items():
        dynamic = dynamics_by_team[team_id]
        selection = selection_by_team[team_id]
        if (
            form.get("as_of") != dynamic.get("as_of")
            or form.get("as_of") != selection.get("as_of")
        ):
            raise ValueError(
                f"Snapshot date mismatch for team_id={team_id}: "
                f"form={form.get('as_of')} dynamics={dynamic.get('as_of')} "
                f"selection={selection.get('as_of')}"
            )
        if (
            form.get("team") != dynamic.get("team")
            or form.get("team") != selection.get("team")
        ):
            raise ValueError(
                f"Team name mismatch for team_id={team_id}: "
                f"form={form.get('team')!r} dynamics={dynamic.get('team')!r} "
                f"selection={selection.get('team')!r}"
            )

        performance = _performance_section(form)
        club_dynamics = _dynamics_section(dynamic)
        squad_selection = _selection_section(selection)
        availability = form.get("availability") or {}
        lineup_prior_ready = bool(
            (squad_selection.get("decision_boundaries") or {}).get(
                "lineup_prior_ready"
            )
        )
        blockers = [
            "fixture_not_selected",
            "fresh_team_news_not_applied",
            "expected_lineup_not_confirmed",
            "dynamics_modifiers_not_walk_forward_validated",
            "fixture_matchup_not_applied",
        ]
        if not lineup_prior_ready:
            blockers.insert(0, "squad_selection_evidence_missing")
        snapshots.append(
            {
                "snapshot_version": SNAPSHOT_VERSION,
                "as_of": form.get("as_of"),
                "team_id": team_id,
                "team": form.get("team"),
                "premier_league_2026_27": bool(form.get("premier_league_2026_27")),
                "ucl_status": form.get("ucl_status"),
                "performance_form": performance,
                "club_dynamics": club_dynamics,
                "squad_selection_prior": squad_selection,
                "availability": availability,
                "decision_boundaries": {
                    "combined_club_form_score": None,
                    "dynamics_changes_performance_score": False,
                    "availability_changes_performance_score": False,
                    "selection_prior_built": True,
                    "lineup_prior_ready": lineup_prior_ready,
                    "expected_minutes_prior_built": lineup_prior_ready,
                    "expected_minutes_locked": False,
                    "transfer_fees_used": False,
                    "fixture_specific": False,
                    "projection_ready": False,
                    "projection_blockers": blockers,
                },
                "quality_flags": {
                    "performance": form.get("quality_flags") or [],
                    "dynamics": dynamic.get("quality_flags") or [],
                    "selection": selection.get("quality_flags") or [],
                },
            }
        )
    snapshots.sort(key=lambda row: (row.get("team") or "", row["team_id"]))
    return snapshots
