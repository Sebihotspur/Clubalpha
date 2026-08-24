#!/usr/bin/env python3
"""Build Club Dynamics v1 from normalized Clubalpha foundation data."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.club_dynamics import build_club_dynamics  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path, *, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
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


def build_audit(
    profiles: list[dict[str, Any]], observations: list[dict[str, Any]], scales: dict[str, Any], as_of: date, config: dict[str, Any]
) -> dict[str, Any]:
    style_axes = [item["key"] for item in config["style"]["axes"]]
    strength_axes = [item["key"] for item in config["strengths"]["axes"]]

    def extremes(path: str, axes: list[str]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for axis in axes:
            ranked = []
            for row in profiles:
                section = row["style"]["axes"] if path == "style" else row["strengths_weaknesses"]["axes"]
                value = (section.get(axis) or {}).get("z")
                if value is not None:
                    ranked.append({"team": row["team"], "team_id": row["team_id"], "z": value})
            ranked.sort(key=lambda item: float(item["z"]), reverse=True)
            output[axis] = {"high": ranked[:3], "low": list(reversed(ranked[-3:]))}
        return output

    transfer_events = [event for row in profiles for event in row["change_state"]["transfers"]["events"]]
    flags = Counter(flag for row in profiles for flag in row["quality_flags"])
    style_coverage = {
        axis: {
            "teams_with_value": sum(row["style"]["axes"][axis].get("z") is not None for row in profiles),
            "target_teams": len(profiles),
        }
        for axis in style_axes
    }
    strength_coverage = {
        axis: {
            "teams_with_value": sum(
                row["strengths_weaknesses"]["axes"][axis].get("z") is not None
                for row in profiles
            ),
            "target_teams": len(profiles),
        }
        for axis in strength_axes
    }

    def scale_summary(groups: dict[str, Any]) -> dict[str, Any]:
        values = [
            (group, axis, scale)
            for group, axes in groups.items()
            for axis, scale in axes.items()
        ]
        return {
            "groups": len(groups),
            "axis_scales": len(values),
            "competition_scales": sum(scale["source"] == "competition" for _, _, scale in values),
            "global_fallback_scales": sum(scale["source"] == "global_fallback" for _, _, scale in values),
            "global_fallbacks": [
                {"group": group, "axis": axis, "peer_rows": scale["peer_rows"]}
                for group, axis, scale in values
                if scale["source"] == "global_fallback"
            ],
        }
    examples = {
        row["team"]: {
            "style_identity": row["style"]["identity"],
            "style_shift": [
                {"axis": key, **value}
                for key, value in row["style"]["season_boundary_shift"]["axes"].items()
                if value.get("delta_raw_z") is not None
            ],
            "strengths": row["strengths_weaknesses"]["strengths"],
            "weaknesses": row["strengths_weaknesses"]["weaknesses"],
            "manager": row["change_state"]["manager"],
            "transfers": {key: row["change_state"]["transfers"][key] for key in ("incoming", "outgoing", "alpha_coverage", "net_known_alpha_z", "minutes_weighted_known_incoming_alpha_z", "incoming_integration_confidence", "incoming_integration_coverage")},
        }
        for row in profiles if row["team"] in {"Chelsea", "Arsenal", "Manchester City", "Coventry City"}
    }
    return {
        "dynamics_version": config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "counts": {
            "target_teams": len(profiles),
            "teams_with_any_style": sum(row["style"]["coverage"] > 0 for row in profiles),
            "teams_with_complete_style": sum(row["style"]["coverage"] == 1 for row in profiles),
            "teams_with_strength_profile": sum(row["strengths_weaknesses"]["coverage"] > 0 for row in profiles),
            "teams_with_current_manager": sum(row["change_state"]["manager"]["current"] is not None for row in profiles),
            "detected_manager_changes": sum(row["change_state"]["manager"]["changed_since_previous_season"] is True for row in profiles),
            "confirmed_transfer_events_in_window": len(transfer_events),
            "transfer_events_with_alpha": sum(row.get("alpha_ability_z") is not None for row in transfer_events),
            "transfer_alpha_coverage_pct": round(
                100 * sum(row.get("alpha_ability_z") is not None for row in transfer_events) / len(transfer_events), 1
            ) if transfer_events else 100.0,
            "team_match_observations": len(observations),
        },
        "coverage": {
            "style_axes": style_coverage,
            "strength_axes": strength_coverage,
        },
        "quality_flags": dict(sorted(flags.items())),
        "style_extremes": extremes("style", style_axes),
        "strength_extremes": extremes("strength", strength_axes),
        "examples": examples,
        "normalisation": {
            category: scale_summary(groups) for category, groups in scales.items()
        },
        "warnings": [
            "Style is descriptive and has no composite grade.",
            "Strengths and weaknesses are competition-relative diagnostics and do not modify Club Form v1.",
            "Cross and long-ball attempts are estimates from FotMob completions and rounded accuracy percentages.",
            "High pressing uses previous-season possessions won in the attacking third; a manager-change flag identifies when it predates the current coach.",
            "Season-boundary style shifts describe association, not manager causation, and low-confidence shifts are labelled insufficient evidence.",
            "A first run cannot calculate true squad continuity; append-only dated snapshots enable it on later pulls.",
            "Transfer fees and market values are preserved for traceability but never determine football impact.",
            "Known-only transfer Alpha totals must always be read with Alpha and integration coverage.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/club-dynamics-v1.json")
    parser.add_argument("--foundation-dir", type=Path, default=ROOT / "data/processed/foundation")
    parser.add_argument("--domestic-dir", type=Path, default=ROOT / "data/processed/domestic_history")
    parser.add_argument("--player-grades", type=Path, default=ROOT / "data/processed/player_quality_v2/player_grades.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/club_dynamics")
    parser.add_argument("--audit", type=Path, default=ROOT / "reports/club-dynamics-v1-audit.json")
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()

    config = load_json(args.config)
    foundation_coverage = load_json(args.foundation_dir / "coverage.json")
    as_of = date.fromisoformat(args.as_of or foundation_coverage["as_of"])
    print("[1/4] Load normalized club, match, and player inputs")
    teams = load_json(args.foundation_dir / "teams.json")
    snapshots = load_jsonl(args.foundation_dir / "club_snapshots.jsonl")
    managers = load_jsonl(args.foundation_dir / "manager_history.jsonl")
    transfers = load_jsonl(args.foundation_dir / "transfer_events.jsonl")
    season_stats = load_jsonl(args.foundation_dir / "season_team_stats.jsonl")
    grades = load_jsonl(args.player_grades, required=False)
    team_rows: list[dict[str, Any]] = []
    for path in (
        args.foundation_dir / "historical_match_team_stats.jsonl",
        args.foundation_dir / "current_match_team_stats.jsonl",
        args.foundation_dir / "preseason_match_team_stats.jsonl",
        args.domestic_dir / "match_team_stats.jsonl",
    ):
        team_rows.extend(load_jsonl(path, required=False))
    player_rows: list[dict[str, Any]] = []
    for path in (
        args.foundation_dir / "current_match_player_stats.jsonl",
        args.foundation_dir / "preseason_match_player_stats.jsonl",
    ):
        player_rows.extend(load_jsonl(path, required=False))

    print("[2/4] Restore append-only source snapshot history")
    snapshot_history_path = args.output_dir / "source_snapshots.jsonl"
    snapshot_history = load_jsonl(snapshot_history_path, required=False)
    snapshot_index = {
        (str(row.get("snapshot_date")), int(row["team_id"])): row for row in [*snapshot_history, *snapshots]
    }
    updated_history = sorted(snapshot_index.values(), key=lambda row: (str(row.get("snapshot_date")), int(row["team_id"])))

    print("[3/4] Build style, strengths/weaknesses, and change state")
    profiles, observations, scales = build_club_dynamics(
        team_rows, teams, snapshots, snapshot_history, managers, transfers, season_stats, grades, player_rows, as_of, config
    )

    print("[4/4] Write ignored datasets and tracked audit")
    write_jsonl(args.output_dir / "dynamic_match_observations.jsonl", observations)
    write_jsonl(args.output_dir / "club_dynamics.jsonl", profiles)
    write_jsonl(snapshot_history_path, updated_history)
    events = []
    for row in profiles:
        manager = row["change_state"]["manager"]
        events.append({
            "event_type": "manager_snapshot", "event_date": as_of.isoformat(), "team_id": row["team_id"], "team": row["team"],
            "coach": manager["current"], "changed_since_previous_season": manager["changed_since_previous_season"]
        })
        events.extend({**event, "event_type": f"transfer_{event['direction']}", "event_date": event["effective_date"]} for event in row["change_state"]["transfers"]["events"])
    events.sort(key=lambda row: (str(row.get("event_date") or ""), int(row["team_id"]), str(row.get("event_type"))))
    write_jsonl(args.output_dir / "club_events.jsonl", events)
    write_json(
        args.output_dir / "manifest.json",
        {
            "dynamics_version": config["version"], "as_of": as_of.isoformat(), "source": config["source"],
            "outputs": {"teams": len(profiles), "team_match_observations": len(observations), "events": len(events), "dated_snapshots": len(updated_history)},
            "composite_modifier_enabled": config["change_state"]["composite_modifier_enabled"]
        },
    )
    audit = build_audit(profiles, observations, scales, as_of, config)
    write_json(args.audit, audit)
    print(json.dumps(audit["counts"], indent=2))
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
