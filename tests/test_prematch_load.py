import unittest

from clubalpha.prematch_load import classify_load_risk


class PrematchLoadTests(unittest.TestCase):
    def test_pending_match_is_high_risk(self):
        risk, flags = classify_load_risk(
            {
                "pending_preleague_fixture": {"match_id": 1},
                "rest_days": 5,
                "projected_xi_latest_match_load_share": 0.2,
                "player_alpha_coverage": 0.95,
            }
        )
        self.assertEqual(risk, "high")
        self.assertIn("pending_preleague_fixture", flags)

    def test_rotated_cup_lineup_is_medium_without_short_rest(self):
        risk, flags = classify_load_risk(
            {
                "rest_days": 4.5,
                "competition_switch": True,
                "projected_xi_starter_overlap": 5,
                "projected_xi_latest_match_load_share": 0.4,
                "player_alpha_coverage": 0.95,
            }
        )
        self.assertEqual(risk, "medium")
        self.assertIn("rotated_cross_competition_lineup", flags)

    def test_short_rest_and_heavy_load_is_high(self):
        risk, _ = classify_load_risk(
            {
                "rest_days": 3.0,
                "competition_switch": False,
                "projected_xi_starter_overlap": 9,
                "projected_xi_latest_match_load_share": 0.8,
                "player_alpha_coverage": 0.95,
            }
        )
        self.assertEqual(risk, "high")

    def test_heavy_international_load_and_short_recovery_is_high(self):
        risk, flags = classify_load_risk(
            {
                "rest_days": 18.0,
                "projected_xi_latest_match_load_share": 0.0,
                "player_alpha_coverage": 0.95,
                "international_projected_xi_players_180_plus": 5,
                "international_projected_xi_players_270_plus": 3,
                "international_min_recovery_days": 3.75,
            }
        )
        self.assertEqual(risk, "high")
        self.assertIn("heavy_international_projected_xi_load", flags)
        self.assertIn("compressed_international_recovery", flags)

    def test_international_load_without_compressed_recovery_is_medium(self):
        risk, flags = classify_load_risk(
            {
                "rest_days": 12.0,
                "projected_xi_latest_match_load_share": 0.0,
                "player_alpha_coverage": 0.95,
                "international_projected_xi_players_180_plus": 4,
                "international_projected_xi_players_270_plus": 1,
                "international_min_recovery_days": 6.0,
            }
        )
        self.assertEqual(risk, "medium")
        self.assertIn("heavy_international_projected_xi_load", flags)


if __name__ == "__main__":
    unittest.main()
