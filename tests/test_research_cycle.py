import hashlib
import json
import unittest
from pathlib import Path

from clubalpha.contextual_backtest import RESULT_VERSION
from clubalpha.research_cycle import load_registered_cycle


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/research-loop-2026-27.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ResearchCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.cycles = {
            row["cycle_id"]: row for row in registry["cycles"]
        }

    def test_official_slate_is_adapted_without_mutating_the_archive(self):
        cycle = self.cycles["2026-08-31-matchweek-3-official"]
        archive = ROOT / cycle["archive"]
        predictions_path = archive / "predictions.jsonl"
        before = sha256(predictions_path)
        normalized = load_registered_cycle(ROOT, cycle)
        self.assertEqual(sha256(predictions_path), before)
        self.assertEqual(normalized["prediction_format"], "official_shadow")
        self.assertEqual(len(normalized["predictions"]), 10)
        source_result_count = sum(
            bool(line.strip())
            for line in (archive / "results.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.assertEqual(len(normalized["results"]), source_result_count)
        self.assertEqual(
            normalized["results"][0]["result_version"], RESULT_VERSION
        )

    def test_official_probability_and_decision_targets_remain_separate(self):
        cycle = self.cycles["2026-08-31-matchweek-3-official"]
        normalized = load_registered_cycle(ROOT, cycle)
        row = next(
            item
            for item in normalized["predictions"]
            if item["fixture"]["match_id"] == 5795441
        )
        self.assertEqual(row["source_official_pick"]["outcome"], "away_win")
        probabilities = row["contextual"]["probabilities"]
        self.assertEqual(
            max(("home_win", "draw", "away_win"), key=probabilities.get),
            "home_win",
        )
        self.assertFalse(
            row["decision_boundaries"]["official_pick_used_as_research_target"]
        )

    def test_lineup_projections_are_bound_to_actual_fixture_ids(self):
        cycle = self.cycles["2026-08-31-matchweek-3-official"]
        normalized = load_registered_cycle(ROOT, cycle)
        keys = {
            (club["next_fixture"]["match_id"], club["team_id"])
            for club in normalized["lineup_snapshot"]["clubs"]
        }
        expected = {
            (row["fixture"]["match_id"], row["fixture"][f"{side}_team_id"])
            for row in normalized["predictions"]
            for side in ("home", "away")
        }
        self.assertEqual(keys, expected)


if __name__ == "__main__":
    unittest.main()
