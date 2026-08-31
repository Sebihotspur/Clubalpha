import copy
import unittest

from clubalpha.contextual_backtest import (
    RESULT_VERSION,
    evaluate_contextual_backtest,
    evaluate_goal_coefficient_ablation,
    validate_contextual_results,
)


def prediction():
    probabilities = {
        "home_win": 0.5,
        "draw": 0.25,
        "away_win": 0.25,
        "over": {"2.5": 0.55},
        "btts_yes": 0.5,
    }
    contextual_probabilities = {
        "home_win": 0.55,
        "draw": 0.24,
        "away_win": 0.21,
        "over": {"2.5": 0.57},
        "btts_yes": 0.51,
    }
    direction = {
        "continuous_signal": 0.2,
        "combined_reliability": 0.6,
        "preferred_route": {"key": "box_pressure"},
    }
    return {
        "fixture": {
            "match_id": 10,
            "kickoff_utc": "2026-08-28T19:00:00Z",
            "home_team_id": 1,
            "home_team": "Home",
            "away_team_id": 2,
            "away_team": "Away",
        },
        "baseline": {
            "predicted_xg": {"home": 1.5, "away": 1.0, "total": 2.5},
            "probabilities": probabilities,
        },
        "contextual": {
            "predicted_xg": {"home": 1.7, "away": 0.9, "total": 2.6},
            "probabilities": contextual_probabilities,
        },
        "directional_context": {
            "home_attack": direction,
            "away_attack": {**direction, "continuous_signal": -0.2},
        },
    }


def result():
    starters = list(range(100, 111))
    return {
        "result_version": RESULT_VERSION,
        "recorded_at_utc": "2026-08-29T00:00:00Z",
        "match_id": 10,
        "season": "2026/2027",
        "kickoff_utc": "2026-08-28T19:00:00Z",
        "home_team_id": 1,
        "home_team": "Home",
        "away_team_id": 2,
        "away_team": "Away",
        "final_home_goals": 2,
        "final_away_goals": 1,
        "outcome": "home_win",
        "actual_xg": {"home": 1.8, "away": 0.8, "total": 2.6},
        "home_stats": {},
        "away_stats": {},
        "home_lineup": {"starter_ids": starters, "formation": "4-3-3"},
        "away_lineup": {
            "starter_ids": list(range(200, 211)),
            "formation": "4-4-2",
        },
        "source": "FotMob",
        "source_match_id": "10",
    }


class ContextualBacktestTests(unittest.TestCase):
    def test_result_validates_against_frozen_match(self):
        validation = validate_contextual_results([prediction()], [result()])
        self.assertEqual(validation["completed_results"], 1)
        self.assertTrue(validation["complete"])

    def test_duplicate_match_result_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate match ids"):
            validate_contextual_results([prediction()], [result(), result()])

    def test_result_requires_exact_declared_lineups(self):
        observed = copy.deepcopy(result())
        observed["home_lineup"]["starter_ids"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "exact home starting XI"):
            validate_contextual_results([prediction()], [observed])

    def test_context_improvement_is_positive_when_errors_fall(self):
        report = evaluate_contextual_backtest([prediction()], [result()])
        improvements = report["metrics"][
            "holy_grail_improvement_positive_is_better"
        ]
        self.assertGreater(improvements["xg_side_mae"], 0)
        self.assertGreater(improvements["one_x_two_brier"], 0)
        self.assertEqual(report["diagnostics"]["outcome_hits"], 1)

    def test_lineup_snapshot_is_scored(self):
        home_ids = list(range(100, 111))
        away_ids = list(range(200, 211))
        snapshot = {
            "snapshot_version": "test",
            "clubs": [
                {
                    "team_id": 1,
                    "team": "Home",
                    "formation": "4-3-3",
                    "expected_xi": [{"player_id": value} for value in home_ids],
                },
                {
                    "team_id": 2,
                    "team": "Away",
                    "formation": "4-2-3-1",
                    "expected_xi": [{"player_id": value} for value in away_ids],
                },
            ],
        }
        report = evaluate_contextual_backtest(
            [prediction()], [result()], lineup_snapshot=snapshot
        )
        lineup = report["lineup_projection"]
        self.assertEqual(lineup["mean_xi_hits_of_11"], 11.0)
        self.assertEqual(lineup["formation_accuracy"], 0.5)

    def test_goal_coefficient_ablation_uses_only_frozen_candidates(self):
        base = copy.deepcopy(prediction())
        base["fixture_intelligence"] = {
            "home": {"fixture_signal_z": 1.0},
            "away": {"fixture_signal_z": -0.5},
        }
        base["predicted_xg"] = base["baseline"]["predicted_xg"]
        artifact = {
            "version": "goal-test",
            "trained_through": "2026-08-24",
            "coefficient": 0.1,
            "point_coefficient": 0.2,
            "raw_coefficient": 0.3,
        }
        report = evaluate_goal_coefficient_ablation([base], [result()], artifact)
        self.assertEqual(len(report["candidates"]), 4)
        self.assertFalse(report["outcomes_used_to_choose_candidates"])
        self.assertIn(
            report["best_side_xg_mae_candidate"],
            {row["candidate"] for row in report["candidates"]},
        )


if __name__ == "__main__":
    unittest.main()
