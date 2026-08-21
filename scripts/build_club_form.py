#!/usr/bin/env python3
"""Build Club Form v1 from cached FotMob fixtures and match cards."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.club_form import (  # noqa: E402
    build_club_forms,
    build_match_observations,
    dedupe_fixtures,
    parse_datetime,
    score_match_observations,
)


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
    observations: list[dict[str, Any]],
    forms: list[dict[str, Any]],
    scales: dict[str, Any],
    reference: dict[str, Any],
    missing_cache: list[int],
    config: dict[str, Any],
    as_of: date,
    processed_team_rows: int,
    cache_fallback_rows: int,
) -> dict[str, Any]:
    scopes = Counter(str(row.get("source_scope")) for row in observations)
    metric_coverage: dict[str, Any] = {}
    for metric in [item["key"] for item in config["form_metrics"]]:
        present = sum(row.get(f"{metric}_for") is not None for row in observations)
        metric_coverage[metric] = {
            "team_match_rows_with_value": present,
            "team_match_rows": len(observations),
            "pct": round(100 * present / len(observations), 1) if observations else 0.0,
        }

    def leaders(field: str) -> list[dict[str, Any]]:
        ranked = sorted(
            (row for row in forms if row.get(field) is not None),
            key=lambda row: float(row[field]),
            reverse=True,
        )
        return [
            {
                "team_id": row["team_id"],
                "team": row["team"],
                field: row[field],
                "attack_form_z": row.get("attack_z"),
                "defense_form_z": row.get("defense_z"),
                "attack_confidence": row["attack_confidence"],
                "defense_confidence": row["defense_confidence"],
                "matches": row["evidence"]["matches"],
                "preseason_weight_share": row["evidence"]["preseason_weight_share"],
            }
            for row in ranked[:10]
        ]

    flags = Counter(flag for row in forms for flag in row.get("quality_flags") or [])
    availability = Counter()
    for row in forms:
        availability["unavailable"] += row["availability"]["unavailable"]
        availability["questionable"] += row["availability"]["questionable"]
        availability["unknown"] += row["availability"]["unknown"]

    competition_groups: dict[str, Any] = {}
    for group, metrics in sorted(scales.items()):
        competition_groups[group] = {
            metric: {
                "peer_rows": values["peer_rows"],
                "source": values["source"],
            }
            for metric, values in metrics.items()
        }

    return {
        "form_version": config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "counts": {
            "target_teams": len(forms),
            "teams_with_form": sum(row.get("overall_form_z") is not None for row in forms),
            "unique_matches": len({row["match_id"] for row in observations}),
            "team_match_rows": len(observations),
            "match_cards_missing_from_cache": len(missing_cache),
            "source_scope_team_rows": dict(sorted(scopes.items())),
        },
        "input_handoff": {
            "source_normalized_team_match_rows": processed_team_rows,
            "legacy_cache_fallback_rows": cache_fallback_rows,
            "note": "The fallback keeps older snapshots buildable; refreshed collectors materialize every row before Club Form scoring.",
        },
        "metric_coverage": metric_coverage,
        "normalisation": {
            "groups": competition_groups,
            "team_reference": reference,
        },
        "quality_flags": dict(sorted(flags.items())),
        "availability_snapshot": dict(availability),
        "leaders": {
            "overall": leaders("overall_form_z"),
            "attack": leaders("attack_z"),
            "defense": leaders("defense_z"),
        },
        "missing_cache_match_ids_sample": missing_cache[:25],
        "warnings": [
            "FotMob is an undocumented source; field-shape tests protect the normalization boundary.",
            "Missing match metrics remain missing. Score-only matches carry lower evidence through metric coverage.",
            "Preseason has a 0.25 source weight and cannot exceed 20% of a club's aggregate match weight.",
            "Injury flags are a dated availability snapshot and do not modify form without projected lineups.",
            "World Cup workload and tactical-role changes remain explicit future Club Form inputs.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config/club-form-v1.json")
    parser.add_argument(
        "--foundation-dir", type=Path, default=ROOT / "data/processed/foundation"
    )
    parser.add_argument(
        "--domestic-dir", type=Path, default=ROOT / "data/processed/domestic_history"
    )
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data/cache/fotmob")
    parser.add_argument(
        "--player-grades",
        type=Path,
        default=ROOT / "data/processed/player_quality_v2/player_grades.jsonl",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "data/processed/club_form"
    )
    parser.add_argument(
        "--audit", type=Path, default=ROOT / "reports/club-form-v1-audit.json"
    )
    parser.add_argument("--as-of", default=None, help="Inclusive YYYY-MM-DD snapshot date.")
    args = parser.parse_args()

    config = load_json(args.config)
    foundation_coverage = load_json(args.foundation_dir / "coverage.json")
    as_of = date.fromisoformat(args.as_of or foundation_coverage["as_of"])

    print("[1/4] Load and deduplicate normalized fixtures")
    foundation_fixtures = load_jsonl(args.foundation_dir / "fixtures.jsonl")
    domestic_fixtures = load_jsonl(args.domestic_dir / "fixtures.jsonl")
    fixtures = dedupe_fixtures(foundation_fixtures, domestic_fixtures)
    print(f"      {len(fixtures)} unique registered fixtures")

    print("[2/4] Normalize cached FotMob team-match evidence")
    processed_team_paths = [
        args.foundation_dir / "historical_match_team_stats.jsonl",
        args.foundation_dir / "current_match_team_stats.jsonl",
        args.foundation_dir / "preseason_match_team_stats.jsonl",
        args.domestic_dir / "match_team_stats.jsonl",
    ]
    processed_rows: list[dict[str, Any]] = []
    for path in processed_team_paths:
        processed_rows.extend(load_jsonl(path, required=False))
    processed_rows = [
        row
        for row in processed_rows
        if (parse_datetime(row.get("kickoff_utc")) or datetime.min.replace(tzinfo=timezone.utc)).date()
        <= as_of
    ]
    processed_match_ids = {int(row["match_id"]) for row in processed_rows}
    fallback_fixtures = [
        row for row in fixtures if int(row["match_id"]) not in processed_match_ids
    ]
    fallback_rows, missing_cache = build_match_observations(
        fallback_fixtures, args.cache_dir, as_of
    )
    observations_by_key: dict[tuple[int, int], dict[str, Any]] = {}
    for row in [*processed_rows, *fallback_rows]:
        observations_by_key.setdefault((int(row["match_id"]), int(row["team_id"])), row)
    observations = list(observations_by_key.values())
    scored, scales = score_match_observations(observations, as_of, config)
    print(
        f"      {len(scored)} team-match rows across "
        f"{len({row['match_id'] for row in scored})} finished matches "
        f"({len(processed_rows)} source-normalized rows, {len(fallback_rows)} cache fallbacks)"
    )

    print("[3/4] Build recency, opponent, reliability, and availability layers")
    teams = load_json(args.foundation_dir / "teams.json")
    squads = load_jsonl(args.foundation_dir / "squads.jsonl")
    grades = load_jsonl(args.player_grades, required=False)
    forms, reference = build_club_forms(scored, teams, squads, grades, as_of, config)
    if len(forms) != len(teams):
        raise RuntimeError(f"Club Form emitted {len(forms)} rows for {len(teams)} target teams")
    maximum_preseason_share = float(config["preseason"]["maximum_weight_share"])
    leaked_preseason = [
        row["team"]
        for row in forms
        if row["evidence"]["previous_competitive_matches"]
        and row["evidence"]["preseason_weight_share"] > maximum_preseason_share + 1e-6
    ]
    if leaked_preseason:
        raise RuntimeError(f"Preseason cap failed for: {', '.join(leaked_preseason)}")

    print("[4/4] Write ignored datasets and tracked audit")
    observation_count = write_jsonl(args.output_dir / "team_match_observations.jsonl", scored)
    form_count = write_jsonl(args.output_dir / "club_form.jsonl", forms)
    manifest = {
        "form_version": config["version"],
        "as_of": as_of.isoformat(),
        "source": config["source"],
        "inputs": {
            "foundation_dir": str(args.foundation_dir),
            "domestic_dir": str(args.domestic_dir),
            "cache_dir": str(args.cache_dir),
            "player_grades": str(args.player_grades),
            "processed_team_stat_files": [str(path) for path in processed_team_paths],
            "processed_team_stat_rows": len(processed_rows),
            "cache_fallback_rows": len(fallback_rows),
        },
        "outputs": {
            "team_match_observations": observation_count,
            "club_form_rows": form_count,
        },
        "availability_changes_form_score": config["availability"]["changes_form_score"],
    }
    write_json(args.output_dir / "manifest.json", manifest)
    audit = build_audit(
        scored,
        forms,
        scales,
        reference,
        missing_cache,
        config,
        as_of,
        len(processed_rows),
        len(fallback_rows),
    )
    write_json(args.audit, audit)
    print(json.dumps(audit["counts"], indent=2))
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
