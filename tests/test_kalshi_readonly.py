import unittest

from clubalpha.kalshi_readonly import (
    group_fixture_markets,
    market_matches_team,
    summarize_market,
)


class KalshiReadonlyTests(unittest.TestCase):
    def test_team_aliases_match_market_titles(self):
        self.assertTrue(
            market_matches_team(
                {"title": "Tottenham wins"}, "Tottenham Hotspur"
            )
        )
        self.assertTrue(
            market_matches_team(
                {"title": "Bournemouth wins"}, "AFC Bournemouth"
            )
        )

    def test_fixture_markets_are_grouped_into_three_outcomes(self):
        markets = [
            {
                "event_ticker": "EVENT",
                "ticker": "EVENT-MCI",
                "title": "Manchester City wins",
            },
            {
                "event_ticker": "EVENT",
                "ticker": "EVENT-TIE",
                "title": "Tie is the result",
            },
            {
                "event_ticker": "EVENT",
                "ticker": "EVENT-FUL",
                "title": "Fulham wins",
            },
        ]
        result = group_fixture_markets(
            markets,
            {"home_team": "Manchester City", "away_team": "Fulham"},
        )
        self.assertEqual(result["event_ticker"], "EVENT")
        self.assertEqual(result["away_win"]["ticker"], "EVENT-FUL")

    def test_market_summary_uses_executable_yes_ask(self):
        result = summarize_market(
            {
                "ticker": "EVENT-MCI",
                "yes_bid_dollars": "0.6700",
                "yes_ask_dollars": "0.6800",
                "yes_ask_size_fp": "100.50",
                "volume_fp": "200.25",
                "open_interest_fp": "150.00",
            }
        )
        self.assertEqual(result["best_ask"], 0.68)
        self.assertAlmostEqual(result["spread"], 0.01)
        self.assertAlmostEqual(result["top_ask_notional"], 68.34)
        self.assertEqual(result["volume_contracts"], 200.25)


if __name__ == "__main__":
    unittest.main()
