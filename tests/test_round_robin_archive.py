import copy
import json
import unittest
from pathlib import Path

from clubalpha.round_robin_archive import (
    load_jsonl,
    validate_results,
    validate_round_robin,
)


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

    def test_summary_table_must_recompute_from_predictions(self):
        summary = copy.deepcopy(self.summary)
        summary["league_table"][0]["expected_points"] += 0.01
        with self.assertRaisesRegex(ValueError, "does not recompute"):
            validate_round_robin(self.predictions, summary)

    def result(self):
        fixture = self.predictions[0]["fixture"]
        return {
            "result_version": "clubalpha_round_robin_result_v1",
            "recorded_at_utc": "2026-09-01T18:00:00Z",
            "season": fixture["season"],
            "home_team_id": fixture["home_team_id"],
            "away_team_id": fixture["away_team_id"],
            "kickoff_utc": "2026-09-01T15:00:00Z",
            "final_home_goals": 2,
            "final_away_goals": 1,
            "outcome": "home_win",
            "source": "FotMob",
            "source_match_id": "real-1",
        }

    def test_result_stream_validates_join_and_score(self):
        validation = validate_results(self.predictions, [self.result()])
        self.assertEqual(validation["results"], 1)

    def test_duplicate_result_join_is_rejected(self):
        result = self.result()
        duplicate = {**result, "source_match_id": "real-2"}
        with self.assertRaisesRegex(ValueError, "duplicate prediction join keys"):
            validate_results(self.predictions, [result, duplicate])

    def test_result_outcome_must_match_goals(self):
        result = {**self.result(), "outcome": "away_win"}
        with self.assertRaisesRegex(ValueError, "outcome does not match"):
            validate_results(self.predictions, [result])


if __name__ == "__main__":
    unittest.main()
