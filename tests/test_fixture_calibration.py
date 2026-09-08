import copy
import unittest

from clubalpha.fixture_calibration import (
    build_calibration_observations,
    calibrate_fixture_forecast,
    fit_fixture_calibration,
)


CONFIG = {
    "version": "clubalpha_fixture_calibration_v1",
    "status": "shadow_challenger",
    "minimum_training_matches": 4,
    "minimum_validation_matches": 100,
    "xg_floor": 0.15,
    "venue": {
        "prior_match_equivalents": 4.0,
        "maximum_absolute_league_log_ratio_correction": 0.2,
        "team_prior_match_equivalents": 2.0,
        "minimum_team_home_matches": 2,
        "minimum_team_away_matches": 2,
        "maximum_absolute_team_log_ratio_effect": 0.1,
        "maximum_absolute_total_log_ratio_correction": 0.25,
    },
    "draw": {
        "prior_match_equivalents": 4.0,
        "maximum_absolute_logit_correction": 0.75,
        "draw_zone_max_probability_gap": 0.08,
        "draw_zone_max_side_probability": 0.5,
    },
    "simulation": {
        "draws": 5000,
        "seed": 77,
        "totals_lines": [2.5, 3.5],
    },
    "locked_boundaries": {
        "player_alpha_formulas_mutable": False,
        "base_60_30_10_weights_mutable": False,
        "frozen_predictions_mutable": False,
        "automatic_capital_authorization_allowed": False,
    },
}


def contextual_prediction(index):
    home_id, away_id = (1, 2) if index % 2 == 0 else (2, 1)
    return {
        "fixture": {
            "match_id": 100 + index,
            "kickoff_utc": f"2026-09-0{index + 1}T14:00:00Z",
            "home_team_id": home_id,
            "home_team": f"Team {home_id}",
            "away_team_id": away_id,
            "away_team": f"Team {away_id}",
        },
        "contextual": {
            "predicted_xg": {"home": 1.8, "away": 1.2, "total": 3.0},
            "probabilities": {
                "home_win": 0.51,
                "draw": 0.23,
                "away_win": 0.26,
            },
        },
    }


def result(index):
    prediction = contextual_prediction(index)
    fixture = prediction["fixture"]
    draw = index in {0, 1, 2, 3}
    return {
        "match_id": fixture["match_id"],
        "kickoff_utc": fixture["kickoff_utc"],
        "actual_xg": {"home": 1.0, "away": 1.3, "total": 2.3},
        "outcome": "draw" if draw else "away_win",
    }


class FixtureCalibrationTests(unittest.TestCase):
    def observations(self):
        predictions = [contextual_prediction(index) for index in range(8)]
        results = [result(index) for index in range(8)]
        return build_calibration_observations(predictions, results)

    def test_fit_reduces_observed_home_bias_and_lifts_draw_rate(self):
        artifact = fit_fixture_calibration(
            self.observations(), CONFIG, as_of="2026-09-08"
        )
        self.assertLess(
            artifact["league_venue"]["applied_log_ratio_correction"], 0
        )
        self.assertGreater(
            artifact["draw_calibration"]["applied_logit_correction"], 0
        )
        self.assertEqual(artifact["training_matches"], 8)
        self.assertTrue(
            artifact["decision_boundaries"]["team_venue_modifiers_active"]
        )
        self.assertFalse(
            artifact["decision_boundaries"]["probability_validated"]
        )

    def test_application_is_deterministic_and_preserves_locked_layers(self):
        artifact = fit_fixture_calibration(
            self.observations(), CONFIG, as_of="2026-09-08"
        )
        future = {
            "fixture": {
                "match_id": 999,
                "kickoff_utc": "2026-09-12T14:00:00Z",
                "home_team_id": 1,
                "home_team": "Team 1",
                "away_team_id": 2,
                "away_team": "Team 2",
            },
            "predicted_xg": {"home": 1.8, "away": 1.2, "total": 3.0},
            "probabilities": {
                "home_win": 0.51,
                "draw": 0.23,
                "away_win": 0.26,
            },
        }
        first = calibrate_fixture_forecast(future, artifact, CONFIG)
        second = calibrate_fixture_forecast(future, artifact, CONFIG)
        self.assertEqual(first, second)
        before_ratio = 1.8 / 1.2
        after_ratio = first["predicted_xg"]["home"] / first["predicted_xg"]["away"]
        self.assertLess(after_ratio, before_ratio)
        self.assertGreater(first["probabilities"]["draw"], 0.23)
        self.assertLessEqual(
            abs(
                sum(
                    first["probabilities"][key]
                    for key in ("home_win", "draw", "away_win")
                )
                - 1.0
            ),
            1e-9,
        )
        self.assertFalse(
            first["decision_boundaries"]["base_60_30_10_changed"]
        )
        self.assertFalse(first["decision_boundaries"]["player_alpha_changed"])
        self.assertFalse(
            first["decision_boundaries"]["capital_deployment_ready"]
        )

    def test_team_venue_effect_waits_for_both_venue_samples(self):
        config = copy.deepcopy(CONFIG)
        config["venue"]["minimum_team_home_matches"] = 5
        config["venue"]["minimum_team_away_matches"] = 5
        artifact = fit_fixture_calibration(
            self.observations(), config, as_of="2026-09-08"
        )
        self.assertFalse(
            artifact["decision_boundaries"]["team_venue_modifiers_active"]
        )
        self.assertTrue(
            all(not row["eligible"] for row in artifact["team_venue_modifiers"])
        )

    def test_application_rejects_lookahead(self):
        artifact = fit_fixture_calibration(
            self.observations(), CONFIG, as_of="2026-09-08"
        )
        future = {
            "fixture": {
                "match_id": 999,
                "kickoff_utc": "2026-09-08T14:00:00Z",
                "home_team_id": 1,
                "home_team": "Team 1",
                "away_team_id": 2,
                "away_team": "Team 2",
            },
            "predicted_xg": {"home": 1.8, "away": 1.2, "total": 3.0},
            "probabilities": {
                "home_win": 0.51,
                "draw": 0.23,
                "away_win": 0.26,
            },
        }
        with self.assertRaisesRegex(ValueError, "must predate"):
            calibrate_fixture_forecast(future, artifact, CONFIG)

    def test_config_cannot_unlock_player_alpha(self):
        config = copy.deepcopy(CONFIG)
        config["locked_boundaries"]["player_alpha_formulas_mutable"] = True
        with self.assertRaisesRegex(ValueError, "weakens a locked boundary"):
            fit_fixture_calibration(self.observations(), config, as_of="2026-09-08")


if __name__ == "__main__":
    unittest.main()
