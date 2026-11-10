#!/usr/bin/env python3
"""Create or score the bounded discretionary review journal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.discretionary_overlay import (  # noqa: E402
    build_review_queue,
    score_review_queue,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--review-queue", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.decisions) == bool(args.review_queue):
        parser.error("provide exactly one of --decisions or --review-queue")

    config = load_json(args.config)
    artifact = (
        build_review_queue(load_json(args.decisions), config)
        if args.decisions
        else score_review_queue(load_json(args.review_queue), config)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = artifact.get("summary") or {
        "fixtures": len(artifact["fixtures"]),
        "structurally_reviewable": sum(
            selection["structurally_reviewable"]
            for fixture in artifact["fixtures"]
            for selection in fixture["selections"]
        ),
        "approved_active_overlays": 0,
    }
    print(json.dumps({"output": str(args.output), **summary}, indent=2))


if __name__ == "__main__":
    main()

