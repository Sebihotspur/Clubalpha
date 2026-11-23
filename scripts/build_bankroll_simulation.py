#!/usr/bin/env python3
"""Build Clubalpha's reproducible $100k paper-bankroll history."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.bankroll_simulation import build_bankroll_artifact  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = load_json(args.registry)
    snapshots = [load_json(ROOT / path) for path in registry["market_snapshots"]]
    results = [
        row
        for path in registry["result_streams"]
        for row in load_jsonl(ROOT / path)
    ]
    artifact = build_bankroll_artifact(snapshots, results, load_json(args.config))
    artifact["sources"] = registry
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **artifact["coverage"], **{key: value for key, value in artifact["simulation"].items() if key not in {"positions", "pending", "by_round"}}}, indent=2))


if __name__ == "__main__":
    main()

