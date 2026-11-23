import unittest

from clubalpha.bankroll_simulation import simulate_bankroll


CONFIG = {
    "version": "clubalpha_bankroll_simulation_v1",
    "starting_bankroll": 100000.0,
    "risk": {"maximum_fraction_of_current_bankroll_per_position": 0.01},
    "locked_boundaries": {
        "real_capital_authorized": False,
        "missing_prices_may_be_imputed": False,
        "post_kickoff_prices_allowed": False,
        "settled_results_may_change_selection": False,
    },
}


def candidate(*, won, ask=0.50, depth=5000.0, kickoff="2026-11-21T15:00:00Z"):
    return {
        "position_id": f"1:one_x_two:home_win:{kickoff}",
        "round": 11,
        "match_id": 1,
        "fixture": "Home vs Away",
        "kickoff_utc": kickoff,
        "market": "one_x_two",
        "outcome": "home_win",
        "model_probability": 0.60,
        "source": "polymarket",
        "best_ask": ask,
        "spread": 0.01,
        "top_ask_notional": depth,
        "raw_model_edge": 0.10,
        "settled": True,
        "won": won,
        "score": "1-0" if won else "0-1",
    }


class BankrollSimulationTests(unittest.TestCase):
    def test_one_percent_winner_compounds_bankroll(self):
        result = simulate_bankroll([candidate(won=True)], CONFIG)
        self.assertEqual(result["starting_bankroll"], 100000.0)
        self.assertEqual(result["ending_bankroll"], 101000.0)
        self.assertEqual(result["gross_pnl_units"], 1000.0)

    def test_top_of_book_depth_caps_position(self):
        result = simulate_bankroll([candidate(won=True, depth=250.0)], CONFIG)
        self.assertEqual(result["positions"][0]["paper_stake_units"], 250.0)
        self.assertEqual(result["ending_bankroll"], 100250.0)

    def test_same_kickoff_uses_same_pre_kickoff_bankroll(self):
        rows = [
            candidate(won=True),
            {**candidate(won=False), "position_id": "2:total:under", "match_id": 2},
        ]
        result = simulate_bankroll(rows, CONFIG)
        self.assertEqual(result["positions"][0]["paper_stake_units"], 1000.0)
        self.assertEqual(result["positions"][1]["paper_stake_units"], 1000.0)
        self.assertEqual(result["ending_bankroll"], 100000.0)

    def test_pending_candidate_does_not_change_bankroll(self):
        row = {**candidate(won=True), "settled": False, "won": None, "score": None}
        result = simulate_bankroll([row], CONFIG)
        self.assertEqual(result["ending_bankroll"], 100000.0)
        self.assertEqual(result["pending_positions"], 1)


if __name__ == "__main__":
    unittest.main()
