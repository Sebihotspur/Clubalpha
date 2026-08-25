import copy
import json
import unittest
from pathlib import Path

from clubalpha.round_robin_archive import load_jsonl, validate_round_robin


REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = REPO_ROOT / "artifacts" / "round_robin" / "2026-08-25"


class RoundRobinArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictions = load_jsonl(ARCHIVE / "predictions.jsonl")
        cls.summary = json.loads((ARCHIVE / "summary.json").read_text())

    def test_frozen_baseline_is_complete_and_joinable(self):
        validation = validate_round_robin(self.predictions, self.summary)
        self.assertEqual(validation["season"], "2026/2027")
        self.assertEqual(validation["teams"], 20)
        self.assertEqual(validation["fixtures"], 380)
        self.assertEqual(validation["matches_per_team"], 38)
        self.assertEqual(validation["unique_join_keys"], 380)

    def test_duplicate_fixture_is_rejected(self):
        predictions = copy.deepcopy(self.predictions)
        predictions[-1] = predictions[0]
        with self.assertRaisesRegex(ValueError, "join keys are not unique"):
            validate_round_robin(predictions, self.summary)

    def test_invalid_probability_is_rejected(self):
        predictions = copy.deepcopy(self.predictions)
        predictions[0]["probabilities"]["home_win"] += 0.01
        with self.assertRaisesRegex(ValueError, "do not sum to 1"):
            validate_round_robin(predictions, self.summary)


if __name__ == "__main__":
    unittest.main()
