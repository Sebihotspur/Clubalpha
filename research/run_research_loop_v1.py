#!/usr/bin/env python3
"""Create or verify one deterministic Clubalpha research-loop checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.research_loop import build_research_state, learning_summary  # noqa: E402
from clubalpha.round_robin_archive import load_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default="2026-08-31")
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "config/research-loop-2026-27.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/research-loop-v1.json",
    )
    parser.add_argument("--checkpoint-dir", type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(state: dict[str, Any]) -> str:
    summary = learning_summary(state)

    def table(rows: list[dict[str, Any]]) -> str:
        output = ["| Team | Matches | Multiplier | Confidence |", "|---|---:|---:|---:|"]
        output.extend(
            f"| {row['team']} | {row['matches']} | {row['posterior_multiplier']:.3f} | {row['confidence']:.3f} |"
            for row in rows
        )
        return "\n".join(output)

    queue = state["research_queue"]
    metrics = state["league_learning"]["base_vs_context_metrics"]
    ablation = state["league_learning"]["pre_match_goal_coefficient_ablation"]
    lines = [
        "# Clubalpha research checkpoint",
        "",
        f"As of: {state['as_of']}",
        "",
        f"Completed frozen fixtures: {state['coverage']['completed_results']}/{state['coverage']['frozen_fixtures']}",
        "",
        "## What the loop learned",
        "",
        "The state below is deliberately tentative. Every club has only one new match, so no belief passed the five-match promotion gate and nothing was applied to a forecast.",
        "",
        "### Attack above expectation",
        "",
        table(summary["attack_above_expectation"]),
        "",
        "### Defensive exposure above expectation",
        "",
        table(summary["defensive_exposure_above_expectation"]),
        "",
        "### Higher-tempo environments than expected",
        "",
        table(summary["higher_tempo_than_expected"]),
        "",
        "## Model diagnostics",
        "",
        f"- Base side-xG MAE: {metrics['baseline']['xg_side_mae']:.3f}",
        f"- Holy Grail side-xG MAE: {metrics['contextual']['xg_side_mae']:.3f}",
        f"- Best pre-match coefficient candidate: {ablation['best_side_xg_mae_candidate'] if ablation else 'not supplied'}",
        f"- Structural fixture reviews: {', '.join(queue['structural_fixture_reviews']) or 'none'}",
        "- Lineup reviews: "
        + (
            ", ".join(
                f"{row['team']} ({'/'.join(row['reasons'])})"
                for row in queue["lineup_projection_reviews"]
            )
            or "none"
        ),
        f"- Missing preferred route evidence: {', '.join(queue['missing_preferred_routes']) or 'none'}",
        "",
        "## Promotion gate",
        "",
        f"Candidates eligible for review: {state['forecast_handoff']['eligible_candidates']}",
        "",
        "Research state updates automatically. Player Alpha, the 60/30/10 base, frozen predictions, code, and capital authorization do not.",
        "",
    ]
    return "\n".join(lines)


def _write_or_verify(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"checkpoint file already exists with different content: {path}")
        return
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    registry = load_json(args.registry)
    if registry.get("registry_version") != "clubalpha_research_cycle_registry_v1":
        raise ValueError("research cycle registry version is not supported")
    cycles = registry.get("cycles") or []
    if not cycles:
        raise ValueError("research cycle registry contains no cycles")
    predictions = []
    results = []
    base_predictions = []
    lineup_clubs = []
    goal_models = []
    cycle_ids = []
    for cycle in cycles:
        cycle_ids.append(str(cycle["cycle_id"]))
        archive = ROOT / cycle["contextual_archive"]
        predictions.extend(load_jsonl(archive / "predictions.jsonl"))
        results.extend(load_jsonl(archive / "results.jsonl"))
        base_predictions.extend(load_jsonl(ROOT / cycle["base_predictions"]))
        snapshot = load_json(ROOT / cycle["lineup_snapshot"])
        lineup_clubs.extend(snapshot.get("clubs") or [])
        goal_models.append(load_json(ROOT / cycle["goal_model_artifact"]))
    goal_versions = {row.get("version") for row in goal_models}
    shared_goal_model = goal_models[0] if len(goal_versions) == 1 else None
    lineup_snapshot = {
        "snapshot_version": "clubalpha_research_registry_combined_lineups_v1",
        "clubs": lineup_clubs,
    }
    state = build_research_state(
        predictions,
        results,
        lineup_snapshot,
        load_json(args.config),
        as_of=args.as_of,
        base_predictions=base_predictions if shared_goal_model else None,
        goal_model_artifact=shared_goal_model,
    )
    checkpoint_dir = args.checkpoint_dir or (
        ROOT
        / "artifacts/research_loop"
        / f"{args.as_of}-{len(state['input_match_ids'])}-completed"
    )
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    state_path = checkpoint_dir / "state.json"
    report_path = checkpoint_dir / "report.md"
    state_content = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    report_content = _report(state)
    _write_or_verify(state_path, state_content)
    _write_or_verify(report_path, report_content)
    manifest = {
        "checkpoint_version": "clubalpha_research_checkpoint_v1",
        "as_of": args.as_of,
        "completed_matches": len(results),
        "input_result_fingerprint_sha256": state["input_fingerprint_sha256"],
        "input_match_ids": state["input_match_ids"],
        "files": {
            "state.json": _sha256(state_path),
            "report.md": _sha256(report_path),
        },
        "source_versions": {
            "research_loop": state["research_loop_version"],
            "research_state": state["research_state_version"],
            "cycle_registry": registry["registry_version"],
        },
        "cycle_ids": cycle_ids,
        "registry_sha256": _sha256(args.registry),
        "implementation_sha256": {
            "clubalpha/research_loop.py": _sha256(
                ROOT / "clubalpha/research_loop.py"
            ),
            "research/run_research_loop_v1.py": _sha256(Path(__file__)),
            "config/research-loop-v1.json": _sha256(args.config),
        },
        "frozen_predictions_mutated": False,
    }
    _write_or_verify(
        checkpoint_dir / "manifest.json",
        json.dumps(manifest, indent=2) + "\n",
    )
    print(
        f"Research checkpoint ready: {len(results)} completed matches, "
        f"{len(state['promotion_candidates'])} promotion candidates, "
        f"{checkpoint_dir.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
