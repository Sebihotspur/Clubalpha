#!/usr/bin/env python3
"""Build a dated Clubalpha paper-performance snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.paper_performance import build_paper_ledger  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--market-gate", type=Path, required=True)
    parser.add_argument("--discretionary-queue", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ledger = build_paper_ledger(
        load_json(args.decisions),
        load_json(args.market_gate),
        load_json(args.discretionary_queue),
        load_jsonl(args.results),
        load_json(args.config),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **ledger["coverage"], **ledger["summary"]}, indent=2))


if __name__ == "__main__":
    main()

