import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "web/public/data/site.json"


class WebHolyGrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [sys.executable, "web/scripts/build_site_data.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.data = json.loads(SITE_DATA.read_text(encoding="utf-8"))

    def test_contextual_slate_reconciles_with_locked_baseline(self):
        baseline = {row["match_id"]: row for row in self.data["predictions"]}
        contextual = self.data["holy_grail"]["predictions"]
        self.assertEqual(len(contextual), 10)
        self.assertEqual({row["match_id"] for row in contextual}, set(baseline))
        for row in contextual:
            locked = baseline[row["match_id"]]
            self.assertEqual(row["home_team"], locked["home_team"])
            self.assertEqual(row["away_team"], locked["away_team"])
            self.assertEqual(
                row["baseline"]["predicted_xg"], locked["predicted_xg"]
            )

    def test_context_probabilities_and_directional_evidence_are_complete(self):
        for row in self.data["holy_grail"]["predictions"]:
            probabilities = row["probabilities"]
            self.assertAlmostEqual(
                probabilities["home_win"]
                + probabilities["draw"]
                + probabilities["away_win"],
                1.0,
            )
            for side in ("home", "away"):
                direction = row["directions"][side]
                self.assertTrue(direction["preferred_route"])
                self.assertGreaterEqual(direction["reliability"], 0.0)
                self.assertLessEqual(direction["reliability"], 1.0)
                self.assertGreater(direction["xg_multiplier"], 0.0)

    def test_shadow_safeguards_are_visible(self):
        model = self.data["holy_grail"]
        self.assertFalse(model["archetype_labels_used_in_math"])
        self.assertFalse(model["coefficient_learned"])
        self.assertFalse(model["capital_deployment_ready"])
        self.assertEqual(model["total_simulations"], 500000)

    def test_original_ledger_observation_is_not_rewritten(self):
        pick = self.data["official_shadow_pick"]
        locked = next(
            row for row in self.data["predictions"] if row["official_pick"]
        )
        self.assertEqual(pick["match_id"], locked["match_id"])
        self.assertEqual(
            pick["model_probability"], locked["probabilities"]["over_2_5"]
        )

    def test_holy_grail_static_route_is_generated(self):
        route = ROOT / "web/public/holy-grail/index.html"
        self.assertTrue(route.is_file())
        self.assertIn(
            'data-route="holy-grail"', route.read_text(encoding="utf-8")
        )

    def test_official_matchweek_three_is_a_separate_scoring_stream(self):
        slate = self.data["official_slate"]
        self.assertEqual(slate["fixtures"], 10)
        self.assertEqual(len(slate["predictions"]), 10)
        self.assertEqual(slate["validation"]["model_overrides"], 2)
        self.assertNotEqual(
            {row["match_id"] for row in slate["predictions"]},
            {row["match_id"] for row in self.data["predictions"]},
        )

    def test_official_ledger_opens_paper_review_only(self):
        ledger = self.data["ledger"]
        self.assertEqual(ledger["sample_gate"], 30)
        self.assertEqual(ledger["hit_rate_gate"], 0.5)
        self.assertEqual(ledger["next_stage"], "paper_allocation_and_price_validation")
        self.assertFalse(ledger["capital_deployment_ready"])


if __name__ == "__main__":
    unittest.main()
