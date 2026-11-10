import unittest

from clubalpha.discretionary_overlay import score_selection


CONFIG = {
    "version": "clubalpha_discretionary_overlay_v1",
    "maximum_total_adjustment": 0.03,
    "categories": {
        "player_state": {"maximum_adjustment": 0.01},
        "tactical_intent": {"maximum_adjustment": 0.01},
        "situational_psychology": {"maximum_adjustment": 0.005},
        "informed_intuition": {"maximum_adjustment": 0.005},
    },
    "near_miss": {
        "side_probability_minimum": 0.45,
        "total_probability_minimum": 0.58,
    },
    "activation": {},
    "locked_boundaries": {
        "systematic_probability_mutable": False,
        "systematic_decision_mutable": False,
        "hard_execution_gates_overridable": False,
        "automatic_real_capital_authorization": False,
    },
}


def selection(status="approved", already_modeled=False):
    return {
        "market": "one_x_two",
        "outcome": "home_win",
        "systematic_probability": 0.45,
        "systematic_call": "pass",
        "systematic_reason": "leader_below_45_percent",
        "structurally_reviewable": True,
        "review_blockers": [],
        "review": {
            "status": status,
            "analyst": "analyst",
            "reviewed_at_utc": "2026-11-20T12:00:00Z",
            "market_price_used_as_rationale": False,
            "thesis": "The new role has improved the attack's route to goal.",
            "signals": {
                "player_state": {
                    "direction": 1,
                    "confidence": 1.0,
                    "note": "Lead attacker is sharper in the new role.",
                    "already_modeled": already_modeled,
                },
                "tactical_intent": {
                    "direction": 1,
                    "confidence": 0.5,
                    "note": "Manager retained the more aggressive shape.",
                    "already_modeled": False,
                },
                "situational_psychology": {
                    "direction": 0,
                    "confidence": 0.0,
                    "note": None,
                    "already_modeled": False,
                },
                "informed_intuition": {
                    "direction": 1,
                    "confidence": 1.0,
                    "note": "The matchup looks more comfortable on film.",
                    "already_modeled": False,
                },
            },
        },
    }


class DiscretionaryOverlayTests(unittest.TestCase):
    def test_approved_final_review_adds_bounded_probability(self):
        result = score_selection(
            selection(), final_refresh_complete=True, config=CONFIG
        )
        self.assertTrue(result["overlay_active"])
        self.assertAlmostEqual(result["discretionary_adjustment"], 0.02)
        self.assertAlmostEqual(result["effective_probability"], 0.47)
        self.assertEqual(result["systematic_probability"], 0.45)
        self.assertEqual(result["effective_call"], "home_win")
        self.assertEqual(result["call_origin"], "discretionary_near_miss")

    def test_provisional_review_is_recorded_but_inactive(self):
        result = score_selection(
            selection(), final_refresh_complete=False, config=CONFIG
        )
        self.assertFalse(result["overlay_active"])
        self.assertEqual(result["effective_probability"], 0.45)
        self.assertEqual(result["adjusted_probability"], 0.47)

    def test_draft_review_is_inactive(self):
        result = score_selection(
            selection(status="draft"),
            final_refresh_complete=True,
            config=CONFIG,
        )
        self.assertFalse(result["overlay_active"])

    def test_already_modeled_evidence_cannot_be_double_counted(self):
        with self.assertRaisesRegex(ValueError, "cannot be counted twice"):
            score_selection(
                selection(already_modeled=True),
                final_refresh_complete=True,
                config=CONFIG,
            )

    def test_nonzero_signal_requires_note(self):
        row = selection()
        row["review"]["signals"]["player_state"]["note"] = None
        with self.assertRaisesRegex(ValueError, "requires note"):
            score_selection(row, final_refresh_complete=True, config=CONFIG)


if __name__ == "__main__":
    unittest.main()
