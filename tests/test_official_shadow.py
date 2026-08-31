import copy
import json
import unittest
from pathlib import Path

from clubalpha.official_shadow import score_results, validate_predictions


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "artifacts/official_shadow/2026-08-31-mw3"


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


class OfficialShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_jsonl(ARCHIVE / "predictions.jsonl")

    def test_official_slate_is_complete_and_pre_kickoff(self):
        result = validate_predictions(
            self.rows,
            expected_round=3,
            expected_fixtures=10,
            as_of_utc="2026-08-31T18:56:06Z",
        )
        self.assertEqual(result["fixtures"], 10)
        self.assertEqual(result["model_overrides"], 2)

    def test_override_requires_reason(self):
        rows = copy.deepcopy(self.rows)
        override = next(
            row
            for row in rows
            if row["translation_audit"]["official_overrides_probability_leader"]
        )
        override["official_pick"]["override_reason"] = None
        with self.assertRaisesRegex(ValueError, "override requires"):
            validate_predictions(
                rows,
                expected_round=3,
                expected_fixtures=10,
                as_of_utc="2026-08-31T18:56:06Z",
            )

    def test_result_stream_scores_exact_pick(self):
        row = self.rows[0]
        result = {
            "match_id": row["fixture"]["match_id"],
            "final_home_goals": 1,
            "final_away_goals": 2,
            "outcome": "away_win",
        }
        score = score_results(self.rows, [result])
        self.assertEqual(score["settled"], 1)
        self.assertEqual(score["hits"], 1)
        self.assertEqual(score["hit_rate"], 1.0)

    def test_duplicate_result_is_rejected(self):
        row = self.rows[0]
        result = {
            "match_id": row["fixture"]["match_id"],
            "final_home_goals": 1,
            "final_away_goals": 2,
            "outcome": "away_win",
        }
        with self.assertRaisesRegex(ValueError, "duplicate match id"):
            score_results(self.rows, [result, result])


if __name__ == "__main__":
    unittest.main()
