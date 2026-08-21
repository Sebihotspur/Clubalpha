import unittest
from datetime import date

from clubalpha.squad_selection import build_squad_selection_priors


CONFIG = {
    "version": "test-selection-v1",
    "expected_team_minutes": 990.0,
    "recent_evidence": {
        "current_competitive_weight": 1.0,
        "preseason_weight": 0.25,
        "half_life_days": 30.0,
        "historical_prior_equivalent_matches": 2.0,
    },
    "default_role_slots": {"GK": 1, "CB": 2, "FB": 2, "CM": 3, "FW": 3},
    "availability": {
        "questionable_terms": ["doubtful", "day to day", "back in training"],
        "hard_exclusion_statuses": ["unavailable"],
    },
}


def squad(player_id, group, position, injury=None):
    return {
        "team_id": 10,
        "team": "Club",
        "player_id": player_id,
        "player": f"Player {player_id}",
        "squad_group": group,
        "position": position,
        "injury": injury,
    }


def grade(player_id, minutes, alpha=0.0):
    return {
        "player_id": player_id,
        "minutes": minutes,
        "alpha_ability_z": alpha,
        "scoring_position": "FW",
    }


def match_row(player_id, minutes, is_starter, kickoff="2026-08-17T15:00:00Z"):
    return {
        "match_id": 100,
        "competition_id": 47,
        "competition": "Premier League",
        "kickoff_utc": kickoff,
        "player_id": player_id,
        "player": f"Player {player_id}",
        "team_id": 10,
        "team": "Club",
        "is_starter": is_starter,
        "lineup_position_id": 11 if player_id == 1 else 70,
        "team_formation": "4-3-3",
        "metrics": {"minutes_played": {"value": minutes}},
    }


def full_squad():
    return [
        squad(1, "keepers", "GK"),
        squad(2, "keepers", "GK"),
        squad(3, "defenders", "CB"),
        squad(4, "defenders", "CB"),
        squad(5, "defenders", "CB"),
        squad(6, "defenders", "RB"),
        squad(7, "defenders", "LB"),
        squad(8, "defenders", "LB"),
        squad(9, "midfielders", "CM"),
        squad(10, "midfielders", "CDM"),
        squad(11, "midfielders", "CAM"),
        squad(12, "midfielders", "CM"),
        squad(13, "attackers", "ST"),
        squad(14, "attackers", "LW"),
        squad(15, "attackers", "RW"),
        squad(16, "attackers", "ST"),
    ]


class SquadSelectionTests(unittest.TestCase):
    def build(self, squads=None, grades=None, current=None, preseason=None):
        return build_squad_selection_priors(
            [{"team_id": 10, "name": "Club", "premier_league_2026_27": True}],
            squads if squads is not None else full_squad(),
            grades if grades is not None else [grade(index, 3000 - index) for index in range(1, 17)],
            current or [],
            preseason or [],
            date(2026, 8, 18),
            CONFIG,
        )[0]

    def test_declared_starters_define_shape_without_minutes_threshold(self):
        starter_ids = [1, 3, 4, 6, 7, 9, 10, 11, 13, 14, 15]
        rows = [match_row(player_id, 45 if player_id == 1 else 90, True) for player_id in starter_ids]
        rows.append(match_row(2, 45, False))
        result = self.build(current=rows)
        self.assertEqual(result["shape_prior"]["formation"], "4-3-3")
        # CAM remains in the FW Alpha population, matching the locked player
        # formula, even though FotMob's formation string calls it midfield.
        self.assertEqual(
            result["shape_prior"]["role_slots"],
            {"GK": 1, "CB": 2, "FB": 2, "CM": 2, "FW": 4},
        )
        self.assertEqual(result["evidence"]["exact_lineup_matches"], 1)
        self.assertAlmostEqual(
            sum(player["expected_minutes_prior"] for player in result["players"]),
            990.0,
            places=2,
        )

    def test_unavailable_player_is_removed_and_minutes_are_redistributed(self):
        squads = full_squad()
        squads[0]["injury"] = {"expectedReturn": "2026-10-01"}
        result = self.build(squads=squads)
        keeper = next(player for player in result["players"] if player["player_id"] == 1)
        self.assertGreater(keeper["baseline_expected_minutes"], 0)
        self.assertEqual(keeper["expected_minutes_prior"], 0)
        self.assertNotIn(1, {player["player_id"] for player in result["expected_starting_xi_prior"]})
        self.assertIn(2, {player["player_id"] for player in result["expected_starting_xi_prior"]})

    def test_alpha_is_context_and_does_not_override_minutes_hierarchy(self):
        grades = [grade(index, 1000) for index in range(1, 17)]
        grades[-1] = grade(16, 1, alpha=9.0)
        grades[-2] = grade(15, 3000, alpha=-2.0)
        result = self.build(grades=grades)
        xi_ids = {player["player_id"] for player in result["expected_starting_xi_prior"]}
        self.assertIn(15, xi_ids)
        self.assertNotIn(16, xi_ids)
        self.assertFalse(result["decision_boundaries"]["alpha_used_to_select_players"])

    def test_future_match_is_excluded(self):
        rows = [match_row(player_id, 90, True, "2026-08-19T15:00:00Z") for player_id in range(1, 12)]
        result = self.build(current=rows)
        self.assertEqual(result["evidence"]["recent_matches"], 0)
        self.assertIn("no_recent_match_detail", result["quality_flags"])

    def test_questionable_player_is_not_silently_assumed_out(self):
        squads = full_squad()
        squads[0]["injury"] = {"expectedReturn": "Doubtful"}
        result = self.build(squads=squads)
        keeper = next(player for player in result["players"] if player["player_id"] == 1)
        self.assertEqual(keeper["availability_status"], "questionable")
        self.assertGreater(keeper["expected_minutes_prior"], 0)
        self.assertTrue(result["decision_boundaries"]["questionable_players_assumed_available"])

    def test_no_minutes_evidence_does_not_create_an_xi_from_alpha(self):
        grades = [grade(index, 0, alpha=10.0) for index in range(1, 17)]
        result = self.build(grades=grades)
        self.assertEqual(result["expected_starting_xi_prior"], [])
        self.assertFalse(result["decision_boundaries"]["lineup_prior_ready"])
        self.assertIn("no_selection_evidence", result["quality_flags"])


if __name__ == "__main__":
    unittest.main()
