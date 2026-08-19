import unittest

from clubalpha.fotmob import (
    flatten_match_player_stats,
    normalize_fixture,
    normalize_name,
    normalize_stat_rows,
)


class FotMobNormalizationTests(unittest.TestCase):
    def test_normalize_name_handles_accents_and_punctuation(self):
        self.assertEqual(normalize_name("Paris Saint-Germain"), "paris saint germain")
        self.assertEqual(normalize_name("Bayern München"), "bayern munchen")

    def test_normalize_fixture_handles_league_shape(self):
        row = {
            "id": "4813374",
            "roundName": 1,
            "home": {"id": "8650", "name": "Liverpool"},
            "away": {"id": "8678", "name": "AFC Bournemouth"},
            "status": {"utcTime": "2025-08-15T19:00:00Z", "finished": True, "scoreStr": "4 - 2"},
        }
        result = normalize_fixture(row, source_scope="premier_league_previous")
        self.assertEqual(result["match_id"], 4813374)
        self.assertEqual(result["home_team_id"], 8650)
        self.assertTrue(result["finished"])

    def test_normalize_stat_rows_preserves_fotmob_ids_and_minutes(self):
        payload = {
            "TopLists": [
                {
                    "StatName": "expected_goals",
                    "Title": "Expected goals (xG)",
                    "StatList": [
                        {
                            "ParticiantId": 737066,
                            "ParticipantName": "Erling Haaland",
                            "TeamId": 8456,
                            "TeamName": "Manchester City",
                            "StatValue": 25.8,
                            "MinutesPlayed": 2958,
                            "MatchesPlayed": 35,
                            "Rank": 1,
                            "Positions": [115],
                        }
                    ],
                }
            ]
        }
        rows = normalize_stat_rows(
            payload,
            competition_id=47,
            competition="Premier League",
            season="2025/2026",
        )
        self.assertEqual(rows[0]["participant_id"], 737066)
        self.assertEqual(rows[0]["metric"], "expected_goals")
        self.assertEqual(rows[0]["minutes"], 2958)

    def test_flatten_match_player_stats_uses_canonical_metric_keys(self):
        payload = {
            "general": {
                "matchId": 1,
                "leagueId": 489,
                "leagueName": "Club Friendlies",
                "matchTimeUTCDate": "2026-08-12T18:30:00Z",
            },
            "content": {
                "playerStats": {
                    "9": {
                        "id": 9,
                        "name": "Forward",
                        "teamId": 10,
                        "teamName": "Club",
                        "isGoalkeeper": False,
                        "stats": [
                            {
                                "title": "Top stats",
                                "stats": {
                                    "Minutes played": {
                                        "key": "minutes_played",
                                        "stat": {"value": 61, "type": "integer"},
                                    },
                                    "Chances created": {
                                        "key": "chances_created",
                                        "stat": {"value": 3, "type": "integer"},
                                    },
                                },
                            }
                        ],
                    }
                }
            },
        }
        rows = flatten_match_player_stats(payload)
        self.assertEqual(rows[0]["metrics"]["minutes_played"]["value"], 61)
        self.assertEqual(rows[0]["metrics"]["chances_created"]["value"], 3)


if __name__ == "__main__":
    unittest.main()
