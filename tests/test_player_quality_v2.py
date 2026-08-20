import json
import unittest
from pathlib import Path

from clubalpha.player_quality_v2 import (
    build_features,
    build_match_index,
    player_league_offset,
    resolved_formula,
    score_population,
    scoring_position,
    team_ratings,
)

CONFIG = json.loads(
    (Path(__file__).resolve().parents[1] / "config/player-quality-clubalpha-v2.json").read_text(
        encoding="utf-8"
    )
)


def match_row(match_id, competition_id, team_id, minutes=90, **metrics):
    payload = {"minutes_played": {"value": minutes, "total": None}}
    for key, value in metrics.items():
        payload[key] = value if isinstance(value, dict) else {"value": value, "total": None}
    return {
        "match_id": match_id,
        "competition_id": competition_id,
        "competition": f"League {competition_id}",
        "player_id": 1,
        "team_id": team_id,
        "metrics": payload,
    }


def player(player_id, scoring_pos, minutes, offset, features, team_id=100, team="Club"):
    return {
        "player_id": player_id,
        "player": f"Player {player_id}",
        "current_team_id": team_id,
        "current_team": team,
        "current_position": scoring_pos,
        "scoring_position": scoring_pos,
        "league_quality": {"offset": offset, "minutes": minutes, "fully_resolved": True},
        "sample": {"minutes": minutes, "matches": int(minutes // 90)},
        "features": {
            key: ({"value": value} if value is not None else None)
            for key, value in features.items()
        },
        "quality_flags": [],
    }


class PositionMappingTests(unittest.TestCase):
    def test_five_populations_resolve(self):
        self.assertEqual(scoring_position("GK", "keepers"), "GK")
        self.assertEqual(scoring_position("CB", "defenders"), "CB")
        self.assertEqual(scoring_position("LB", "defenders"), "FB")
        self.assertEqual(scoring_position("CDM,CM", "midfielders"), "CM")
        self.assertEqual(scoring_position("ST", "attackers"), "FW")

    def test_wingback_filed_under_midfielders_scores_as_fullback(self):
        """FotMob files at least one LWB under midfielders; role must win."""

        self.assertEqual(scoring_position("LWB", "midfielders"), "FB")
        self.assertEqual(scoring_position("RB,CDM", "defenders"), "FB")

    def test_cam_still_routes_to_forwards_matching_wcalpha(self):
        self.assertEqual(scoring_position("CAM,RW", "midfielders"), "FW")
        self.assertEqual(scoring_position("CDM,CM,CAM", "midfielders"), "CM")

    def test_coach_and_unknown_group_are_not_graded(self):
        self.assertIsNone(scoring_position(None, "coach"))
        self.assertIsNone(scoring_position("ST", "unknown-group"))


class FormulaShapeTests(unittest.TestCase):
    def test_every_formula_is_flat_and_documented(self):
        expected = {"FW": 10, "CM": 11, "CB": 11, "FB": 10, "GK": 5}
        for position, count in expected.items():
            formula = resolved_formula(position, CONFIG)
            self.assertEqual(len(formula), count, position)
            weights = {spec["weight"] for spec in formula.values()}
            self.assertEqual(weights, {2.0}, f"{position} weights are not flat")
            for key, spec in formula.items():
                self.assertIn(spec["direction"], {"positive", "inverted"}, f"{position}.{key}")
                self.assertIn(spec["form"], {"per90", "percentage", "physical"}, f"{position}.{key}")

    def test_minutes_is_not_a_scored_metric_anywhere(self):
        """Availability belongs to Club Form, not to Player Ratings."""

        for position in CONFIG["formulas"]:
            self.assertNotIn("avail", resolved_formula(position, CONFIG))


class MinimumAttemptsTests(unittest.TestCase):
    def test_percentage_below_attempt_floor_is_missing_not_zero(self):
        rows = [match_row(1, 47, 100, accurate_crosses={"value": 2, "total": 3})]
        features, flags = build_features(rows, [], "FB", CONFIG)
        self.assertIsNone(features["crosspct"])
        self.assertIn("crosspct_below_minimum_attempts", flags)

    def test_percentage_above_attempt_floor_is_calculated(self):
        rows = [
            match_row(index, 47, 100, accurate_crosses={"value": 5, "total": 10})
            for index in range(1, 6)
        ]
        features, flags = build_features(rows, [], "FB", CONFIG)
        self.assertIsNotNone(features["crosspct"])
        self.assertAlmostEqual(features["crosspct"]["value"], 50.0)
        self.assertEqual(flags, [])


class LeagueOffsetTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = [
            {"match_id": 1, "home_team_id": 100, "away_team_id": 200, "competition_id": 47},
            {"match_id": 2, "home_team_id": 300, "away_team_id": 100, "competition_id": 42},
        ]
        self.index = build_match_index(self.fixtures)

    def test_offset_comes_from_the_opponent_league(self):
        """A Champions League tie inherits the opponent's domestic strength."""

        rows = [match_row(2, 42, 100, minutes=90)]
        team_leagues = {300: 87}  # opponent plays in La Liga
        result = player_league_offset(rows, self.index, team_leagues, CONFIG)
        self.assertAlmostEqual(result["offset"], 0.36)
        self.assertEqual(result["resolution"], {"opponent_league": 100.0})

    def test_offset_is_minutes_weighted_across_leagues(self):
        """A transferred player blends the leagues actually played in."""

        rows = [
            match_row(1, 47, 100, minutes=90),   # opponent in the Premier League
            match_row(2, 42, 100, minutes=30),   # opponent in a default-tier league
        ]
        team_leagues = {200: 47, 300: 999999}
        result = player_league_offset(rows, self.index, team_leagues, CONFIG)
        expected = (0.45 * 90 + -0.9 * 30) / 120
        self.assertAlmostEqual(result["offset"], expected, places=6)
        self.assertFalse(result["fully_resolved"])

    def test_unknown_league_falls_back_to_default(self):
        rows = [match_row(9, 999999, 100, minutes=90)]
        result = player_league_offset(rows, {}, {}, CONFIG)
        self.assertAlmostEqual(result["offset"], CONFIG["league_quality"]["default_offset"])


class LeagueDirectionRegressionTests(unittest.TestCase):
    """The v1 defect: a weak-league defender scored better for identical errors.

    v1 computed ``sign * raw * multiplier``, so after the sign flip 0.10
    errors per 90 became -0.115 in the Premier League and -0.070 in a default
    league — rewarding the weaker league. The additive offset must reverse it.
    """

    def _two_identical_defenders(self):
        features = {
            key: (0.1 if key == "err90" else 1.0)
            for key in resolved_formula("CB", CONFIG)
            if key != "pace"
        }
        features["pace"] = None
        strong = player(1, "CB", 3000, 0.45, features, team_id=1, team="Strong League Club")
        weak = player(2, "CB", 3000, -0.90, features, team_id=2, team="Weak League Club")
        filler = [
            player(index, "CB", 3000, 0.0, {**features, "err90": 0.1 + index * 0.02})
            for index in range(3, 10)
        ]
        return strong, weak, filler

    def test_strong_league_defender_is_not_punished_for_identical_errors(self):
        strong, weak, filler = self._two_identical_defenders()
        grades = {row["player_id"]: row for row in score_population([strong, weak, *filler], CONFIG)}
        self.assertGreater(
            grades[1]["metrics"]["err90"]["z"],
            grades[2]["metrics"]["err90"]["z"],
            "the stronger league must not grade worse on an identical error rate",
        )

    def test_league_offset_shifts_every_metric_form_equally(self):
        """Percentages and rates must move by the same amount in z-units."""

        strong, weak, filler = self._two_identical_defenders()
        grades = {row["player_id"]: row for row in score_population([strong, weak, *filler], CONFIG)}
        gaps = {
            key: grades[1]["metrics"][key]["z"] - grades[2]["metrics"][key]["z"]
            for key, spec in resolved_formula("CB", CONFIG).items()
            if grades[1]["metrics"][key]["z"] is not None
            and grades[2]["metrics"][key]["z"] is not None
            and spec["form"] in {"per90", "percentage"}
        }
        self.assertTrue(gaps)
        self.assertAlmostEqual(max(gaps.values()), min(gaps.values()), places=6)


class StandardisationAndShrinkageTests(unittest.TestCase):
    def _population(self, scoring_pos, count=12, minutes=3000):
        keys = [key for key in resolved_formula(scoring_pos, CONFIG)]
        return [
            player(
                index,
                scoring_pos,
                minutes,
                0.0,
                {key: 1.0 + index * 0.1 for key in keys},
            )
            for index in range(count)
        ]

    def test_positions_land_on_a_common_scale(self):
        """A +1.0 forward and a +1.0 keeper must mean the same thing."""

        grades = score_population(
            [*self._population("FW"), *self._population("GK")],
            CONFIG,
        )
        for position in ("FW", "GK"):
            values = [row["standardised_z"] for row in grades if row["scoring_position"] == position]
            self.assertAlmostEqual(sum(values) / len(values), 0.0, places=2)
            spread = max(values) - min(values)
            self.assertGreater(spread, 0.0)

    def test_thin_samples_are_shrunk_toward_the_positional_average(self):
        population = self._population("CB", count=12, minutes=3000)
        thin = player(99, "CB", 300, 0.0, {key: 5.0 for key in resolved_formula("CB", CONFIG)})
        grades = {row["player_id"]: row for row in score_population([*population, thin], CONFIG)}
        row = grades[99]
        self.assertAlmostEqual(row["shrinkage_weight"], 300 / (300 + 900), places=3)
        self.assertLess(abs(row["alpha_ability_z"]), abs(row["standardised_z"]))

    def test_reference_distribution_excludes_short_samples(self):
        """Sub-threshold players are graded but never define the yardstick."""

        population = self._population("FB", count=10, minutes=3000)
        cameo = player(99, "FB", 90, 0.0, {key: 50.0 for key in resolved_formula("FB", CONFIG)})
        grades = score_population([*population, cameo], CONFIG)
        reference = {row["reference_players"] for row in grades}
        self.assertEqual(reference, {10})
        self.assertTrue(any(row["player_id"] == 99 for row in grades))


class NonPenaltyGoalTests(unittest.TestCase):
    def test_unreconciled_goal_leaves_the_feature_missing(self):
        rows = [
            match_row(1, 47, 100, goals=1, non_penalty_goals=1),
            match_row(2, 47, 100, goals=1),  # no shot-map classification
        ]
        features, flags = build_features(rows, [], "FW", CONFIG)
        self.assertIsNone(features["npg90"])
        self.assertIn("non_penalty_goals_unreconciled_match_shotmap", flags)

    def test_goalless_unclassified_match_does_not_block_the_feature(self):
        rows = [
            match_row(1, 47, 100, goals=1, non_penalty_goals=1),
            match_row(2, 47, 100),  # played, did not score
        ]
        features, flags = build_features(rows, [], "FW", CONFIG)
        self.assertIsNotNone(features["npg90"])
        self.assertEqual(flags, [])


class TeamRollUpTests(unittest.TestCase):
    def test_attack_and_defence_weight_positions_differently(self):
        keys_fw = resolved_formula("FW", CONFIG)
        keys_gk = resolved_formula("GK", CONFIG)
        squad = [
            *[player(i, "FW", 3000, 0.0, {k: 1.0 + i * 0.1 for k in keys_fw}) for i in range(6)],
            *[player(100 + i, "GK", 3000, 0.0, {k: 1.0 + i * 0.1 for k in keys_gk}) for i in range(6)],
        ]
        grades = score_population(squad, CONFIG)
        ratings = team_ratings(grades, CONFIG)
        self.assertEqual(len(ratings), 1)
        record = ratings[0]
        self.assertIsNotNone(record["attack_rating"])
        self.assertIsNotNone(record["defence_rating"])
        # Six forwards at 3.0 and six keepers at 0.1 for attack; reversed for defence.
        self.assertAlmostEqual(record["attack_weight"], 6 * 3.0 + 6 * 0.1, places=3)
        self.assertAlmostEqual(record["defence_weight"], 6 * 0.5 + 6 * 2.5, places=3)


if __name__ == "__main__":
    unittest.main()
