import unittest

from clubalpha.domestic_history import (
    build_domestic_competitions,
    filter_target_player_rows,
    select_domestic_fixtures,
)


class DomesticHistoryTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "default_season": "2025/2026",
            "included_ucl_statuses": ["direct_league_phase", "playoff_contender"],
            "excluded_league_ids": [47],
            "league_seasons": {"59": "2025"},
            "league_names": {"48": "Championship", "54": "Bundesliga", "59": "Eliteserien"},
            "team_league_overrides": {
                "3": {
                    "league_id": 48,
                    "league_name": "Championship",
                    "season": "2025/2026",
                    "reason": "Promoted",
                }
            },
        }

    def test_registry_excludes_existing_pl_and_applies_promoted_override(self):
        teams = [
            {
                "team_id": 1,
                "name": "English UCL Club",
                "ucl_status": "direct_league_phase",
                "primary_league_id": 47,
                "primary_league": "Premier League",
            },
            {
                "team_id": 2,
                "name": "German Club",
                "ucl_status": "direct_league_phase",
                "primary_league_id": 54,
                "primary_league": "Bundesliga",
            },
            {
                "team_id": 3,
                "name": "Promoted Club",
                "ucl_status": None,
                "primary_league_id": 47,
                "primary_league": "Premier League",
            },
            {
                "team_id": 4,
                "name": "Norwegian Club",
                "ucl_status": "playoff_contender",
                "primary_league_id": 59,
                "primary_league": "Eliteserien",
            },
        ]
        result = build_domestic_competitions(teams, self.config)
        by_id = {row["league_id"]: row for row in result}
        self.assertEqual(set(by_id), {48, 54, 59})
        self.assertEqual(by_id[48]["target_teams"][0]["team_id"], 3)
        self.assertEqual(by_id[59]["season"], "2025")

    def test_fixture_selection_keeps_only_target_club_matches(self):
        payload = {
            "fixtures": {
                "allMatches": [
                    {
                        "id": 10,
                        "home": {"id": 2, "name": "Target"},
                        "away": {"id": 8, "name": "Opponent"},
                        "status": {"finished": True, "utcTime": "2025-08-01T18:00:00Z"},
                    },
                    {
                        "id": 11,
                        "home": {"id": 7, "name": "Other"},
                        "away": {"id": 8, "name": "Opponent"},
                        "status": {"finished": True, "utcTime": "2025-08-02T18:00:00Z"},
                    },
                ]
            }
        }
        competition = {
            "league_id": 54,
            "league_name": "Bundesliga",
            "season": "2025/2026",
            "target_teams": [{"team_id": 2, "team": "Target"}],
        }
        result = select_domestic_fixtures(payload, competition)
        self.assertEqual([row["match_id"] for row in result], [10])
        self.assertEqual(result[0]["competition_id"], 54)

    def test_opponent_rows_are_excluded_from_player_sample(self):
        competition = {
            "league_id": 54,
            "league_name": "Bundesliga",
            "season": "2025/2026",
            "target_teams": [{"team_id": 2, "team": "Target"}],
        }
        rows = [
            {"match_id": 10, "team_id": 2, "player_id": 20, "metrics": {}},
            {"match_id": 10, "team_id": 8, "player_id": 80, "metrics": {}},
        ]
        result = filter_target_player_rows(rows, competition)
        self.assertEqual([row["player_id"] for row in result], [20])
        self.assertEqual(result[0]["source_scope"], "domestic_history_previous")


if __name__ == "__main__":
    unittest.main()
