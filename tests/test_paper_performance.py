import unittest

from clubalpha.paper_performance import _book_summary, _selection


CONFIG = {
    "allocation": {
        "default_position_stake_units": 1.0,
        "shadow_candidate_official_stake_units": 0.0,
    }
}


class PaperPerformanceTests(unittest.TestCase):
    def test_winning_yes_contract_uses_equal_capital_return(self):
        row = _selection(
            fixture={
                "match_id": 1,
                "fixture": "Home vs Away",
                "kickoff_utc": "2026-11-21T15:00:00Z",
            },
            market="one_x_two",
            outcome="home_win",
            probability=0.60,
            best_execution={
                "source": "polymarket",
                "best_ask": 0.50,
                "market_no_vig_probability": 0.48,
            },
            result={
                "outcome": "home_win",
                "final_home_goals": 2,
                "final_away_goals": 0,
            },
            book="official_paper",
            official_position=True,
            config=CONFIG,
        )
        self.assertEqual(row["official_gross_pnl_units"], 1.0)
        self.assertEqual(row["official_stake_units"], 1.0)
        self.assertEqual(row["market_no_vig_probability"], 0.48)
        self.assertAlmostEqual(row["model_vs_market_no_vig"], 0.12)
        self.assertAlmostEqual(row["model_vs_executable_ask"], 0.10)

    def test_shadow_candidate_never_becomes_official_stake(self):
        row = _selection(
            fixture={
                "match_id": 1,
                "fixture": "Home vs Away",
                "kickoff_utc": "2026-11-21T15:00:00Z",
            },
            market="one_x_two",
            outcome="home_win",
            probability=0.60,
            best_execution={"source": "polymarket", "best_ask": 0.40},
            result={
                "outcome": "home_win",
                "final_home_goals": 1,
                "final_away_goals": 0,
            },
            book="discretionary_review_candidate",
            official_position=False,
            config=CONFIG,
        )
        self.assertEqual(row["official_stake_units"], 0.0)
        self.assertEqual(row["official_gross_pnl_units"], 0.0)
        self.assertEqual(row["counterfactual_equal_stake_gross_pnl_units"], 1.5)

    def test_counterfactual_summary_separates_pending(self):
        rows = [
            {
                "settled": True,
                "won": True,
                "counterfactual_equal_stake_gross_pnl_units": 1.0,
                "official_gross_pnl_units": 0.0,
                "official_stake_units": 0.0,
            },
            {
                "settled": True,
                "won": False,
                "counterfactual_equal_stake_gross_pnl_units": -1.0,
                "official_gross_pnl_units": 0.0,
                "official_stake_units": 0.0,
            },
            {
                "settled": False,
                "won": None,
                "counterfactual_equal_stake_gross_pnl_units": None,
                "official_gross_pnl_units": 0.0,
                "official_stake_units": 0.0,
            },
        ]
        summary = _book_summary(rows, counterfactual=True)
        self.assertEqual(summary["settled"], 2)
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["gross_roi"], 0.0)


if __name__ == "__main__":
    unittest.main()
