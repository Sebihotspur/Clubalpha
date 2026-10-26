import copy
import json
import unittest
from pathlib import Path

from clubalpha.decision_policy import (
    evaluate_side,
    evaluate_total,
    price_eligible,
    refresh_gate,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads(
    (ROOT / "config/decision-policy-v1.json").read_text(encoding="utf-8")
)


def baseline(home_form=1.0, home_alpha=1.0, away_form=-1.0, away_alpha=-1.0):
    return {
        "probabilities": {"home_win": 0.56, "draw": 0.24, "away_win": 0.20},
        "fixture_intelligence": {
            "home": {
                "normalized_components_z": {
                    "club_form": home_form,
                    "player_quality_lineup": home_alpha,
                    "historical_residual": 0.0,
                }
            },
            "away": {
                "normalized_components_z": {
                    "club_form": away_form,
                    "player_quality_lineup": away_alpha,
                    "historical_residual": 0.0,
                }
            },
        },
    }


def contextual(probability=0.56, verdict="baseline_reinforced", reliability=0.9):
    return {
        "contextual": {
            "probabilities": {
                "home_win": probability,
                "draw": 0.24,
                "away_win": 0.76 - probability,
            }
        },
        "context_read": {"verdict": verdict},
        "directional_context": {
            "home_attack": {"projected_xi_reliability": reliability},
            "away_attack": {"projected_xi_reliability": reliability},
        },
    }


def calibrated(probability=0.56, draw=0.24, away=0.20, over=0.61, draw_zone=False):
    return {
        "probabilities": {
            "home_win": probability,
            "draw": draw,
            "away_win": away,
            "over": {"2.5": over},
        },
        "calibration_read": {
            "draw_zone": draw_zone,
            "goal_environment_log_correction": -0.05,
        },
    }


class DecisionPolicyTests(unittest.TestCase):
    def test_strong_aligned_side_is_promoted(self):
        decision = evaluate_side(baseline(), contextual(), calibrated(), CONFIG)
        self.assertEqual(decision["call"], "home_win")
        self.assertEqual(decision["tier"], "strong")

    def test_medium_side_requires_form_and_player_alpha_alignment(self):
        prediction = baseline(home_form=-1.0, away_form=1.0)
        context = contextual(probability=0.49)
        decision = evaluate_side(
            prediction,
            context,
            calibrated(probability=0.49, draw=0.25, away=0.26),
            CONFIG,
        )
        self.assertEqual(decision["call"], "pass")
        self.assertEqual(
            decision["reason"],
            "club_form_and_player_alpha_do_not_both_support_side",
        )

    def test_side_below_45_percent_is_a_pass(self):
        context = contextual(probability=0.44)
        decision = evaluate_side(
            baseline(),
            context,
            calibrated(probability=0.44, draw=0.24, away=0.32),
            CONFIG,
        )
        self.assertEqual(decision["call"], "pass")
        self.assertEqual(decision["reason"], "leader_below_45_percent")

    def test_draw_zone_forces_a_pass(self):
        decision = evaluate_side(
            baseline(), contextual(), calibrated(draw_zone=True), CONFIG
        )
        self.assertEqual(decision["call"], "pass")
        self.assertEqual(decision["reason"], "calibrated_draw_zone")

    def test_total_uses_calibrated_probability_and_keeps_pass_band(self):
        self.assertEqual(
            evaluate_total(calibrated(over=0.61), CONFIG)["call"],
            "over_2_5",
        )
        self.assertEqual(
            evaluate_total(calibrated(over=0.50), CONFIG)["call"], "pass"
        )
        self.assertEqual(
            evaluate_total(calibrated(over=0.39), CONFIG)["call"],
            "under_2_5",
        )

    def test_price_gate_cannot_promote_a_pass(self):
        self.assertFalse(price_eligible("pass", 0.60, 0.40, CONFIG))
        self.assertTrue(price_eligible("home_win", 0.60, 0.50, CONFIG))
        self.assertFalse(price_eligible("home_win", 0.60, 0.57, CONFIG))

    def test_policy_cannot_unlock_capital(self):
        config = copy.deepcopy(CONFIG)
        config["locked_boundaries"]["automatic_capital_authorization_allowed"] = True
        with self.assertRaisesRegex(ValueError, "weakens a locked boundary"):
            evaluate_side(baseline(), contextual(), calibrated(), config)

    def test_final_freeze_is_blocked_until_midweek_refresh(self):
        load = {
            "teams": [
                {"team": "Team 1", "pending_preleague_fixture": {"match_id": 1}},
                {"team": "Team 2", "pending_preleague_fixture": None},
            ]
        }
        provisional = refresh_gate(
            load, {"Team 1", "Team 2"}, stage="provisional", config=CONFIG
        )
        self.assertFalse(provisional["final_call_eligible"])
        with self.assertRaisesRegex(ValueError, "pending preleague fixtures"):
            refresh_gate(load, {"Team 1", "Team 2"}, stage="final", config=CONFIG)


if __name__ == "__main__":
    unittest.main()
