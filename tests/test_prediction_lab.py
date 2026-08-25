import unittest
from datetime import date

from clubalpha.prediction_lab import (
    build_prediction_slate,
    fit_component_scale_artifact,
    fit_goal_model_artifact,
    scaled_fixture_signals,
)
from research.aug24_shadow_test import reconstruct_squads_to_as_of


CONFIG = {
    "version": "prediction-test-v0",
    "component_scaling": {
        "artifact_version": "scales-test-v0",
        "method": "past_only_training_standard_deviation",
        "minimum_training_fixture_sides": 4,
        "minimum_validation_fixture_sides": 20,
    },
    "goal_model": {
        "artifact_version": "goal-test-v0",
        "method": "ridge_log_xg_adjustment_without_intercept",
        "target": "observed_fotmob_expected_goals",
        "observed_xg_floor": 0.05,
        "ridge_lambda": 0.5,
        "small_sample_coefficient_policy": "bootstrap_95_bound_closest_to_zero",
        "minimum_shadow_training_matches": 2,
        "minimum_validation_matches": 100,
        "predicted_xg_bounds": {"minimum": 0.05, "maximum": 5.0},
        "bootstrap": {"samples": 200, "seed": 7},
    },
    "simulation": {
        "draws": 2000,
        "distribution": "independent_poisson",
        "seed": 11,
        "totals_lines": [2.5, 3.5],
    },
}


def state(match_id, as_of, kickoff, home_values, away_values):
    components = (
        "club_form",
        "player_quality_lineup",
        "historical_residual",
    )

    def side(values):
        return {
            "components": {
                component: {
                    "effective_signal_z": value,
                    "confidence": 0.5,
                }
                for component, value in zip(components, values)
            }
        }

    return {
        "fixture_state_version": "fixture-test-v1",
        "as_of": as_of,
        "fixture": {
            "match_id": match_id,
            "kickoff_utc": kickoff,
            "home_team_id": 1,
            "home_team": "Home",
            "away_team_id": 2,
            "away_team": "Away",
            "source_scope": "premier_league_current",
        },
        "component_weights": {
            "club_form": 0.6,
            "player_quality_lineup": 0.3,
            "historical_residual": 0.1,
        },
        "home": side(home_values),
        "away": side(away_values),
        "goal_model_handoff": {
            "competition_baseline": {"home_xg": 1.5, "away_xg": 1.2}
        },
        "decision_boundaries": {
            "raw_components_ready_for_scale_fitting": True
        },
    }


class PredictionLabTests(unittest.TestCase):
    def scale_training_states(self):
        return [
            state(
                1,
                "2026-08-17",
                "2026-08-21T19:00:00Z",
                (1.0, 0.5, 0.25),
                (-1.0, -0.5, -0.25),
            ),
            state(
                2,
                "2026-08-17",
                "2026-08-22T14:00:00Z",
                (0.5, -0.25, 0.1),
                (-0.5, 0.25, -0.1),
            ),
        ]

    def goal_training_states(self):
        rows = self.scale_training_states()
        for row in rows:
            row["as_of"] = "2026-08-18"
        return rows

    def test_scale_artifact_is_dated_and_uses_no_outcomes(self):
        artifact = fit_component_scale_artifact(self.scale_training_states(), CONFIG)
        self.assertEqual(artifact["trained_through"], "2026-08-17")
        self.assertEqual(artifact["training_fixture_sides"], 4)
        self.assertFalse(artifact["outcomes_used"])
        self.assertFalse(artifact["decision_boundaries"]["scale_validated"])
        self.assertTrue(all(value > 0 for value in artifact["scales"].values()))

    def test_goal_model_uses_only_pre_match_states_and_stays_shadow_only(self):
        states = self.goal_training_states()
        scales = fit_component_scale_artifact(self.scale_training_states(), CONFIG)
        artifact = fit_goal_model_artifact(
            states,
            [
                {"match_id": 1, "home_xg": 2.0, "away_xg": 0.8},
                {"match_id": 2, "home_xg": 1.7, "away_xg": 1.0},
            ],
            scales,
            CONFIG,
            trained_through="2026-08-24",
        )
        self.assertGreater(artifact["coefficient"], 0)
        self.assertLessEqual(artifact["coefficient"], artifact["point_coefficient"])
        self.assertEqual(artifact["training_matches"], 2)
        self.assertEqual(
            artifact["training_fixture_state_as_of_dates"], ["2026-08-18"]
        )
        self.assertTrue(
            artifact["decision_boundaries"]["shadow_prediction_ready"]
        )
        self.assertFalse(
            artifact["decision_boundaries"]["probability_validated"]
        )

    def test_goal_model_rejects_a_state_not_frozen_before_kickoff(self):
        states = self.goal_training_states()
        states[0]["as_of"] = "2026-08-21"
        scale_states = self.scale_training_states()
        scales = fit_component_scale_artifact(scale_states, CONFIG)
        with self.assertRaisesRegex(ValueError, "must predate fixture kickoff"):
            fit_goal_model_artifact(
                states,
                [
                    {"match_id": 1, "home_xg": 2.0, "away_xg": 0.8},
                    {"match_id": 2, "home_xg": 1.7, "away_xg": 1.0},
                ],
                scales,
                CONFIG,
                trained_through="2026-08-24",
            )

    def test_simulation_is_deterministic_and_probabilities_reconcile(self):
        states = self.goal_training_states()
        scales = fit_component_scale_artifact(self.scale_training_states(), CONFIG)
        goal_model = fit_goal_model_artifact(
            states,
            [
                {"match_id": 1, "home_xg": 2.0, "away_xg": 0.8},
                {"match_id": 2, "home_xg": 1.7, "away_xg": 1.0},
            ],
            scales,
            CONFIG,
            trained_through="2026-08-24",
        )
        future = state(
            3,
            "2026-08-24",
            "2026-08-28T19:00:00Z",
            (0.75, 0.2, 0.1),
            (-0.4, -0.1, -0.05),
        )
        first = build_prediction_slate([future], scales, goal_model, CONFIG)[0]
        second = build_prediction_slate([future], scales, goal_model, CONFIG)[0]
        self.assertEqual(first, second)
        result = first["probabilities"]
        self.assertAlmostEqual(
            result["home_win"] + result["draw"] + result["away_win"],
            1.0,
            places=6,
        )
        self.assertAlmostEqual(
            result["over"]["2.5"] + result["under"]["2.5"],
            1.0,
            places=6,
        )
        self.assertFalse(first["decision_boundaries"]["market_ready"])

    def test_prediction_scales_must_predate_snapshot(self):
        scale_states = self.scale_training_states()
        scales = fit_component_scale_artifact(scale_states, CONFIG)
        with self.assertRaisesRegex(ValueError, "must predate"):
            scaled_fixture_signals(scale_states[0], scales)

    def test_prediction_rejects_mismatched_scale_artifact(self):
        states = self.goal_training_states()
        scales = fit_component_scale_artifact(self.scale_training_states(), CONFIG)
        goal_model = fit_goal_model_artifact(
            states,
            [
                {"match_id": 1, "home_xg": 2.0, "away_xg": 0.8},
                {"match_id": 2, "home_xg": 1.7, "away_xg": 1.0},
            ],
            scales,
            CONFIG,
            trained_through="2026-08-24",
        )
        scales["version"] = "wrong-scale"
        future = state(
            3,
            "2026-08-24",
            "2026-08-28T19:00:00Z",
            (0.75, 0.2, 0.1),
            (-0.4, -0.1, -0.05),
        )
        with self.assertRaisesRegex(ValueError, "versions differ"):
            build_prediction_slate([future], scales, goal_model, CONFIG)

    def test_goal_model_rejects_negative_xg(self):
        states = self.goal_training_states()
        scales = fit_component_scale_artifact(self.scale_training_states(), CONFIG)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            fit_goal_model_artifact(
                states,
                [
                    {"match_id": 1, "home_xg": -0.1, "away_xg": 0.8},
                    {"match_id": 2, "home_xg": 1.7, "away_xg": 1.0},
                ],
                scales,
                CONFIG,
                trained_through="2026-08-24",
            )

    def test_historical_roster_reconstruction_reverses_later_transfers(self):
        teams = [
            {"team_id": 1, "name": "Alpha", "premier_league_2026_27": True},
            {"team_id": 2, "name": "Other", "premier_league_2026_27": False},
        ]
        squads = [
            {
                "team_id": 1,
                "team": "Alpha",
                "player_id": 10,
                "player": "Later Arrival",
                "position": "ST",
                "squad_group": "attackers",
                "injury": {"expectedReturn": "2026-09-01"},
            },
            {
                "team_id": 1,
                "team": "Alpha",
                "player_id": 30,
                "player": "Always There",
                "position": "CM",
                "squad_group": "midfielders",
                "injury": {"expectedReturn": "unknown"},
            },
        ]
        events = [
            {
                "team_id": 1,
                "team": "Alpha",
                "player_id": 10,
                "player": "Later Arrival",
                "position": "ST",
                "direction": "in",
                "effective_date": "2026-08-12",
            },
            {
                "team_id": 1,
                "team": "Alpha",
                "player_id": 20,
                "player": "Later Departure",
                "position": "CB",
                "direction": "out",
                "effective_date": "2026-08-13",
            },
            {
                "team_id": 1,
                "team": "Alpha",
                "player_id": 40,
                "player": "Cutoff Arrival",
                "position": "RW",
                "direction": "in",
                "effective_date": "2026-08-11",
            },
        ]
        reconstructed, provenance = reconstruct_squads_to_as_of(
            squads, teams, events, date(2026, 8, 11)
        )
        player_ids = {row["player_id"] for row in reconstructed}
        self.assertNotIn(10, player_ids)
        self.assertIn(20, player_ids)
        self.assertIn(30, player_ids)
        self.assertTrue(all(row.get("injury") is None for row in reconstructed))
        self.assertEqual(provenance["later_transfer_events_reversed"], 2)


if __name__ == "__main__":
    unittest.main()
