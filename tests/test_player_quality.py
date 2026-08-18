import json
import unittest
from pathlib import Path

from clubalpha.player_quality import (
    build_player_features,
    coverage_reliability_weight,
    minutes_reliability_weight,
    score_population,
    scoring_position,
)


ROOT = Path(__file__).resolve().parents[1]


class PlayerQualityParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (ROOT / "config/player-quality-wcalpha-v1.json").read_text(encoding="utf-8")
        )

    def player(self, player_id, npg90, xg90):
        features = {key: None for key in self.config["formulas"]["FW"]}
        features["npg90"] = {
            "value": npg90,
            "source": "parity fixture",
            "confidence": "calculated",
        }
        features["xg90"] = {
            "value": xg90,
            "source": "parity fixture",
            "confidence": "calculated",
        }
        return {
            "player_id": player_id,
            "player": f"Player {player_id}",
            "current_team_id": 1,
            "current_team": "Club",
            "current_position": "ST",
            "scoring_position": "FW",
            "league_quality": {"key": "test", "multiplier": 1.0},
            "sample": {"minutes": 1800, "matches": 20},
            "features": features,
            "quality_flags": [],
        }

    def test_attacker_score_matches_locked_wcalpha_math(self):
        population = [
            self.player(1, 0.0, 0.0),
            self.player(2, 1.0, 2.0),
            self.player(3, 2.0, 1.0),
        ]
        scores = {row["player_id"]: row for row in score_population(population, self.config)}

        # npg z=1, xg z=0. Available-weight composite = 3.0 / (3.0+2.8).
        self.assertEqual(scores[3]["alpha_ability_z"], 0.517)
        # 20% positive coverage hits WCALPHA's 0.35 minimum coverage weight.
        self.assertEqual(scores[3]["coverage_weight"], 0.35)
        self.assertEqual(scores[3]["reliability_adjusted_z"], 0.181)
        # Negative grades are not coverage-dampened in the locked engine.
        self.assertEqual(scores[1]["alpha_ability_z"], -1.0)
        self.assertEqual(scores[1]["coverage_weight"], 1.0)

    def test_inverted_error_metric_rewards_lower_value(self):
        formula = self.config["formulas"]["CB"]
        population = []
        for player_id, errors in enumerate((0.0, 1.0, 2.0), start=1):
            features = {key: None for key in formula}
            features["err"] = {
                "value": errors,
                "source": "parity fixture",
                "confidence": "calculated",
            }
            population.append(
                {
                    "player_id": player_id,
                    "player": f"Defender {player_id}",
                    "current_team_id": 1,
                    "current_team": "Club",
                    "current_position": "CB",
                    "scoring_position": "CB",
                    "league_quality": {"key": "test", "multiplier": 1.0},
                    "sample": {"minutes": 1800, "matches": 20},
                    "features": features,
                    "quality_flags": [],
                }
            )
        scores = {row["player_id"]: row for row in score_population(population, self.config)}
        self.assertEqual(scores[1]["alpha_ability_z"], 1.0)
        self.assertEqual(scores[3]["alpha_ability_z"], -1.0)

    def test_locked_reliability_bands_and_coverage_rule(self):
        self.assertEqual(minutes_reliability_weight(1700, self.config), 1.0)
        self.assertEqual(minutes_reliability_weight(1200, self.config), 0.92)
        self.assertEqual(minutes_reliability_weight(700, self.config), 0.84)
        self.assertEqual(minutes_reliability_weight(699, self.config), 0.76)
        self.assertAlmostEqual(coverage_reliability_weight(40, 1.0, self.config), 2 / 3)
        self.assertEqual(coverage_reliability_weight(40, -1.0, self.config), 1.0)


class PlayerFeatureAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(
            (ROOT / "config/player-quality-wcalpha-v1.json").read_text(encoding="utf-8")
        )

    def test_position_populations_follow_current_role(self):
        self.assertEqual(scoring_position("ST,LW", "attackers"), "FW")
        self.assertEqual(scoring_position("CAM,CM", "midfielders"), "FW")
        self.assertEqual(scoring_position("CB,LB", "defenders"), "CB")
        self.assertEqual(scoring_position("LWB,LB", "defenders"), "FB")
        self.assertIsNone(scoring_position("CM,CDM", "midfielders"))

    def test_match_rows_aggregate_to_traceable_per90_features(self):
        squads = [
            {
                "team_id": 10,
                "team": "Current Club",
                "player_id": 9,
                "player": "Forward",
                "squad_group": "attackers",
                "position": "ST",
                "age": 24,
                "injury": None,
            }
        ]
        teams = [
            {
                "team_id": 10,
                "primary_league_id": 47,
                "primary_league": "Premier League",
                "premier_league_2026_27": True,
                "ucl_status": None,
            }
        ]
        history = [
            {
                "match_id": 1,
                "competition_id": 47,
                "competition": "Premier League",
                "team_id": 11,
                "team": "Old Club",
                "player_id": 9,
                "metrics": {
                    "minutes_played": {"value": 90},
                    "goals": {"value": 1},
                    "assists": {"value": 0},
                    "expected_goals_non_penalty": {"value": 0.5},
                    "expected_assists": {"value": 0.2},
                    "touches_opp_box": {"value": 5},
                    "ShotsOnTarget": {"value": 2},
                    "chances_created": {"value": 3},
                    "dribbles_succeeded": {"value": 1},
                },
            },
            {
                "match_id": 2,
                "competition_id": 42,
                "competition": "Champions League",
                "team_id": 11,
                "team": "Old Club",
                "player_id": 9,
                "metrics": {
                    "minutes_played": {"value": 90},
                    "goals": {"value": 0},
                    "assists": {"value": 1},
                    "expected_goals": {"value": 0.3},
                    "expected_assists": {"value": 0.1},
                },
            },
        ]
        season = [
            {
                "participant_id": 9,
                "competition": "Premier League",
                "metric": "goals",
                "value": 1,
                "sub_value": 0,
                "minutes": 90,
            },
            {
                "participant_id": 9,
                "competition": "Premier League",
                "metric": "poss_won_att_3rd",
                "value": 2.0,
                "minutes": 180,
            },
        ]
        result = build_player_features(squads, teams, history, season, self.config)[0]
        features = result["features"]
        self.assertEqual(result["sample"]["minutes"], 180.0)
        self.assertEqual(features["npg90"]["value"], 0.5)
        self.assertEqual(features["xg90"]["value"], 0.4)
        self.assertEqual(features["axa90"]["value"], 0.65)
        self.assertEqual(features["kp90"]["value"], 1.5)
        self.assertEqual(features["press90"]["value"], 2.0)
        self.assertIsNone(features["sca90"])
        self.assertIsNone(features["pc90"])

    def test_penalty_only_xg_is_not_counted_as_non_penalty_xg(self):
        squads = [
            {
                "team_id": 10,
                "team": "Club",
                "player_id": 9,
                "player": "Penalty Taker",
                "squad_group": "attackers",
                "position": "ST",
            }
        ]
        teams = [
            {
                "team_id": 10,
                "primary_league_id": 47,
                "primary_league": "Premier League",
            }
        ]
        history = [
            {
                "match_id": 1,
                "competition_id": 47,
                "competition": "Premier League",
                "team_id": 10,
                "team": "Club",
                "player_id": 9,
                "metrics": {
                    "minutes_played": {"value": 90},
                    "goals": {"value": 1},
                    "expected_goals": {"value": 0.79},
                },
            },
            {
                "match_id": 1,
                "competition_id": 47,
                "competition": "Premier League",
                "team_id": 10,
                "team": "Club",
                "player_id": 10,
                "metrics": {
                    "minutes_played": {"value": 90},
                    "expected_goals": {"value": 0.2},
                    "expected_goals_non_penalty": {"value": 0.2},
                },
            },
        ]
        season = [
            {
                "participant_id": 9,
                "competition": "Premier League",
                "metric": "goals",
                "value": 1,
                "sub_value": 1,
                "minutes": 90,
            }
        ]
        result = build_player_features(squads, teams, history, season, self.config)[0]
        self.assertEqual(result["features"]["npg90"]["value"], 0.0)
        self.assertEqual(result["features"]["xg90"]["value"], 0.0)


if __name__ == "__main__":
    unittest.main()
