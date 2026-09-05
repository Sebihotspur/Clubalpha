import json
import subprocess
import sys
import unittest
from pathlib import Path

from web.scripts.build_site_data import score_matchweek


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

    def test_matchweek_hit_rates_keep_markets_separate(self):
        weeks = {
            row["matchweek"]: row for row in self.data["ledger"]["matchweeks"]
        }
        self.assertEqual(set(weeks), {2, 3})
        completed = weeks[2]
        self.assertEqual(completed["settled"], 10)
        self.assertEqual(completed["markets"]["one_x_two"]["hit_rate"], 0.4)
        self.assertEqual(
            completed["markets"]["over_under_2_5"]["hit_rate"], 0.4
        )
        self.assertEqual(completed["markets"]["btts"]["hit_rate"], 0.6)
        self.assertFalse(completed["counts_toward_promotion_gate"])
        official = weeks[3]
        result_path = (
            ROOT
            / "artifacts/official_shadow/2026-08-31-mw3/results.jsonl"
        )
        result_count = sum(
            bool(line.strip())
            for line in result_path.read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(official["settled"], result_count)
        self.assertEqual(official["pending"], official["fixtures"] - result_count)
        for market in official["markets"].values():
            self.assertEqual(market["settled"], result_count)
            if result_count:
                self.assertEqual(
                    market["hit_rate"],
                    round(market["hits"] / result_count, 6),
                )
            else:
                self.assertIsNone(market["hit_rate"])
        self.assertTrue(official["counts_toward_promotion_gate"])

    def test_ipswich_liverpool_result_scores_markets_independently(self):
        predictions = [
            json.loads(line)
            for line in (
                ROOT
                / "artifacts/official_shadow/2026-08-31-mw3/predictions.jsonl"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        results = [
            json.loads(line)
            for line in (
                ROOT
                / "artifacts/official_shadow/2026-08-31-mw3/results.jsonl"
            )
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        prediction = next(
            row
            for row in predictions
            if row["fixture"]["match_id"] == 5795441
        )
        result = next(
            row for row in results if row["match_id"] == 5795441
        )
        score = score_matchweek([prediction], [result], official=True)
        # Liverpool was the audited 1X2 selection, while the model probabilities
        # leaned Over 2.5 and BTTS. The 0-2 result therefore grades 1X2 as a hit
        # and both goal markets as misses.
        self.assertEqual(score["settled"], 1)
        self.assertEqual(score["markets"]["one_x_two"]["hits"], 1)
        self.assertEqual(score["markets"]["over_under_2_5"]["hits"], 0)
        self.assertEqual(score["markets"]["btts"]["hits"], 0)

    def test_matchweek_history_uses_collapsible_native_controls(self):
        app = (ROOT / "web/public/app.js").read_text(encoding="utf-8")
        self.assertIn('<details class="matchweek-fold">', app)
        self.assertIn("Hit rate by matchweek", app)

    def test_methodology_exposes_the_append_only_learning_loop(self):
        learning = self.data["methodology"]["research_loop"]
        self.assertEqual(learning["completed_results"], 17)
        self.assertEqual(learning["frozen_fixtures"], 20)
        self.assertEqual(learning["promotion_candidates"], 0)
        self.assertEqual(learning["automatically_applied"], 0)
        self.assertFalse(learning["capital_deployment_ready"])
        app = (ROOT / "web/public/app.js").read_text(encoding="utf-8")
        self.assertIn("05 · Learning loop", app)
        self.assertIn("Absorb evidence without rewriting the model", app)

    def test_current_results_expose_outcomes_and_model_diagnostics(self):
        diagnostic = self.data["official_slate"]["performance_diagnostic"]
        self.assertEqual(diagnostic["settled"], 7)
        self.assertEqual(diagnostic["official_1x2_hits"], 2)
        self.assertEqual(diagnostic["raw_probability_leader_hits"], 1)
        self.assertAlmostEqual(
            diagnostic["mean_projected_xi_hits_of_11"], 8.285714
        )
        self.assertFalse(diagnostic["sample_sufficient_to_recalibrate"])
        official_week = next(
            row
            for row in self.data["ledger"]["matchweeks"]
            if row["counts_toward_promotion_gate"]
        )
        self.assertEqual(official_week["markets"]["one_x_two"]["hits"], 2)
        self.assertEqual(
            official_week["markets"]["over_under_2_5"]["hits"], 2
        )
        self.assertEqual(official_week["markets"]["btts"]["hits"], 4)

        newcastle = next(
            row
            for row in self.data["official_slate"]["predictions"]
            if row["match_id"] == 5795443
        )
        self.assertEqual(newcastle["status"], "settled")
        self.assertEqual(newcastle["result"]["final_home_goals"], 2)
        self.assertEqual(newcastle["result"]["final_away_goals"], 2)
        self.assertFalse(newcastle["result"]["official_1x2_hit"])
        self.assertFalse(newcastle["result"]["raw_1x2_hit"])


if __name__ == "__main__":
    unittest.main()
