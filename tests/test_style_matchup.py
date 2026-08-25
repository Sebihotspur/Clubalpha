import unittest

from clubalpha.style_matchup import (
    build_style_matchup_snapshot,
    classify_archetype,
    evaluate_style_matchup,
    route_and_exposure,
)


def metric(value):
    return {"z": value}


def profile(*, pressing=0.8, control=0.4, territory=0.5, directness=-0.4, crossing=0.1):
    return {
        "team_id": 1,
        "team": "Example City",
        "premier_league_2026_27": True,
        "style": {
            "axes": {
                "control": metric(control),
                "territory": metric(territory),
                "directness": metric(directness),
                "crossing": metric(crossing),
                "set_piece_reliance": metric(0.2),
                "high_pressing": metric(pressing),
            }
        },
        "strengths_weaknesses": {
            "axes": {
                "chance_creation": metric(0.6),
                "shot_quality": metric(0.3),
                "box_access": metric(0.8),
                "set_piece_attack": metric(0.4),
                "chance_prevention": metric(-0.4),
                "shot_suppression": metric(-0.2),
                "box_defense": metric(-0.6),
                "set_piece_defense": metric(-0.5),
            }
        },
    }


class StyleMatchupTests(unittest.TestCase):
    def test_route_and_exposure_are_transparent_weighted_signals(self):
        routes, exposures = route_and_exposure(profile())
        self.assertEqual(routes["box_pressure"], 0.635)
        self.assertEqual(routes["set_pieces"], 0.36)
        self.assertEqual(exposures["set_pieces"], 0.5)
        self.assertEqual(exposures["direct_transition"], 0.455)

    def test_archetype_classifier_separates_control_and_direct_pressing(self):
        self.assertEqual(classify_archetype(profile()), "territorial_controller")
        direct = profile(control=-0.2, territory=-0.2, directness=0.4, pressing=1.0)
        self.assertEqual(classify_archetype(direct), "high_intensity_direct")
        forming = profile(control=0.2, directness=-0.2, pressing=None)
        self.assertEqual(classify_archetype(forming), "promoted_forming")

    def test_snapshot_keeps_challenger_outside_composite(self):
        alpha = {
            "team": "Example City",
            "grade_confidence": "high",
            "grade_provisional": False,
            "alpha": {
                "attacking_unit_alpha_ability": metric(0.5),
                "scoring_threat": metric(0.2),
                "chance_creation": metric(0.4),
                "defensive_prevention": metric(0.3),
            },
        }
        snapshot = build_style_matchup_snapshot([profile()], [alpha], as_of="2026-08-25")
        self.assertEqual(snapshot["composite_weight"], 0)
        self.assertEqual(snapshot["status"], "research_challenger")
        self.assertEqual(snapshot["teams"][0]["projected_xi"]["attacking_unit"], 0.5)

    def test_directional_matchup_keeps_probability_modifier_null(self):
        alpha = {
            "team": "Example City",
            "grade_confidence": "high",
            "grade_provisional": False,
            "alpha": {
                "attacking_unit_alpha_ability": metric(0.5),
                "scoring_threat": metric(0.2),
                "chance_creation": metric(0.4),
                "defensive_prevention": metric(0.3),
            },
        }
        snapshot = build_style_matchup_snapshot([profile()], [alpha], as_of="2026-08-25")
        team = snapshot["teams"][0]
        result = evaluate_style_matchup(team, team)
        self.assertEqual(len(result["routes"]), 5)
        self.assertIsNone(result["probability_modifier"])
        self.assertEqual(result["composite_weight"], 0)


if __name__ == "__main__":
    unittest.main()
