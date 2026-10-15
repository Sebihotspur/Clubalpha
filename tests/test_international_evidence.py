import unittest

from clubalpha.international_evidence import (
    enrich_player_match,
    is_national_team_competition,
    summarize_player_matches,
)


class InternationalEvidenceTests(unittest.TestCase):
    def test_competition_filter_keeps_national_events_only(self):
        self.assertTrue(
            is_national_team_competition(
                {"ccode": "INT", "name": "UEFA Nations League A Grp. 2"}
            )
        )
        self.assertTrue(
            is_national_team_competition(
                {"ccode": "INT", "name": "EURO U21 Qualification Grp. A"}
            )
        )
        self.assertFalse(
            is_national_team_competition(
                {"ccode": "INT", "name": "Women's Champions League"}
            )
        )
        self.assertFalse(
            is_national_team_competition(
                {"ccode": "ENG", "name": "Premier League"}
            )
        )

    def test_enrichment_and_summary_preserve_club_identity(self):
        fixture = {
            "match_id": 1,
            "home_team_id": 10,
            "home_team": "Nation A",
            "away_team_id": 20,
            "away_team": "Nation B",
            "score": "2 - 1",
        }
        row = {
            "match_id": 1,
            "player_id": 99,
            "player": "Alpha Player",
            "team_id": 10,
            "team": "Nation A",
            "kickoff_utc": "2026-10-01T18:45:00Z",
            "is_starter": True,
            "metrics": {
                "minutes_played": {"value": 90},
                "rating_title": {"value": 8.0},
                "goals": {"value": 1},
                "assists": {"value": 1},
                "chances_created": {"value": 3},
            },
        }
        enriched = enrich_player_match(
            row,
            fixture,
            {"clubs": {"Premier Club"}, "positions": {"FW"}},
        )
        self.assertEqual(enriched["result"], "W")
        self.assertEqual(enriched["opponent"], "Nation B")
        summary = summarize_player_matches([enriched])[0]
        self.assertEqual(summary["covered_clubs"], ["Premier Club"])
        self.assertEqual(summary["minutes"], 90.0)
        self.assertEqual(summary["totals"]["goals"], 1.0)
        self.assertEqual(summary["totals"]["assists"], 1.0)
        self.assertEqual(summary["record"]["wins"], 1)


if __name__ == "__main__":
    unittest.main()

