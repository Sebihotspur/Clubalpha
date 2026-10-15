#!/usr/bin/env python3
"""Build direct-opponent and archetype matchup memory from learning cards."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.archetype_memory import build_archetype_memory  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    memory = build_archetype_memory(load_jsonl(args.cards), as_of=args.as_of)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "memory.json").write_text(
        json.dumps(memory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    league_rows = memory["archetype_vs_archetype"]
    report_lines = [
        "# Archetype matchup memory",
        "",
        f"As of: {args.as_of}",
        "",
        f"Team-perspective observations: {len(memory['observations'])}",
        "",
        "This is a zero-weight context ledger. It cannot rewrite Player Alpha, Club Form, probabilities, or capital authorization.",
        "",
        "## Most observed archetype interactions",
        "",
        "| Attacker archetype | Opponent archetype | N | W-D-L | xG diff | Tier |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in league_rows[:20]:
        record = row["record"]
        report_lines.append(
            "| {team} | {opponent} | {n} | {w}-{d}-{l} | {xg} | {tier} |".format(
                team=row.get("team_archetype") or "Unknown",
                opponent=row.get("opponent_archetype") or "Unknown",
                n=row["observations"],
                w=record["wins"],
                d=record["draws"],
                l=record["losses"],
                xg=row["weighted_process"]["xg_difference"],
                tier=row["evidence_tier"],
            )
        )
    (args.output_dir / "report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output_dir),
                "observations": len(memory["observations"]),
                "direct_opponent_rows": len(memory["direct_opponent"]),
                "team_archetype_rows": len(memory["team_vs_opponent_archetype"]),
                "league_archetype_rows": len(memory["archetype_vs_archetype"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

