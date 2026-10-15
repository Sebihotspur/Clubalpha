#!/usr/bin/env python3
"""Audit actual minutes, rest, and cup rotation before a league slate."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    flatten_match_player_stats,
    normalize_fixture,
    team_fixtures,
)
from clubalpha.prematch_load import VERSION, classify_load_risk  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def kickoff(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--alpha", type=Path, required=True)
    parser.add_argument(
        "--cache-dir", type=Path, default=ROOT / "data/cache/fotmob"
    )
    parser.add_argument(
        "--international-summary",
        type=Path,
        default=(
            ROOT
            / "data/processed/international_current/player_window_summary.jsonl"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    alpha = load_json(args.alpha)
    international_by_player = {
        int(row["player_id"]): row for row in load_jsonl(args.international_summary)
    }
    client = FotMobClient(args.cache_dir, refresh=False)
    output = []
    for club in alpha["clubs"]:
        next_fixture = club["next_fixture"]
        next_kickoff = kickoff(next_fixture["kickoff_utc"])
        fixtures = []
        for source in team_fixtures(client.team(int(club["team_id"]))):
            row = normalize_fixture(source, source_scope="prematch_load_audit")
            day = str(row.get("kickoff_utc") or "")[:10]
            if row.get("cancelled") or not day or day < "2026-07-01":
                continue
            fixtures.append(row)
        completed = [
            row
            for row in fixtures
            if row.get("finished") and str(row["kickoff_utc"])[:10] <= args.as_of
        ]
        if not completed:
            continue
        latest = max(completed, key=lambda row: row["kickoff_utc"])
        future_before_league = [
            row
            for row in fixtures
            if not row.get("finished")
            and args.as_of < str(row["kickoff_utc"])[:10]
            and kickoff(row["kickoff_utc"]) < next_kickoff
        ]
        player_rows = [
            row
            for row in flatten_match_player_stats(
                client.match(int(latest["match_id"])), latest
            )
            if int(row.get("team_id") or -1) == int(club["team_id"])
        ]
        projected_ids = {int(row["player_id"]) for row in club["expected_xi"]}
        projected_names = {
            int(row["player_id"]): row["player"] for row in club["expected_xi"]
        }
        actual_starters = {
            int(row["player_id"]) for row in player_rows if row.get("is_starter")
        }
        projected_minutes = 0.0
        for row in player_rows:
            if int(row["player_id"]) not in projected_ids:
                continue
            projected_minutes += float(
                ((row.get("metrics") or {}).get("minutes_played") or {}).get("value")
                or 0.0
            )
        pending = min(future_before_league, key=lambda row: row["kickoff_utc"]) if future_before_league else None
        international_rows = [
            international_by_player[player_id]
            for player_id in sorted(projected_ids)
            if player_id in international_by_player
        ]
        international_minutes = sum(
            float(row.get("minutes") or 0.0) for row in international_rows
        )
        international_latest = max(
            (
                row.get("last_kickoff_utc")
                for row in international_rows
                if row.get("last_kickoff_utc")
            ),
            default=None,
        )
        international_recovery = (
            (next_kickoff - kickoff(international_latest)).total_seconds() / 86400.0
            if international_latest
            else None
        )
        international_180 = sum(
            float(row.get("minutes") or 0.0) >= 180.0
            for row in international_rows
        )
        international_270 = sum(
            float(row.get("minutes") or 0.0) >= 270.0
            for row in international_rows
        )
        result = {
            "team_id": int(club["team_id"]),
            "team": club["team"],
            "next_fixture": next_fixture,
            "latest_completed_match": {
                "match_id": int(latest["match_id"]),
                "kickoff_utc": latest["kickoff_utc"],
                "competition_id": latest.get("competition_id"),
                "competition": latest.get("competition"),
                "opponent": (
                    latest["away_team"]
                    if int(latest["home_team_id"]) == int(club["team_id"])
                    else latest["home_team"]
                ),
                "score": latest.get("score"),
            },
            "rest_days": round(
                (next_kickoff - kickoff(latest["kickoff_utc"])).total_seconds()
                / 86400.0,
                3,
            ),
            "competition_switch": int(latest.get("competition_id") or -1) != 47,
            "projected_xi_starter_overlap": len(projected_ids & actual_starters),
            "projected_xi_latest_match_minutes": round(projected_minutes, 1),
            "projected_xi_latest_match_load_share": round(projected_minutes / 990.0, 4),
            "player_alpha_coverage": float(
                club["alpha"]["overall_alpha_ability"]["coverage"]
            ),
            "international_projected_xi_total_minutes": round(
                international_minutes, 1
            ),
            "international_projected_xi_players_180_plus": international_180,
            "international_projected_xi_players_270_plus": international_270,
            "international_min_recovery_days": (
                round(international_recovery, 3)
                if international_recovery is not None
                else None
            ),
            "international_window": {
                "source": str(args.international_summary),
                "projected_xi_players_with_appearances": len(international_rows),
                "projected_xi_total_minutes": round(international_minutes, 1),
                "projected_xi_players_180_plus": international_180,
                "projected_xi_players_270_plus": international_270,
                "latest_kickoff_utc": international_latest,
                "minimum_recovery_days": (
                    round(international_recovery, 3)
                    if international_recovery is not None
                    else None
                ),
                "players": [
                    {
                        "player_id": int(row["player_id"]),
                        "player": projected_names[int(row["player_id"])],
                        "minutes": row.get("minutes"),
                        "appearances": row.get("appearances"),
                        "goals": (row.get("totals") or {}).get("goals"),
                        "assists": (row.get("totals") or {}).get("assists"),
                        "chances_created": (row.get("totals") or {}).get(
                            "chances_created"
                        ),
                        "last_kickoff_utc": row.get("last_kickoff_utc"),
                    }
                    for row in sorted(
                        international_rows,
                        key=lambda item: (
                            -float(item.get("minutes") or 0.0),
                            str(item.get("player") or ""),
                        ),
                    )
                ],
            },
            "pending_preleague_fixture": (
                {
                    "match_id": int(pending["match_id"]),
                    "kickoff_utc": pending["kickoff_utc"],
                    "competition_id": pending.get("competition_id"),
                    "competition": pending.get("competition"),
                }
                if pending
                else None
            ),
        }
        risk, flags = classify_load_risk(result)
        result["risk"] = risk
        result["flags"] = flags
        output.append(result)
    payload = {
        "version": VERSION,
        "status": "research_diagnostic_zero_probability_weight",
        "as_of": args.as_of,
        "teams": sorted(output, key=lambda row: row["team"]),
        "decision_boundaries": {
            "changes_projected_xi": False,
            "changes_player_alpha": False,
            "changes_probabilities": False,
            "capital_deployment_ready": False,
            "international_evidence_probability_weight": 0,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve().relative_to(ROOT)),
                "teams": len(output),
                "risk_counts": {
                    key: sum(row["risk"] == key for row in output)
                    for key in ("low", "medium", "high")
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
