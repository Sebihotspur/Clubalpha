#!/usr/bin/env python3
"""Join Performance Form, Club Dynamics, and Availability by team."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.club_form_snapshot import (  # noqa: E402
    SNAPSHOT_VERSION,
    join_club_form_snapshots,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(materialized)


def _example(row: dict[str, Any]) -> dict[str, Any]:
    performance = row["performance_form"]
    dynamics = row["club_dynamics"]
    style = dynamics["style"] or {}
    strengths = dynamics["strengths_weaknesses"] or {}
    change = dynamics["change_state"] or {}
    transfers = change.get("transfers") or {}
    availability = row["availability"]
    declared_shifts = [
        {"axis": axis, **values}
        for axis, values in (((style.get("season_boundary_shift") or {}).get("axes")) or {}).items()
        if values.get("direction") not in (None, "insufficient evidence", "broadly stable")
    ]
    return {
        "team_id": row["team_id"],
        "performance": {
            "overall_form_z": performance["overall_form_z"],
            "attack_form_z": performance["attack_form_z"],
            "defense_form_z": performance["defense_form_z"],
            "confidence": performance["confidence"],
        },
        "style_identity": style.get("identity") or [],
        "declared_style_shifts": declared_shifts,
        "strengths": strengths.get("strengths") or [],
        "weaknesses": strengths.get("weaknesses") or [],
        "manager": change.get("manager"),
        "transfers": {
            key: transfers.get(key)
            for key in (
                "incoming",
                "outgoing",
                "alpha_coverage",
                "net_known_alpha_z",
                "minutes_weighted_known_incoming_alpha_z",
                "incoming_integration_confidence",
                "incoming_integration_coverage",
            )
        },
        "availability": {
            "unavailable": availability.get("unavailable"),
            "questionable": availability.get("questionable"),
            "unknown": availability.get("unknown"),
        },
        "quality_flags": row["quality_flags"],
        "projection_ready": row["decision_boundaries"]["projection_ready"],
    }


def build_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    examples = {row["team"]: _example(row) for row in rows if row["team"] in {
        "Chelsea",
        "Arsenal",
        "Manchester City",
        "Coventry City",
        "Shakhtar Donetsk",
    }}
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": rows[0]["as_of"] if rows else None,
        "counts": {
            "teams": len(rows),
            "teams_with_performance_form": sum(
                row["performance_form"]["overall_form_z"] is not None for row in rows
            ),
            "teams_with_style": sum(
                float((row["club_dynamics"]["style"] or {}).get("coverage") or 0) > 0
                for row in rows
            ),
            "teams_with_strengths_weaknesses": sum(
                float((row["club_dynamics"]["strengths_weaknesses"] or {}).get("coverage") or 0) > 0
                for row in rows
            ),
            "projection_ready": sum(
                row["decision_boundaries"]["projection_ready"] for row in rows
            ),
        },
        "decision_boundaries": {
            "combined_score_created": False,
            "dynamics_modifier_applied": False,
            "availability_modifier_applied": False,
            "transfer_fees_used": False,
            "fixture_specific": False,
        },
        "examples": examples,
        "next_requirements": [
            "expected starting XI",
            "expected minutes",
            "walk-forward validation of any dynamics modifier",
            "fixture-specific style matchup",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--club-form",
        type=Path,
        default=ROOT / "data/processed/club_form/club_form.jsonl",
    )
    parser.add_argument(
        "--club-dynamics",
        type=Path,
        default=ROOT / "data/processed/club_dynamics/club_dynamics.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/club_form_snapshot",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/club-form-snapshot-v1-audit.json",
    )
    args = parser.parse_args()

    print("[1/3] Load Performance Form and Club Dynamics")
    forms = load_jsonl(args.club_form)
    dynamics = load_jsonl(args.club_dynamics)
    print("[2/3] Validate and join the team universe")
    snapshots = join_club_form_snapshots(forms, dynamics)
    print("[3/3] Write ignored snapshot and tracked audit")
    count = write_jsonl(args.output_dir / "club_form_snapshot.jsonl", snapshots)
    write_json(
        args.output_dir / "manifest.json",
        {
            "snapshot_version": SNAPSHOT_VERSION,
            "as_of": snapshots[0]["as_of"] if snapshots else None,
            "inputs": {
                "club_form": str(args.club_form),
                "club_dynamics": str(args.club_dynamics),
            },
            "outputs": {"club_form_snapshot_rows": count},
            "combined_score_created": False,
        },
    )
    audit = build_audit(snapshots)
    write_json(args.audit, audit)
    print(json.dumps(audit["counts"], indent=2))
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
