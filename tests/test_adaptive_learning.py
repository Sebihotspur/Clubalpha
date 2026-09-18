import copy
import unittest

from clubalpha.adaptive_learning import (
    build_adaptive_learning_state,
    build_match_learning_cards,
)
from clubalpha.contextual_backtest import RESULT_VERSION


CONFIG = {
    "version": "clubalpha_research_loop_v1",
    "xg_floor": 0.15,
    "adaptive_learning": {
        "memory": {
            "fast": {
                "half_life_days": 7,
                "prior_match_equivalents": 2,
                "minimum_observations": 2,
            },
            "medium": {
                "half_life_days": 28,
                "prior_match_equivalents": 3,
                "minimum_observations": 3,
            },
            "slow": {
                "half_life_days": 120,
                "prior_match_equivalents": 8,
                "minimum_observations": 8,
            },
        },
        "challenger": {
            "minimum_prior_team_matches": 2,
            "minimum_validation_matches": 20,
            "maximum_absolute_log_xg_adjustment": 0.12,
            "minimum_brier_improvement": 0,
            "minimum_xg_mae_improvement": 0,
            "promotion_mode": "human_review_only",
        },
    },
    "locked_boundaries": {
        "player_alpha_formulas_mutable": False,
        "base_60_30_10_weights_mutable": False,
        "frozen_predictions_mutable": False,
        "automatic_code_rewrite_allowed": False,
        "automatic_capital_authorization_allowed": False,
    },
}


def prediction(match_id: int, day: int) -> dict:
    probabilities = {
        "home_win": 0.52,
        "draw": 0.25,
        "away_win": 0.23,
        "over": {"2.5": 0.55},
        "btts_yes": 0.5,
    }
    direction = {
        "continuous_signal": 0.15,
        "combined_reliability": 0.7,
        "preferred_route": {"key": "box_pressure"},
    }
    return {
        "fixture": {
            "match_id": match_id,
            "kickoff_utc": f"2026-09-{day:02d}T14:00:00Z",
            "home_team_id": 1,
            "home_team": "Home",
            "away_team_id": 2,
            "away_team": "Away",
            "source_scope": "test_league",
        },
        "baseline": {
            "predicted_xg": {"home": 1.5, "away": 1.0, "total": 2.5},
            "probabilities": probabilities,
        },
        "contextual": {
            "predicted_xg": {"home": 1.6, "away": 0.95, "total": 2.55},
            "probabilities": probabilities,
        },
        "directional_context": {
            "home_attack": direction,
            "away_attack": {**direction, "continuous_signal": -0.15},
        },
    }


def result(match_id: int, day: int, *, rotated: bool = False) -> dict:
    home_ids = list(range(100, 111))
    away_ids = list(range(200, 211))
    if rotated:
        home_ids = list(range(300, 311))
    return {
        "result_version": RESULT_VERSION,
        "recorded_at_utc": "2026-09-12T00:00:00Z",
        "match_id": match_id,
        "season": "2026/2027",
        "kickoff_utc": f"2026-09-{day:02d}T14:00:00Z",
        "home_team_id": 1,
        "home_team": "Home",
        "away_team_id": 2,
        "away_team": "Away",
        "final_home_goals": 0,
        "final_away_goals": 1,
        "outcome": "away_win",
        "actual_xg": {"home": 2.2, "away": 0.8, "total": 3.0},
        "home_stats": {},
        "away_stats": {},
        "home_lineup": {
            "starter_ids": home_ids,
            "starters": [
                {"player_id": value, "player": f"H{value}"} for value in home_ids
            ],
            "formation": "4-3-3",
        },
        "away_lineup": {
            "starter_ids": away_ids,
            "starters": [
                {"player_id": value, "player": f"A{value}"} for value in away_ids
            ],
            "formation": "4-4-2",
        },
        "source": "FotMob",
        "source_match_id": str(match_id),
        "source_coverage_level": "xG",
    }


def lineup_snapshot(predictions: list[dict]) -> dict:
    clubs = []
    for row in predictions:
        match_id = row["fixture"]["match_id"]
        clubs.extend(
            [
                {
                    "team_id": 1,
                    "team": "Home",
                    "formation": "4-3-3",
                    "expected_xi": [
                        {"player_id": value, "player": f"H{value}"}
                        for value in range(100, 111)
                    ],
                    "next_fixture": {"match_id": match_id},
                },
                {
                    "team_id": 2,
                    "team": "Away",
                    "formation": "4-4-2",
                    "expected_xi": [
                        {"player_id": value, "player": f"A{value}"}
                        for value in range(200, 211)
                    ],
                    "next_fixture": {"match_id": match_id},
                },
            ]
        )
    return {"snapshot_version": "adaptive-test", "clubs": clubs}


class AdaptiveLearningTests(unittest.TestCase):
    def test_card_separates_process_from_finishing_outcome(self):
        predictions = [prediction(1, 1)]
        cards = build_match_learning_cards(
            predictions, [result(1, 1)], lineup_snapshot(predictions), CONFIG
        )
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["observed"]["xg_process_outcome"], "home_win")
        self.assertEqual(card["error_attribution"]["primary"], "outcome_variance")
        self.assertLess(
            card["error_attribution"]["outcome_learning_weight"],
            card["error_attribution"]["process_learning_weight"],
        )
        self.assertFalse(card["governance"]["player_alpha_changed"])

    def test_large_lineup_miss_is_attributed_to_projection(self):
        predictions = [prediction(1, 1)]
        cards = build_match_learning_cards(
            predictions,
            [result(1, 1, rotated=True)],
            lineup_snapshot(predictions),
            CONFIG,
        )
        attribution = cards[0]["error_attribution"]
        self.assertTrue(attribution["major_rotation_or_lineup_miss"])
        self.assertEqual(attribution["primary"], "lineup_projection")

    def test_three_speed_memory_and_challenger_remain_non_mutating(self):
        predictions = [prediction(index, index) for index in range(1, 5)]
        results = [result(index, index) for index in range(1, 5)]
        state = build_adaptive_learning_state(
            predictions,
            results,
            lineup_snapshot(predictions),
            CONFIG,
            as_of="2026-09-12",
        )
        self.assertEqual(state["completed_match_cards"], 4)
        self.assertEqual(set(state["memory"]["teams"]), {"fast", "medium", "slow"})
        self.assertEqual(
            state["champion_challenger"]["champion"]["fixtures"], 2
        )
        self.assertFalse(
            state["champion_challenger"]["promotion_gate"]["sample_sufficient"]
        )
        self.assertEqual(
            state["champion_challenger"]["promotion_gate"]["status"],
            "hold_champion",
        )
        self.assertFalse(
            state["governance"]["challenger_updates_champion_automatically"]
        )
        self.assertFalse(
            state["governance"]["player_alpha_formula_updates_automatically"]
        )

    def test_locked_boundary_cannot_be_weakened(self):
        config = copy.deepcopy(CONFIG)
        config["locked_boundaries"]["base_60_30_10_weights_mutable"] = True
        predictions = [prediction(1, 1)]
        with self.assertRaisesRegex(ValueError, "weakens a locked boundary"):
            build_adaptive_learning_state(
                predictions,
                [result(1, 1)],
                lineup_snapshot(predictions),
                config,
                as_of="2026-09-12",
            )


if __name__ == "__main__":
    unittest.main()
