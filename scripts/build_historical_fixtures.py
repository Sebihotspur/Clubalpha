#!/usr/bin/env python3
"""Build Historical Fixtures intelligence from normalized Clubalpha match records."""

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

from clubalpha.historical_fixtures import (  # noqa: E402
    build_historical_fixture_intelligence,
    dedupe_team_match_rows,
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
    outputs: list[dict[str, Any]],
    scored_rows: list[dict[str, Any]],
    scales: dict[str, Any],
    as_of: date,
    config: dict[str, Any],
) -> dict[str, Any]:
    flags = Counter(flag for row in outputs for flag in row["quality_flags"])
    direct_counts = Counter(int(row["direct_history"]["meetings"]) for row in outputs)
    scope_counts = Counter(str(row["fixture"]["source_scope"]) for row in outputs)

    def sample(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "match_id": row["fixture"]["match_id"],
            "kickoff_utc": row["fixture"]["kickoff_utc"],
            "fixture": f"{row['fixture']['home_team']} vs {row['fixture']['away_team']}",
            "direct_meetings": row["direct_history"]["meetings"],
            "direct_signal_share": row["direct_history"]["signal_share"],
            "historical_signals": row["historical_signals"],
            "quality_flags": row["quality_flags"],
        }

    examples = [sample(row) for row in outputs[:12]]
    scale_values = [
        scale
        for metrics in scales.values()
        for scale in metrics.values()
    ]
    return {
        "historical_fixtures_version": config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of.isoformat(),
        "counts": {
            "target_fixtures": len(outputs),
            "fixture_scopes": dict(sorted(scope_counts.items())),
            "historical_team_match_rows": len(scored_rows),
            "fixtures_with_direct_history": sum(row["direct_history"]["meetings"] > 0 for row in outputs),
            "fixtures_without_direct_history": sum(row["direct_history"]["meetings"] == 0 for row in outputs),
            "fixtures_with_xg_baseline": sum(row["historical_signals"]["descriptive_xg_baseline"]["total"] is not None for row in outputs),
            "fixtures_with_complete_attack_signals": sum(row["historical_signals"]["home_attack_z"] is not None and row["historical_signals"]["away_attack_z"] is not None for row in outputs),
            "fixtures_with_competition_baseline": sum(
                row.get("competition_baseline") is not None for row in outputs
            ),
        },
        "coverage": {
            "direct_meeting_distribution": {str(key): value for key, value in sorted(direct_counts.items())},
            "quality_flags": dict(sorted(flags.items())),
        },
        "normalisation": {
            "groups": len(scales),
            "metric_scales": len(scale_values),
            "competition_scales": sum(scale["source"] == "competition" for scale in scale_values),
            "global_fallback_scales": sum(scale["source"] == "global_fallback" for scale in scale_values),
            "league_strength_policy": config["league_strength"],
        },
        "examples": examples,
        "decision_boundaries": {
            **config["decision_boundaries"],
            "descriptive_only": True,
            "maximum_direct_signal_share": config["direct_history"]["maximum_signal_share"],
            "raw_xg_baseline_is_competition_adjusted": False,
        },
        "warnings": [
            "Historical attack and defence signals are competition-normalized and use the locked Player Quality league ladder.",
            "Descriptive xG and empirical rates are raw historical context, not calibrated fixture probabilities.",
            "Direct head-to-head evidence is recency-weighted, venue-aware, reliability-shrunk, and capped.",
            "No historical signal changes Player Quality or Club Form.",
            "Only information available on or before the as-of date enters this snapshot.",
            "Deep history uses separate clocks: slow competition baselines and shorter team/direct windows.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config/historical-fixtures-v1.json"
    )
    parser.add_argument(
        "--foundation-dir", type=Path, default=ROOT / "data/processed/foundation"
    )
    parser.add_argument(
        "--domestic-dir", type=Path, default=ROOT / "data/processed/domestic_history"
    )
    parser.add_argument("--deep-history-dir", type=Path, default=None)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "data/processed/historical_fixtures"
    )
    parser.add_argument(
        "--audit", type=Path, default=ROOT / "reports/historical-fixtures-v1-audit.json"
    )
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()

    config = load_json(args.config)
    foundation_coverage = load_json(args.foundation_dir / "coverage.json")
    as_of = date.fromisoformat(args.as_of or foundation_coverage["as_of"])
    league_config_path = ROOT / config["league_strength"]["config_path"]
    league_config = load_json(league_config_path)
    league_policy = league_config[config["league_strength"]["policy_key"]]

    print("[1/4] Load dated fixtures and normalized competitive history")
    fixtures = load_jsonl(args.foundation_dir / "fixtures.jsonl")
    history_inputs = config.get("history_inputs") or {}
    configured_deep_dir = (
        ROOT / history_inputs["deep_history_dir"]
        if history_inputs.get("include_deep_history")
        else None
    )
    deep_history_dir = args.deep_history_dir or configured_deep_dir
    row_sets: list[list[dict[str, Any]]] = []
    if deep_history_dir is not None:
        row_sets.append(load_jsonl(deep_history_dir / "match_team_stats.jsonl"))
    row_sets.extend(
        [
            load_jsonl(args.foundation_dir / "historical_match_team_stats.jsonl"),
            load_jsonl(
                args.foundation_dir / "current_match_team_stats.jsonl", required=False
            ),
            load_jsonl(args.domestic_dir / "match_team_stats.jsonl", required=False),
        ]
    )
    history_rows = dedupe_team_match_rows(*row_sets)

    print("[2/4] Standardize history and apply the locked league-strength ladder")
    outputs, scored_rows, scales = build_historical_fixture_intelligence(
        fixtures, history_rows, as_of, config, league_policy
    )

    print("[3/4] Materialize fixture intelligence")
    write_jsonl(args.output_dir / "historical_fixture_intelligence.jsonl", outputs)
    write_jsonl(args.output_dir / "scored_history_observations.jsonl", scored_rows)
    write_json(
        args.output_dir / "manifest.json",
        {
            "historical_fixtures_version": config["version"],
            "as_of": as_of.isoformat(),
            "source": config["source"],
            "outputs": {
                "fixtures": len(outputs),
                "historical_team_match_rows": len(scored_rows),
            },
            "decision_boundaries": config["decision_boundaries"],
        },
    )

    print("[4/4] Write tracked coverage and decision audit")
    audit = build_audit(outputs, scored_rows, scales, as_of, config)
    write_json(args.audit, audit)
    print(json.dumps(audit["counts"], indent=2))
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
