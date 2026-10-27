import unittest
from unittest.mock import patch

from research.current_premier_league_alpha import (
    collect_shared_selection_rows,
    merge_current_selection_rows,
)
from research.build_current_matchweek_v1 import lineup_inputs


def row(match_id, team_id=10, competition_id=47, kickoff="2026-09-12T14:00:00Z"):
    return {
        "match_id": match_id,
        "team_id": team_id,
        "player_id": 100,
        "competition_id": competition_id,
        "kickoff_utc": kickoff,
        "is_starter": True,
        "metrics": {"minutes_played": {"value": 90}},
    }


class CurrentSelectionEvidenceTests(unittest.TestCase):
    def test_unrated_foreign_xi_is_neutral_not_negative(self):
        quality, confidence = lineup_inputs(
            {
                "alpha": {
                    "overall_alpha_ability": {"z": None, "coverage": 0.0}
                },
                "evidence": {"weighted_matches": 5.0},
            }
        )
        self.assertEqual(quality, 0.0)
        self.assertEqual(confidence, 0.0)

    def test_supplementary_collection_is_past_only_and_deduplicated(self):
        fixtures = [
            {**row(1, competition_id=133), "finished": True},
            {**row(2), "finished": True},
            {**row(3, competition_id=42), "finished": True},
            {**row(4, competition_id=489), "finished": True},
            {**row(5, competition_id=133), "finished": False},
            {**row(6, competition_id=133, kickoff="2026-09-16T19:00:00Z"), "finished": True},
            {**row(7, competition_id=133, kickoff="2025-09-12T19:00:00Z"), "finished": True},
        ]

        class Client:
            fetched = []

            def team(self, team_id):
                return fixtures

            def match(self, match_id):
                self.fetched.append(match_id)
                return {}

        client = Client()
        with (
            patch("research.current_premier_league_alpha.team_fixtures", side_effect=lambda p: p),
            patch("research.current_premier_league_alpha.normalize_fixture", side_effect=lambda f, **kw: f),
            patch("research.current_premier_league_alpha.flatten_match_player_stats", side_effect=lambda p, f: [f]),
        ):
            result = collect_shared_selection_rows(client, {10, 20}, "2026-09-15", "2026-07-01")
        self.assertEqual(client.fetched, [1])
        self.assertEqual([r["match_id"] for r in result], [1])

    def test_includes_european_appearances_and_preserves_competition(self):
        european = row(2, competition_id=42, kickoff="2026-09-09T19:00:00Z")
        result = merge_current_selection_rows([european], [row(1)], {10}, "2026-09-15")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["competition_id"], 42)
        self.assertEqual(result[1]["selection_source"], "current_season")

    def test_fresh_pl_copy_wins_without_double_counting(self):
        cached = row(1)
        fresh = {**cached, "is_starter": False}
        result = merge_current_selection_rows([cached], [fresh], {10}, "2026-09-15")
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["is_starter"])

    def test_excludes_other_teams_future_and_undated_evidence(self):
        rows = [
            row(1, team_id=20),
            row(2, kickoff="2026-09-16T19:00:00Z"),
            row(3, kickoff=""),
            row(4, kickoff="2026-09-15T19:00:00Z"),
        ]
        result = merge_current_selection_rows(rows, [], {10}, "2026-09-15")
        self.assertEqual([r["match_id"] for r in result], [4])


if __name__ == "__main__":
    unittest.main()
