import unittest

from clubalpha.fotmob import (
    clip_fixture_to_as_of,
    flatten_match_player_stats,
    flatten_match_team_stats,
    normalize_fixture,
    normalize_manager_history,
    normalize_name,
    normalize_stat_rows,
    normalize_team_snapshot,
    normalize_transfer_events,
    team_squad,
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

    def test_future_fixture_snapshot_does_not_leak_a_later_result(self):
        row = {
            "kickoff_utc": "2026-08-25T19:00:00Z",
            "score": "3 - 0",
            "started": True,
            "finished": True,
            "cancelled": False,
        }
        result = clip_fixture_to_as_of(row, "2026-08-18")
        self.assertIsNone(result["score"])
        self.assertFalse(result["started"])
        self.assertFalse(result["finished"])

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
                "lineup": {
                    "source": "provider",
                    "homeTeam": {
                        "formation": "4-3-3",
                        "starters": [{"id": 9, "positionId": 105}],
                        "subs": [],
                    },
                },
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
                    },
                    "placeholder": {
                        "id": 0,
                        "name": "Unavailable player",
                        "stats": [],
                    },
                }
            },
        }
        rows = flatten_match_player_stats(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metrics"]["minutes_played"]["value"], 61)
        self.assertEqual(rows[0]["metrics"]["chances_created"]["value"], 3)
        self.assertTrue(rows[0]["is_starter"])
        self.assertEqual(rows[0]["lineup_position_id"], 105)
        self.assertEqual(rows[0]["team_formation"], "4-3-3")
        self.assertEqual(rows[0]["lineup_source"], "provider")

    def test_missing_lineup_remains_unknown_instead_of_inferred_from_minutes(self):
        payload = {
            "general": {"matchId": 1, "leagueId": 47, "leagueName": "Premier League"},
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
                                "stats": {
                                    "Minutes played": {
                                        "key": "minutes_played",
                                        "stat": {"value": 90, "type": "integer"},
                                    }
                                }
                            }
                        ],
                    }
                }
            },
        }
        row = flatten_match_player_stats(payload)[0]
        self.assertIsNone(row["is_starter"])
        self.assertIsNone(row["lineup_position_id"])
        self.assertIsNone(row["team_formation"])

    def test_decorated_team_stats_preserve_counts_rates_and_attempt_proxies(self):
        payload = {
            "content": {
                "stats": {
                    "Periods": {
                        "All": {
                            "stats": [
                                {
                                    "stats": [
                                        {"key": "passes", "stats": [531, 258]},
                                        {"key": "accurate_passes", "stats": ["460 (87%)", "183 (71%)"]},
                                        {"key": "long_balls_accurate", "stats": ["22 (46%)", "22 (40%)"]},
                                        {"key": "accurate_crosses", "stats": ["9 (24%)", "3 (20%)"]},
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }
        fixture = {
            "match_id": 1,
            "home_team_id": 10,
            "home_team": "Home",
            "away_team_id": 20,
            "away_team": "Away",
            "score": "1 - 0",
        }
        home = flatten_match_team_stats(payload, fixture)[0]
        self.assertEqual(home["accurate_passes_for"], 460)
        self.assertEqual(home["pass_accuracy_pct_for"], 87)
        self.assertAlmostEqual(home["long_balls_attempted_est_for"], 47.8261, places=3)
        self.assertEqual(home["crosses_attempted_est_for"], 37.5)

    def test_team_page_normalizes_manager_history_and_confirmed_transfers(self):
        payload = {
            "squad": {
                "squad": [
                    {"title": "coach", "members": [{"id": 7, "name": "Coach", "excludeFromRanking": True}]},
                    {
                        "title": "attackers",
                        "members": [
                            {"id": 9, "name": "Forward"},
                            {
                                "id": 10,
                                "name": "Unranked Forward",
                                "excludeFromRanking": True,
                            },
                        ],
                    },
                ]
            },
            "history": {
                "coachHistory": [
                    {"id": 6, "name": "Prior", "season": "2025/2026", "leagueId": 47, "win": 10, "draw": 5, "loss": 5}
                ]
            },
            "transfers": {
                "data": {
                    "Players in": [
                        {
                            "playerId": 9,
                            "name": "Forward",
                            "position": {"label": "ST"},
                            "fromDate": "2026-07-01T00:00:00Z",
                            "transferDate": "2026-06-20T10:00:00Z",
                            "fromClubId": 30,
                            "fromClubFullName": "Other",
                            "transferType": {"text": "contract"},
                            "fee": {"value": 100},
                        }
                    ],
                    "Players out": [],
                }
            },
        }
        snapshot = normalize_team_snapshot(payload, team_id=10, team="Club", snapshot_date="2026-08-18")
        history = normalize_manager_history(payload, team_id=10, team="Club")
        transfers = normalize_transfer_events(payload, team_id=10, team="Club")
        self.assertEqual(snapshot["current_coach"]["coach_id"], 7)
        self.assertEqual(snapshot["squad_player_ids"], [9, 10])
        self.assertEqual(
            [member["id"] for member in team_squad(payload)],
            [9, 10],
        )
        self.assertEqual(history[0]["coach_id"], 6)
        self.assertEqual(transfers[0]["effective_date"], "2026-07-01")
        self.assertEqual(transfers[0]["counterparty_id"], 30)

    def test_match_shotmap_derives_reconciled_non_penalty_goals(self):
        payload = {
            "general": {"matchId": 1, "leagueId": 47, "leagueName": "Premier League"},
            "content": {
                "playerStats": {
                    "9": {
                        "id": 9,
                        "name": "Forward",
                        "teamId": 10,
                        "teamName": "Club",
                        "stats": [
                            {
                                "stats": {
                                    "Goals": {
                                        "key": "goals",
                                        "stat": {"value": 2, "type": "integer"},
                                    }
                                }
                            }
                        ],
                    }
                },
                "shotmap": {
                    "shots": [
                        {
                            "eventType": "Goal",
                            "playerId": 9,
                            "situation": "RegularPlay",
                            "period": "FirstHalf",
                            "isOwnGoal": False,
                        },
                        {
                            "eventType": "Goal",
                            "playerId": 9,
                            "situation": "Penalty",
                            "period": "SecondHalf",
                            "isOwnGoal": False,
                        },
                    ]
                },
            },
        }
        rows = flatten_match_player_stats(payload)
        self.assertEqual(rows[0]["metrics"]["non_penalty_goals"]["value"], 1)
        self.assertEqual(
            rows[0]["metrics"]["non_penalty_goals"]["derived_from"],
            "shotmap",
        )

    def test_match_events_fill_non_penalty_goals_when_shotmap_is_empty(self):
        payload = {
            "general": {"matchId": 1, "leagueId": 127, "leagueName": "League"},
            "content": {
                "playerStats": {
                    "9": {
                        "id": 9,
                        "name": "Forward",
                        "teamId": 10,
                        "teamName": "Club",
                        "stats": [
                            {
                                "stats": {
                                    "Goals": {
                                        "key": "goals",
                                        "stat": {"value": 2, "type": "integer"},
                                    }
                                }
                            }
                        ],
                    }
                },
                "shotmap": {"shots": []},
                "matchFacts": {
                    "events": {
                        "events": [
                            {
                                "type": "Goal",
                                "playerId": 9,
                                "ownGoal": None,
                                "isPenaltyShootoutEvent": False,
                                "goalDescriptionKey": None,
                            },
                            {
                                "type": "Goal",
                                "playerId": 9,
                                "ownGoal": None,
                                "isPenaltyShootoutEvent": False,
                                "goalDescriptionKey": "penalty",
                            },
                        ]
                    }
                },
            },
        }
        rows = flatten_match_player_stats(payload)
        self.assertEqual(rows[0]["metrics"]["non_penalty_goals"]["value"], 1)
        self.assertEqual(
            rows[0]["metrics"]["non_penalty_goals"]["derived_from"],
            "match_events",
        )


if __name__ == "__main__":
    unittest.main()
