"""Zero-weight lineup, rotation, and rest risk diagnostics."""

from __future__ import annotations

from typing import Any


VERSION = "clubalpha_prematch_load_audit_v1"


def classify_load_risk(row: dict[str, Any]) -> tuple[str, list[str]]:
    flags = []
    if row.get("pending_preleague_fixture"):
        flags.append("pending_preleague_fixture")
    if float(row.get("rest_days") or 99.0) < 4.0:
        flags.append("short_rest")
    if (
        float(row.get("rest_days") or 99.0) < 5.0
        and float(row.get("projected_xi_latest_match_load_share") or 0.0) >= 2.0 / 3.0
    ):
        flags.append("heavy_projected_xi_load")
    if row.get("competition_switch") and int(row.get("projected_xi_starter_overlap") or 0) < 7:
        flags.append("rotated_cross_competition_lineup")
    if float(row.get("player_alpha_coverage") or 0.0) < 0.85:
        flags.append("provisional_player_alpha_coverage")
    international_180 = int(
        row.get("international_projected_xi_players_180_plus") or 0
    )
    international_270 = int(
        row.get("international_projected_xi_players_270_plus") or 0
    )
    international_recovery = row.get("international_min_recovery_days")
    if international_180 >= 4:
        flags.append("heavy_international_projected_xi_load")
    if international_270 >= 2:
        flags.append("extreme_international_projected_xi_load")
    if international_recovery is not None and float(international_recovery) < 5.0:
        flags.append("compressed_international_recovery")
    if "pending_preleague_fixture" in flags or (
        "short_rest" in flags and "heavy_projected_xi_load" in flags
    ) or (
        "compressed_international_recovery" in flags
        and (
            "heavy_international_projected_xi_load" in flags
            or "extreme_international_projected_xi_load" in flags
        )
    ):
        risk = "high"
    elif flags:
        risk = "medium"
    else:
        risk = "low"
    return risk, flags
