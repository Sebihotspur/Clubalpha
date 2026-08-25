import unittest

from clubalpha.role_aware_alpha import attach_role_aware_alpha, build_role_aware_alpha


def grade(player_id, scoring_position, alpha, metric_values, minutes=1800):
    return {
        "player_id": player_id,
        "player": f"Player {player_id}",
        "scoring_position": scoring_position,
        "minutes": minutes,
        "alpha_ability_z": alpha,
        "shrinkage_weight": minutes / (minutes + 900),
        "metrics": {key: {"z": value} for key, value in metric_values.items()},
    }


class RoleAwareAlphaTests(unittest.TestCase):
    def setUp(self):
        self.grades = [
            grade(1, "FW", 1.5, {"npg90": 2.0, "xg90": 1.0, "kp90": 0.5, "axa90": 1.0, "press90": 1.0}),
            grade(2, "FW", -0.5, {"npg90": -1.0, "xg90": -0.5, "kp90": -1.0, "axa90": -0.5, "press90": -0.5}),
            grade(3, "CB", 1.0, {"err90": 1.0, "aer": 1.5, "tkl90": 0.5, "int90": 1.0, "ga90": 0.1}),
            grade(4, "CB", -1.0, {"err90": -1.0, "aer": -0.5, "tkl90": -1.0, "int90": -0.5, "ga90": -0.1}),
        ]

    def test_expected_minutes_weight_role_outputs(self):
        projected = [
            {"player_id": 1, "player": "Player 1", "selection_role": "FWD", "expected_minutes": 90},
            {"player_id": 2, "player": "Player 2", "selection_role": "FWD", "expected_minutes": 30},
            {"player_id": 3, "player": "Player 3", "selection_role": "DEF", "expected_minutes": 90},
            {"player_id": 4, "player": "Player 4", "selection_role": "DEF", "expected_minutes": 30},
        ]
        result = build_role_aware_alpha(self.grades, projected)
        self.assertGreater(result["team_aggregates"]["scoring_threat"]["z"], 0)
        self.assertGreater(result["team_aggregates"]["defensive_prevention"]["z"], 0)
        self.assertGreater(result["team_aggregates"]["attacking_unit_alpha_ability"]["z"], 0)
        self.assertTrue(result["decision_boundaries"]["uses_fixture_expected_minutes"])

    def test_missing_grade_reduces_coverage_instead_of_becoming_zero(self):
        projected = [
            {"player_id": 1, "selection_role": "FWD", "expected_minutes": 60},
            {"player_id": 99, "selection_role": "FWD", "expected_minutes": 30},
        ]
        result = build_role_aware_alpha(self.grades, projected)
        self.assertEqual(result["team_aggregates"]["overall_alpha_ability"]["coverage"], 0.6667)
        missing = next(row for row in result["players"] if row["player_id"] == 99)
        self.assertFalse(missing["alpha_available"])

    def test_locked_headline_grade_is_passed_through_unchanged(self):
        result = build_role_aware_alpha(
            self.grades,
            [{"player_id": 1, "selection_role": "FWD", "expected_minutes": 90}],
        )
        player = result["players"][0]
        self.assertEqual(player["alpha_ability_z"], 1.5)
        self.assertFalse(result["decision_boundaries"]["changes_locked_alpha_ability"])
        self.assertFalse(result["decision_boundaries"]["used_to_select_players"])

    def test_attachment_does_not_change_frozen_xi(self):
        projection = {
            "predicted_starting_xi": [{"player_id": 1}],
            "players": [
                {"player_id": 1, "selection_role": "FWD", "expected_minutes": 90},
                {"player_id": 2, "selection_role": "FWD", "expected_minutes": 20},
            ],
        }
        result = attach_role_aware_alpha(projection, self.grades)
        self.assertEqual(result["predicted_starting_xi"], [{"player_id": 1}])
        self.assertIn("role_aware_alpha", result)
        self.assertEqual(result["players"][0]["alpha_ability_z"], 1.5)


if __name__ == "__main__":
    unittest.main()
