import copy
import unittest

from clubalpha.contextual_interaction import (
    contextualize_prediction,
    directional_context,
    simulate_expected_goals,
)


CONFIG = {
    "version": "test-context-v1",
    "status": "shadow",
    "channel_evidence_reliability": {
        "measured": 1.0,
        "partial": 0.7,
        "hypothesis": 0.45,
    },
    "projected_xi_confidence": {"high": 1.0, "medium": 0.75, "low": 0.5},
    "route_preference_temperature": 1.0,
    "signal_saturation_z": 0.35,
    "maximum_absolute_log_xg_adjustment": 0.1,
    "simulation": {"draws": 5000, "totals_lines": [2.5, 3.5]},
    "display_thresholds": {"probability_change": 0.01, "total_xg_change": 0.03},
    "decision_boundaries": {
        "archetype_label_used_in_math": False,
        "base_60_30_10_modified": False,
        "coefficient_learned_from_residuals": False,
        "probability_validated": False,
        "market_ready": False,
        "capital_deployment_ready": False,
    },
}


def profile(
    team,
    *,
    route=0.0,
    exposure=0.0,
    confidence="high",
    archetype="Label",
):
    channels = (
        "box_pressure",
        "set_pieces",
        "wide_delivery",
        "high_press",
        "direct_transition",
    )
    return {
        "team": team,
        "archetype": archetype,
        "route_expression": {key: route for key in channels},
        "opponent_exposure": {key: exposure for key in channels},
        "projected_xi": {
            "scoring_threat": 0.0,
            "chance_creation": 0.0,
            "defensive_prevention": 0.0,
            "grade_confidence": confidence,
        },
        "quality_flags": [],
    }


def baseline():
    simulation = simulate_expected_goals(
        1.5, 1.0, draws=5000, totals_lines=[2.5, 3.5], seed=77
    )
    return {
        "prediction_version": "base-v1",
        "fixture": {
            "match_id": 10,
            "kickoff_utc": "2026-08-30T15:00:00Z",
            "home_team": "Home",
            "away_team": "Away",
        },
        "predicted_xg": {"home": 1.5, "away": 1.0, "total": 2.5},
        "probabilities": simulation["probabilities"],
        "simulation": {"seed": 77},
    }


class ContextualInteractionTests(unittest.TestCase):
    def test_archetype_label_never_changes_the_mathematics(self):
        attacker = profile("Home", route=0.4, archetype="Controller")
        defender = profile("Away", exposure=0.3, archetype="Direct")
        first = directional_context(attacker, defender, CONFIG)
        attacker["archetype"] = "Anything Else"
        defender["archetype"] = "Another Label"
        second = directional_context(attacker, defender, CONFIG)
        self.assertEqual(first["continuous_signal"], second["continuous_signal"])
        self.assertEqual(first["xg_multiplier"], second["xg_multiplier"])

    def test_favorable_context_raises_only_that_directional_xg(self):
        result = contextualize_prediction(
            baseline(),
            profile("Home", route=0.5),
            profile("Away", exposure=0.5),
            CONFIG,
        )
        self.assertGreater(result["contextual"]["predicted_xg"]["home"], 1.5)
        self.assertGreater(
            result["contextual"]["probabilities"]["home_win"],
            result["baseline"]["probabilities"]["home_win"],
        )

    def test_low_xi_confidence_smoothly_shrinks_the_effect(self):
        attacker = profile("Home", route=0.5)
        high = directional_context(
            attacker, profile("Away", exposure=0.5, confidence="high"), CONFIG
        )
        low = directional_context(
            attacker, profile("Away", exposure=0.5, confidence="low"), CONFIG
        )
        self.assertLess(abs(low["log_xg_adjustment"]), abs(high["log_xg_adjustment"]))

    def test_missing_pressing_evidence_removes_that_channel(self):
        attacker = profile("Home")
        defender = profile("Away")
        attacker["route_expression"]["high_press"] = 3.0
        defender["opponent_exposure"]["high_press"] = 3.0
        available = directional_context(attacker, defender, CONFIG)
        missing_attacker = copy.deepcopy(attacker)
        missing_attacker["quality_flags"] = ["pressing_evidence_missing"]
        missing = directional_context(missing_attacker, defender, CONFIG)
        self.assertLess(
            abs(missing["log_xg_adjustment"]),
            abs(available["log_xg_adjustment"]),
        )

    def test_context_response_is_continuous_without_favorite_bands(self):
        defender = profile("Away", exposure=0.2)
        first = directional_context(profile("Home", route=0.2), defender, CONFIG)
        second = directional_context(profile("Home", route=0.2001), defender, CONFIG)
        self.assertLess(
            abs(first["log_xg_adjustment"] - second["log_xg_adjustment"]),
            0.0001,
        )

    def test_contextual_probabilities_reconcile(self):
        result = contextualize_prediction(
            baseline(), profile("Home", route=0.2), profile("Away", exposure=0.1), CONFIG
        )
        probabilities = result["contextual"]["probabilities"]
        self.assertFalse(
            result["simulation"]["common_random_numbers_with_baseline"]
        )
        self.assertAlmostEqual(
            probabilities["home_win"]
            + probabilities["draw"]
            + probabilities["away_win"],
            1.0,
        )
        self.assertAlmostEqual(
            probabilities["over"]["2.5"] + probabilities["under"]["2.5"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
