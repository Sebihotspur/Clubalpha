import unittest

from clubalpha.polymarket_readonly import (
    event_matches_fixture,
    market_tokens,
    no_vig_probabilities,
    summarize_book,
)


class PolymarketReadonlyTests(unittest.TestCase):
    def test_market_tokens_reads_gamma_json_strings(self):
        self.assertEqual(
            market_tokens(
                {
                    "outcomes": '["Over", "Under"]',
                    "clobTokenIds": '["one", "two"]',
                }
            ),
            {"Over": "one", "Under": "two"},
        )

    def test_book_summary_uses_executable_top_and_depth(self):
        result = summarize_book(
            {
                "asset_id": "one",
                "bids": [{"price": "0.61", "size": "10"}],
                "asks": [
                    {"price": "0.65", "size": "20"},
                    {"price": "0.63", "size": "30"},
                    {"price": "0.66", "size": "40"},
                ],
                "min_order_size": "5",
                "tick_size": "0.01",
            }
        )
        self.assertEqual(result["best_ask"], 0.63)
        self.assertAlmostEqual(result["ask_notional_within_2c"], 31.9)

    def test_event_match_uses_teams_and_exact_kickoff(self):
        self.assertTrue(
            event_matches_fixture(
                {
                    "title": "Brighton & Hove Albion FC vs. Arsenal FC",
                    "endDate": "2026-09-19T14:00:00Z",
                },
                {
                    "home_team": "Brighton & Hove Albion",
                    "away_team": "Arsenal",
                    "kickoff_utc": "2026-09-19T14:00:00Z",
                },
            )
        )

    def test_no_vig_normalizes_three_outcomes(self):
        result = no_vig_probabilities({"home": 0.4, "draw": 0.3, "away": 0.35})
        self.assertAlmostEqual(sum(result.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
