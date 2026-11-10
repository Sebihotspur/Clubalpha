import unittest

from clubalpha.market_gate import evaluate_selection, snapshot_index


CONFIG = {
    "version": "clubalpha_market_gate_v1",
    "edge": {
        "minimum_raw_edge": 0.05,
        "execution_cost_reserve": 0.015,
        "uncertainty_reserve": {"provisional": 0.025, "final": 0.015},
        "minimum_edge_after_reserves": 0.01,
    },
    "execution": {
        "maximum_spread": 0.03,
        "minimum_top_ask_notional": 50.0,
        "maximum_cross_book_ask_gap": 0.03,
    },
    "requirements": {
        "football_call_required": True,
        "final_refresh_required": True,
        "executable_best_ask_required": True,
    },
    "locked_boundaries": {
        "price_can_promote_football_pass": False,
        "automatic_real_capital_authorization": False,
        "frozen_model_probabilities_mutable": False,
    },
}


def snapshots(ask=0.50, spread=0.02, depth=100.0):
    return {
        "polymarket": {
            1: {
                "one_x_two": {
                    "outcomes": {
                        "home_win": {
                            "book": {
                                "best_bid": ask - spread,
                                "best_ask": ask,
                                "spread": spread,
                                "top_ask_notional": depth,
                            }
                        }
                    }
                }
            }
        }
    }


def two_book_snapshots():
    result = snapshots(ask=0.50, depth=25.0)
    result["kalshi"] = {
        1: {
            "one_x_two": {
                "outcomes": {
                    "home_win": {
                        "book": {
                            "best_bid": 0.49,
                            "best_ask": 0.51,
                            "spread": 0.02,
                            "top_ask_notional": 100.0,
                        }
                    }
                }
            }
        }
    }
    return result


class MarketGateTests(unittest.TestCase):
    def test_price_cannot_promote_a_football_pass(self):
        result = evaluate_selection(
            match_id=1,
            market="one_x_two",
            football_call="pass",
            diagnostic_outcome="home_win",
            probability=0.70,
            stage="final",
            final_call_eligible=True,
            snapshots=snapshots(ask=0.40),
            config=CONFIG,
        )
        self.assertFalse(result["paper_eligible"])
        self.assertEqual(result["reason"], "football_layer_pass")
        self.assertTrue(result["diagnostic_only"])

    def test_final_call_with_edge_and_execution_quality_passes_paper_gate(self):
        result = evaluate_selection(
            match_id=1,
            market="one_x_two",
            football_call="home_win",
            diagnostic_outcome="home_win",
            probability=0.60,
            stage="final",
            final_call_eligible=True,
            snapshots=snapshots(ask=0.52),
            config=CONFIG,
        )
        self.assertTrue(result["paper_eligible"])
        self.assertAlmostEqual(result["best_execution"]["raw_edge"], 0.08)
        self.assertAlmostEqual(
            result["best_execution"]["edge_after_reserves"], 0.05
        )

    def test_provisional_refresh_blocks_otherwise_valid_price(self):
        result = evaluate_selection(
            match_id=1,
            market="one_x_two",
            football_call="home_win",
            diagnostic_outcome="home_win",
            probability=0.60,
            stage="provisional",
            final_call_eligible=False,
            snapshots=snapshots(ask=0.52),
            config=CONFIG,
        )
        self.assertFalse(result["paper_eligible"])
        self.assertEqual(result["reason"], "final_refresh_incomplete")

    def test_shallow_book_blocks_paper_gate(self):
        result = evaluate_selection(
            match_id=1,
            market="one_x_two",
            football_call="home_win",
            diagnostic_outcome="home_win",
            probability=0.60,
            stage="final",
            final_call_eligible=True,
            snapshots=snapshots(ask=0.52, depth=25.0),
            config=CONFIG,
        )
        self.assertFalse(result["paper_eligible"])
        self.assertEqual(result["reason"], "top_ask_depth_below_gate")

    def test_best_execution_skips_cheaper_book_without_required_depth(self):
        result = evaluate_selection(
            match_id=1,
            market="one_x_two",
            football_call="home_win",
            diagnostic_outcome="home_win",
            probability=0.60,
            stage="final",
            final_call_eligible=True,
            snapshots=two_book_snapshots(),
            config=CONFIG,
        )
        self.assertEqual(result["best_execution"]["source"], "kalshi")
        self.assertEqual(result["best_execution"]["best_ask"], 0.51)
        self.assertTrue(result["paper_eligible"])

    def test_snapshot_index_identifies_supported_books(self):
        result = snapshot_index(
            [
                {
                    "version": "clubalpha_polymarket_readonly_v1",
                    "fixtures": [{"fixture": {"match_id": 1}}],
                },
                {
                    "version": "clubalpha_kalshi_readonly_v1",
                    "fixtures": [{"fixture": {"match_id": 1}}],
                },
            ]
        )
        self.assertEqual(set(result), {"polymarket", "kalshi"})


if __name__ == "__main__":
    unittest.main()
