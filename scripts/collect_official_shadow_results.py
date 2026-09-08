#!/usr/bin/env python3
"""Append completed FotMob results to the latest official shadow slate."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.collect_contextual_results import main  # noqa: E402


def latest_official_archive() -> Path:
    candidates = []
    for report_path in (ROOT / "artifacts/official_shadow").glob("*/report.json"):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        candidates.append(
            (
                int(report["round"]),
                str(report["as_of_utc"]),
                report_path.parent,
            )
        )
    if not candidates:
        raise FileNotFoundError("no official shadow archive is available")
    return max(candidates, key=lambda row: row[:2])[2]


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--archive-dir" not in arguments:
        arguments = [
            "--archive-dir",
            str(latest_official_archive()),
            *arguments,
        ]
    sys.argv = [sys.argv[0], "--result-stream", "official", *arguments]
    raise SystemExit(main())
