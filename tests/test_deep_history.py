import unittest

from clubalpha.deep_history import (
    competition_seasons,
    dedupe_fixtures,
    normalize_season_fixtures,
)
from clubalpha.fotmob import flatten_match_team_stats


class DeepHistoryTests(unittest.TestCase):
    def test_competition_registry_expands_every_season(self):
        config = {
            "competitions": [
                {
                    "key": "premier_league",
                    "name": "Premier League",
                    "fotmob_id": 47,
                    "seasons": ["2024/2025", "2025/2026"],
                }
            ]
        }
        result = competition_seasons(config)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["source_scope"], "premier_league_history_2024_2025")

    def test_season_registry_rejects_silent_provider_fallback(self):
        payload = {"details": {"selectedSeason": "2025/2026"}, "fixtures": {}}
        competition = {
            "key": "premier_league",
            "name": "Premier League",
            "fotmob_id": 47,
            "season": "2024/2025",
            "source_scope": "premier_league_history_2024_2025",
        }
        with self.assertRaises(RuntimeError):
            normalize_season_fixtures(payload, competition, "2026-08-18")

    def test_only_finished_pre_as_of_fixtures_are_collected(self):
        payload = {
            "details": {"selectedSeason": "2025/2026"},
            "fixtures": {
                "allMatches": [
                    {
                        "id": 1,
                        "home": {"id": 10, "name": "Home"},
                        "away": {"id": 20, "name": "Away"},
                        "status": {
                            "utcTime": "2026-05-01T19:00:00Z",
                            "finished": True,
                            "scoreStr": "2 - 1",
                        },
                    },
                    {
                        "id": 2,
                        "home": {"id": 10, "name": "Home"},
                        "away": {"id": 20, "name": "Away"},
                        "status": {
                            "utcTime": "2026-08-19T19:00:00Z",
                            "finished": True,
                            "scoreStr": "1 - 0",
                        },
                    },
                    {
                        "id": 3,
                        "home": {"id": 10, "name": "Home"},
                        "away": {"id": 20, "name": "Away"},
                        "status": {
                            "utcTime": "2026-05-02T19:00:00Z",
                            "finished": True,
                            "cancelled": True,
                            "scoreStr": "1 - 1",
                        },
                    },
                ]
            },
        }
        competition = {
            "key": "premier_league",
            "name": "Premier League",
            "fotmob_id": 47,
            "season": "2025/2026",
            "source_scope": "premier_league_history_2025_2026",
        }
        result = normalize_season_fixtures(payload, competition, "2026-08-18")
        self.assertEqual([row["match_id"] for row in result], [1])
        self.assertEqual(result[0]["season"], "2025/2026")

    def test_team_match_normalization_preserves_season(self):
        fixture = {
            "match_id": 1,
            "source_scope": "premier_league_history_2025_2026",
            "competition_id": 47,
            "competition": "Premier League",
            "season": "2025/2026",
            "kickoff_utc": "2026-05-01T19:00:00Z",
            "home_team_id": 10,
            "home_team": "Home",
            "away_team_id": 20,
            "away_team": "Away",
            "score": "2 - 1",
        }
        rows = flatten_match_team_stats({}, fixture)
        self.assertEqual({row["season"] for row in rows}, {"2025/2026"})

    def test_fixture_dedupe_is_stable_by_match_id(self):
        first = {"match_id": 1, "kickoff_utc": "2026-01-01", "season": "old"}
        replacement = {"match_id": 1, "kickoff_utc": "2026-01-01", "season": "new"}
        result = dedupe_fixtures([[first], [replacement]])
        self.assertEqual(result, [replacement])


if __name__ == "__main__":
    unittest.main()
