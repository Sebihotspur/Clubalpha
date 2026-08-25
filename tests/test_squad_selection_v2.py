import unittest

from clubalpha.squad_selection_v2 import project_team_selection


CONFIG = {
    "version": "test-selection-v2",
    "expected_team_minutes": 990.0,
    "recent_evidence": {
        "maximum_matches": 5,
        "match_rank_decay": 0.75,
        "same_competition_weight": 1.0,
        "cross_competition_weight": 0.75,
    },
    "shape": {"maximum_matches": 3},
    "selection": {"latest_declared_start_bonus_minutes": 0.0},
    "minutes": {
        "default_starter_minutes": 75.0,
        "default_substitute_minutes": 20.0,
    },
    "default_role_slots": {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3},
    "availability": {
        "questionable_terms": ["doubtful"],
        "unknown_terms": ["unknown"],
        "hard_exclusion_statuses": ["unavailable"],
    },
}


ROLE_POSITIONS = [11, 32, 34, 36, 38, 72, 74, 76, 102, 104, 106]


def candidate(player_id, injury=None):
    if player_id == 1:
        group, position = "keepers", "GK"
    elif player_id <= 5:
        group, position = "defenders", "CB"
    elif player_id <= 8:
        group, position = "midfielders", "CM"
    else:
        group, position = "attackers", "ST"
    return {
        "player_id": player_id,
        "player": f"Player {player_id}",
        "squad_group": group,
        "position": position,
        "injury": injury,
        "alpha_ability_z": 99.0 if player_id == 16 else -1.0,
    }


def match_rows(match_id, kickoff, starters=None, substitution=None, formation="4-3-3"):
    starter_ids = starters or list(range(1, 12))
    rows = []
    for index, player_id in enumerate(starter_ids):
        minutes = 90
        if substitution and player_id == substitution[0]:
            minutes = substitution[2]
        rows.append(
            {
                "match_id": match_id,
                "competition_id": 47,
                "kickoff_utc": kickoff,
                "team_id": 10,
                "player_id": player_id,
                "player": f"Player {player_id}",
                "is_starter": True,
                "lineup_position_id": ROLE_POSITIONS[index],
                "team_formation": formation,
                "metrics": {"minutes_played": {"value": minutes}},
            }
        )
    if substitution:
        starter_id, substitute_id, minute = substitution
        rows.append(
            {
                "match_id": match_id,
                "competition_id": 47,
                "kickoff_utc": kickoff,
                "team_id": 10,
                "player_id": substitute_id,
                "player": f"Player {substitute_id}",
                "is_starter": False,
                "lineup_position_id": None,
                "team_formation": formation,
                "metrics": {"minutes_played": {"value": 90 - minute}},
            }
        )
    return rows


class SquadSelectionV2Tests(unittest.TestCase):
    def project(self, rows, candidates=None):
        return project_team_selection(
            rows,
            candidates or [candidate(player_id) for player_id in range(1, 17)],
            "2026-08-26T15:00:00Z",
            47,
            CONFIG,
            team_id=10,
            team="Club",
        )

    def test_uses_only_the_latest_five_matches_before_kickoff(self):
        rows = []
        for match_id, day in enumerate(range(10, 17), start=100):
            rows.extend(match_rows(match_id, f"2026-08-{day:02d}T15:00:00Z"))
        rows.extend(match_rows(999, "2026-08-27T15:00:00Z"))
        result = self.project(rows)
        self.assertEqual(result["evidence"]["prior_matches"], 5)
        self.assertEqual(result["evidence"]["prior_match_ids"], [106, 105, 104, 103, 102])
        self.assertNotIn(999, result["evidence"]["prior_match_ids"])

    def test_start_and_appearance_probabilities_are_separate(self):
        rows = []
        rows.extend(match_rows(1, "2026-08-20T15:00:00Z", substitution=(11, 12, 60)))
        rows.extend(
            match_rows(
                2,
                "2026-08-23T15:00:00Z",
                starters=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12],
                substitution=(12, 11, 70),
            )
        )
        result = self.project(rows)
        player = next(row for row in result["players"] if row["player_id"] == 11)
        self.assertGreater(player["appearance_probability"], player["start_probability"])
        self.assertGreater(player["conditional_starter_minutes"], player["conditional_substitute_minutes"])
        self.assertGreater(player["expected_minutes_raw"], 0)

    def test_minutes_are_physical_and_sum_to_team_total(self):
        result = self.project(match_rows(1, "2026-08-23T15:00:00Z"))
        self.assertAlmostEqual(
            sum(row["expected_minutes"] for row in result["players"]), 990.0, places=2
        )
        self.assertLessEqual(max(row["expected_minutes"] for row in result["players"]), 90.0)
        self.assertTrue(result["decision_boundaries"]["projection_ready"])
        self.assertFalse(
            result["decision_boundaries"]["selection_probabilities_calibrated"]
        )

    def test_unavailable_player_is_removed(self):
        candidates = [candidate(player_id) for player_id in range(1, 17)]
        candidates[0]["injury"] = {"expectedReturn": "2026-10-01"}
        result = self.project(match_rows(1, "2026-08-23T15:00:00Z"), candidates)
        keeper = next(row for row in result["players"] if row["player_id"] == 1)
        self.assertEqual(keeper["start_probability"], 0)
        self.assertEqual(keeper["expected_minutes"], 0)
        self.assertNotIn(1, {row["player_id"] for row in result["predicted_starting_xi"]})

    def test_alpha_fields_on_candidates_cannot_select_a_player(self):
        rows = match_rows(1, "2026-08-23T15:00:00Z")
        result = self.project(rows)
        xi_ids = {row["player_id"] for row in result["predicted_starting_xi"]}
        self.assertNotIn(16, xi_ids)
        self.assertFalse(result["decision_boundaries"]["alpha_used_to_select_players"])

    def test_weighted_shape_uses_three_exact_lineups(self):
        rows = []
        rows.extend(match_rows(1, "2026-08-20T15:00:00Z", formation="4-3-3"))
        rows.extend(match_rows(2, "2026-08-21T15:00:00Z", formation="4-2-4"))
        rows.extend(match_rows(3, "2026-08-22T15:00:00Z", formation="4-2-4"))
        result = self.project(rows)
        self.assertEqual(result["shape_projection"]["formation"], "4-2-4")
        self.assertEqual(len(result["shape_projection"]["source_match_ids"]), 3)

    def test_global_history_is_filtered_to_requested_team(self):
        rows = match_rows(1, "2026-08-23T15:00:00Z")
        opponent_rows = [{**row, "team_id": 20, "player_id": row["player_id"] + 100} for row in rows]
        result = self.project([*rows, *opponent_rows])
        self.assertEqual(result["evidence"]["prior_matches"], 1)
        self.assertEqual(len(result["predicted_starting_xi"]), 11)


if __name__ == "__main__":
    unittest.main()
