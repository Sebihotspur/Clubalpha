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

    def test_wide_midfielder_with_fullback_secondary_scores_as_fullback(self):
        """Dimarco- and Dumfries-style provider roles are wing-backs, not CMs."""

        self.assertEqual(scoring_position("LM,LB", "midfielders"), "FB")
        self.assertEqual(scoring_position("RM,RB", "midfielders"), "FB")

    def test_central_midfielder_with_fullback_secondary_stays_central(self):
        """Do not turn Kimmich- or Camavinga-style secondary roles into FBs."""

        self.assertEqual(scoring_position("CDM,RB", "midfielders"), "CM")
        self.assertEqual(scoring_position("CM,LM,LB", "midfielders"), "CM")

    def test_cam_still_routes_to_forwards_matching_wcalpha(self):
        self.assertEqual(scoring_position("CAM,RW", "midfielders"), "FW")
        self.assertEqual(scoring_position("CDM,CM,CAM", "midfielders"), "CM")

    def test_coach_and_unknown_group_are_not_graded(self):
        self.assertIsNone(scoring_position(None, "coach"))
        self.assertIsNone(scoring_position("ST", "unknown-group"))


class FormulaShapeTests(unittest.TestCase):
    def test_every_formula_is_flat_and_documented(self):
        expected = {"FW": 12, "CM": 11, "CB": 11, "FB": 12, "GK": 5}
        for position, count in expected.items():
            formula = resolved_formula(position, CONFIG)
            self.assertEqual(len(formula), count, position)
            weights = {spec["weight"] for spec in formula.values()}
            self.assertEqual(weights, {2.0}, f"{position} weights are not flat")
            for key, spec in formula.items():
                self.assertIn(spec["direction"], {"positive", "inverted"}, f"{position}.{key}")
                self.assertIn(spec["form"], {"per90", "percentage", "physical"}, f"{position}.{key}")

    def test_progression_and_creation_metrics_are_in_the_requested_roles(self):
        forward = resolved_formula("FW", CONFIG)
        fullback = resolved_formula("FB", CONFIG)

        self.assertIn("pf390", forward)
        self.assertIn("lbp90", forward)
        self.assertIn("kp90", fullback)
        self.assertIn("axa90", fullback)
        self.assertIn("gxg90", fullback)
        self.assertNotIn("ga90", fullback)

    def test_fullback_scoring_and_creation_do_not_double_count_assists(self):
        rows = [
            match_row(
                1,
                47,
                100,
                minutes=90,
                goals=1,
                assists=2,
                expected_goals=0.5,
                expected_assists=0.6,
            )
        ]
        features, _ = build_features(rows, [], "FB", CONFIG)

        self.assertAlmostEqual(features["gxg90"]["value"], 1.5)
        self.assertAlmostEqual(features["axa90"]["value"], 2.6)

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
            match_row(1, 47, 100, minutes=90),       # opponent in the Premier League
            match_row(2, 999998, 100, minutes=30),   # neither opponent nor competition maps
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

    def test_champions_league_stage_ids_are_mapped(self):
        """Regression: match rows carry stage ids, not the league id used to fetch.

        Mapping only 42 sent 375,008 minutes of Champions League football to the
        -0.9 default, grading the strongest club competition as the weakest.
        """

        mapping = CONFIG["league_quality"]["fotmob_league_id_to_key"]
        for league_id in ("42", "904988", "904995"):
            self.assertEqual(mapping.get(league_id), "Champions League", league_id)

        offsets = CONFIG["league_quality"]["offsets"]
        self.assertGreater(offsets["Champions League"], offsets["Ligue 1"])
        for stage_id in (904988, 904995):
            rows = [match_row(9, stage_id, 100, minutes=90)]
            result = player_league_offset(rows, {}, {}, CONFIG)
            self.assertAlmostEqual(result["offset"], offsets["Champions League"])

    def test_every_collected_competition_has_an_offset(self):
        """Any competition carrying minutes must map, or its players are penalised."""

        mapping = CONFIG["league_quality"]["fotmob_league_id_to_key"]
        collected = {
            47: "Premier League",
            48: "Championship",
            53: "Ligue 1",
            54: "Bundesliga",
            55: "Serie A",
            57: "Eredivisie",
            59: "Eliteserien",
            61: "Liga Portugal",
            64: "Scottish Premiership",
            71: "Super Lig",
            87: "LaLiga",
            122: "Czech First League",
            127: "Israeli Premier League",
            135: "Greek Super League",
            176: "Slovak First Football League",
            252: "Croatian HNL",
            38: "Austrian Bundesliga",
            40: "Belgian Pro League",
            904988: "Champions League",
            904995: "Champions League",
        }
        unmapped = [name for key, name in collected.items() if str(key) not in mapping]
        self.assertEqual(unmapped, [], f"unmapped competitions carrying minutes: {unmapped}")


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


class AbsentFieldTests(unittest.TestCase):
    """Two absences must stay distinguishable.

    FotMob omits zero-valued event cards, so a defender with no errors has no
    error key and that is a genuine zero. A field the provider does not publish
    at all is missing — and treating it as zero collapses the metric's variance
    to nothing, at which point it contributes only the league offset while
    presenting itself as evidence.
    """

    def test_field_no_competition_publishes_yields_no_feature(self):
        """Regression: line_breaking_passes was absent from all 38,193 rows."""

        rows = [
            match_row(index, 47, 100, minutes=90, recoveries=5)
            for index in range(1, 6)
        ]
        features, _ = build_features(rows, [], "CM", CONFIG)
        self.assertIsNone(features["lbp90"], "an unpublished field must not read as zero")
        self.assertIsNotNone(features["rec90"])

    def test_absent_key_within_a_supplying_competition_is_zero(self):
        rows = [
            match_row(1, 47, 100, minutes=90, errors_led_to_goal=1),
            match_row(2, 47, 100, minutes=90),  # no error card: a real zero
        ]
        features, _ = build_features(rows, [], "CB", CONFIG)
        self.assertIsNotNone(features["err90"])
        self.assertAlmostEqual(features["err90"]["numerator"], 1.0)
        self.assertAlmostEqual(features["err90"]["denominator_minutes"], 180.0)

    def test_zero_variance_metric_cannot_become_a_league_bonus(self):
        """With no signal the metric must drop out, not pass the offset through."""

        def defender(pid, offset):
            keys = resolved_formula("CB", CONFIG)
            values = {key: 1.0 for key in keys}
            values["lbp90"] = None
            return player(pid, "CB", 3000, offset, values)

        squad = [defender(index, 0.45 if index % 2 else -0.9) for index in range(12)]
        grades = score_population(squad, CONFIG)
        for row in grades:
            self.assertIsNone(row["metrics"]["lbp90"]["z"])
            self.assertEqual(row["metrics"]["lbp90"]["confidence"], "missing")

    def test_multi_source_metric_sums_rather_than_falling_back(self):
        """Regression: clearances plus blocks only counted clearances.

        _sum_event treats extra keys as fallbacks, so the second addend was
        never reached while the first was present in every row.
        """

        rows = [match_row(1, 47, 100, minutes=90, clearances=4, shot_blocks=2)]
        features, _ = build_features(rows, [], "CB", CONFIG)
        self.assertAlmostEqual(features["clrblk90"]["numerator"], 6.0)
        self.assertAlmostEqual(features["clrblk90"]["value"], 6.0)


class GoalPreventionCoverageTests(unittest.TestCase):
    def test_global_direct_availability_does_not_create_false_zero(self):
        """A keeper in an unsupported competition has no gprev evidence."""

        rows = [match_row(1, 176, 100, minutes=90)]
        availability = {"goals_prevented": {(47, "League 47")}}
        features, _ = build_features(rows, [], "GK", CONFIG, availability)

        self.assertIsNone(features["gprev90"])

    def test_fallback_is_selected_for_the_players_competition(self):
        rows = [
            match_row(
                1,
                176,
                100,
                minutes=90,
                expected_goals_on_target_faced=1.8,
                goals_conceded=1,
            )
        ]
        availability = {
            "goals_prevented": {(47, "League 47")},
            "expected_goals_on_target_faced": {(176, "League 176")},
            "goals_conceded": {(176, "League 176")},
        }
        features, _ = build_features(rows, [], "GK", CONFIG, availability)

        self.assertAlmostEqual(features["gprev90"]["value"], 0.8)
        self.assertAlmostEqual(features["gprev90"]["denominator_minutes"], 90.0)

    def test_direct_and_fallback_competitions_combine_without_dilution(self):
        rows = [
            match_row(1, 47, 100, minutes=90, goals_prevented=0.5),
            match_row(
                2,
                176,
                100,
                minutes=90,
                expected_goals_on_target_faced=1.8,
                goals_conceded=1,
            ),
            match_row(3, 999, 100, minutes=90),
        ]
        availability = {
            "goals_prevented": {(47, "League 47")},
            "expected_goals_on_target_faced": {(176, "League 176")},
            "goals_conceded": {(176, "League 176")},
        }
        features, _ = build_features(rows, [], "GK", CONFIG, availability)

        self.assertAlmostEqual(features["gprev90"]["value"], 0.65)
        self.assertAlmostEqual(features["gprev90"]["numerator"], 1.3)
        self.assertAlmostEqual(features["gprev90"]["denominator_minutes"], 180.0)


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
