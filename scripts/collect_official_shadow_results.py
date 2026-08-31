#!/usr/bin/env python3
"""Append completed FotMob results to the current official shadow slate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.collect_contextual_results import main  # noqa: E402


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--archive-dir" not in arguments:
        arguments = [
            "--archive-dir",
            str(ROOT / "artifacts/official_shadow/2026-08-31-mw3"),
            *arguments,
        ]
    sys.argv = [sys.argv[0], "--result-stream", "official", *arguments]
    raise SystemExit(main())
