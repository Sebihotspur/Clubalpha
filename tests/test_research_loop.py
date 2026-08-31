import copy
import unittest

from clubalpha.contextual_backtest import RESULT_VERSION
from clubalpha.research_loop import build_research_state


CONFIG = {
    "version": "clubalpha_research_loop_v1",
    "status": "research_state_only",
    "learning_target": "observed_fotmob_xg_residual_against_locked_base_forecast",
    "xg_floor": 0.15,
    "recency_half_life_days": 45.0,
    "prior_match_equivalents": 3.0,
    "minimum_observation_reliability": 0.5,
    "lineup_prior_hit_rate": 0.8,
    "neutral_log_residual": 0.05,
    "promotion_gates": {
        "minimum_team_matches": 5,
        "minimum_route_observations": 5,
        "minimum_effective_evidence": 3.0,
        "minimum_absolute_posterior_log_residual": 0.08,
        "minimum_direction_consistency": 0.6,
        "mode": "propose_only",
    },
    "review_thresholds": {
        "lineup_hit_rate_below": 0.75,
        "formation_accuracy_below": 0.7,
    },
    "locked_boundaries": {
        "player_alpha_formulas_mutable": False,
        "base_60_30_10_weights_mutable": False,
        "historical_residual_cap_mutable": False,
        "frozen_predictions_mutable": False,
        "automatic_code_rewrite_allowed": False,
        "automatic_capital_authorization_allowed": False,
        "research_state_can_update_automatically": True,
    },
}


def prediction(match_id=1, kickoff="2026-08-28T19:00:00Z"):
    probabilities = {
        "home_win": 0.5,
        "draw": 0.25,
        "away_win": 0.25,
        "over": {"2.5": 0.55},
        "btts_yes": 0.5,
    }
    direction = {
        "continuous_signal": 0.2,
        "combined_reliability": 0.6,
        "preferred_route": {"key": "box_pressure"},
    }
    return {
        "fixture": {
            "match_id": match_id,
            "kickoff_utc": kickoff,
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
            "predicted_xg": {"home": 1.6, "away": 0.95, "total": 2.55},
            "probabilities": {
                **probabilities,
                "home_win": 0.53,
                "draw": 0.24,
                "away_win": 0.23,
            },
        },
        "directional_context": {
            "home_attack": direction,
            "away_attack": {**direction, "continuous_signal": -0.2},
        },
    }


def result(match_id=1, kickoff="2026-08-28T19:00:00Z"):
    home_ids = list(range(100, 111))
    away_ids = list(range(200, 211))
    return {
        "result_version": RESULT_VERSION,
        "recorded_at_utc": "2026-08-31T00:00:00Z",
        "match_id": match_id,
        "season": "2026/2027",
        "kickoff_utc": kickoff,
        "home_team_id": 1,
        "home_team": "Home",
        "away_team_id": 2,
        "away_team": "Away",
        "final_home_goals": 3,
        "final_away_goals": 0,
        "outcome": "home_win",
        "actual_xg": {"home": 2.4, "away": 0.8, "total": 3.2},
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
    }


def snapshot():
    return {
        "snapshot_version": "lineup-test",
        "clubs": [
            {
                "team_id": 1,
                "team": "Home",
                "formation": "4-3-3",
                "expected_xi": [
                    {"player_id": value, "player": f"H{value}"}
                    for value in range(100, 111)
                ],
            },
            {
                "team_id": 2,
                "team": "Away",
                "formation": "4-4-2",
                "expected_xi": [
                    {"player_id": value, "player": f"A{value}"}
                    for value in range(200, 211)
                ],
            },
        ],
    }


class ResearchLoopTests(unittest.TestCase):
    def test_one_match_updates_state_but_cannot_promote(self):
        state = build_research_state(
            [prediction()], [result()], snapshot(), CONFIG, as_of="2026-08-31"
        )
        home = next(team for team in state["teams"] if team["team"] == "Home")
        belief = home["beliefs"]["attack_creation"]
        self.assertGreater(belief["posterior_multiplier"], 1.0)
        self.assertLess(
            abs(belief["posterior_log_residual"]),
            abs(belief["raw_weighted_mean_log_residual"]),
        )
        self.assertFalse(belief["promotion_candidate"])
        self.assertEqual(state["forecast_handoff"]["automatically_applied"], 0)

    def test_repeated_consistent_evidence_can_only_propose(self):
        predictions = []
        results = []
        for index in range(5):
            kickoff = f"2026-08-{24 + index:02d}T19:00:00Z"
            predictions.append(prediction(index + 1, kickoff))
            results.append(result(index + 1, kickoff))
        state = build_research_state(
            predictions, results, snapshot(), CONFIG, as_of="2026-08-31"
        )
        home = next(team for team in state["teams"] if team["team"] == "Home")
        self.assertTrue(home["beliefs"]["attack_creation"]["promotion_candidate"])
        self.assertGreaterEqual(state["forecast_handoff"]["eligible_candidates"], 1)
        self.assertEqual(state["forecast_handoff"]["automatically_applied"], 0)

    def test_scoreline_variance_does_not_change_xg_strength_target(self):
        high_score = result()
        low_score = copy.deepcopy(high_score)
        low_score["final_home_goals"] = 1
        high = build_research_state(
            [prediction()], [high_score], snapshot(), CONFIG, as_of="2026-08-31"
        )
        low = build_research_state(
            [prediction()], [low_score], snapshot(), CONFIG, as_of="2026-08-31"
        )
        high_home = next(team for team in high["teams"] if team["team"] == "Home")
        low_home = next(team for team in low["teams"] if team["team"] == "Home")
        self.assertEqual(
            high_home["beliefs"]["attack_creation"],
            low_home["beliefs"]["attack_creation"],
        )
        self.assertNotEqual(
            high_home["finishing_variance"], low_home["finishing_variance"]
        )

    def test_locked_boundary_cannot_be_weakened(self):
        config = copy.deepcopy(CONFIG)
        config["locked_boundaries"]["player_alpha_formulas_mutable"] = True
        with self.assertRaisesRegex(ValueError, "weakens a locked boundary"):
            build_research_state(
                [prediction()], [result()], snapshot(), config, as_of="2026-08-31"
            )


if __name__ == "__main__":
    unittest.main()
