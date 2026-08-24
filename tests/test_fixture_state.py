import unittest
from copy import deepcopy

from clubalpha.fixture_state import (
    build_fixture_state,
    build_fixture_states,
    form_matchup,
    historical_residuals,
    lineup_quality,
)


CONFIG = {
    "version": "test_fixture_state_v1",
    "source_versions": {
        "club_form": "form-v1",
        "squad_selection_prior": "selection-v1",
        "historical_fixtures": "history-v2",
    },
    "component_weights": {
        "club_form": 0.6,
        "player_quality_lineup": 0.3,
        "historical_residual": 0.1,
    },
    "lineup_confidence": {"evidence_prior": 2.0},
    "goal_engine": {
        "calibration_coefficient": None,
        "formula": "baseline * exp(beta * signal)",
    },
    "decision_boundaries": {
        "probability_ready": False,
        "market_ready": False,
        "capital_deployment_ready": False,
    },
}

HISTORY_CONFIG = {
    "recency": {"team_max_age_days": 1095},
    "venue_history": {"prior_weighted_matches": 1.0},
    "direct_history": {
        "prior_weighted_matches": 1.0,
        "same_venue_multiplier": 1.25,
        "maximum_signal_share": 0.15,
    },
}


def form(team_id, attack, defense, confidence=0.5):
    return {
        "form_version": "form-v1",
        "as_of": "2026-08-18",
        "team_id": team_id,
        "team": f"Team {team_id}",
        "attack_z": attack,
        "defense_z": defense,
        "attack_confidence": confidence,
        "defense_confidence": confidence,
        "quality_flags": [],
    }


def selection(team_id, unavailable_strong_player=False):
    players = []
    for player_id in range(1, 13):
        baseline = 90.0 if player_id <= 11 else 0.0
        adjusted = baseline
        alpha = 1.0 if player_id == 1 else 0.0
        if unavailable_strong_player and player_id == 1:
            adjusted = 0.0
        if unavailable_strong_player and player_id == 12:
            adjusted = 90.0
        players.append(
            {
                "player_id": team_id * 100 + player_id,
                "alpha_ability_z": alpha,
                "baseline_expected_minutes": baseline,
                "expected_minutes_prior": adjusted,
            }
        )
    return {
        "selection_prior_version": "selection-v1",
        "as_of": "2026-08-18",
        "team_id": team_id,
        "players": players,
        "evidence": {
            "coverage_adjusted_recent_matches": 1.0,
            "historical_prior_strength": 2.0,
        },
        "decision_boundaries": {
            "lineup_prior_ready": True,
            "expected_team_minutes": 990.0,
            "fixture_specific": False,
            "confirmed_lineup": False,
        },
        "quality_flags": [],
    }


def aggregate(attack, defense, confidence):
    return {
        "attack_strength_z_raw": attack,
        "defense_strength_z_raw": defense,
        "confidence": confidence,
    }


def historical_fixture(direct_share=0.0):
    return {
        "historical_fixtures_version": "history-v2",
        "as_of": "2026-08-18",
        "fixture": {
            "match_id": 100,
            "competition_id": 47,
            "competition": "Premier League",
            "source_scope": "premier_league_current",
            "round": 2,
            "kickoff_utc": "2026-08-22T15:00:00Z",
            "home_team_id": 1,
            "home_team": "Home",
            "away_team_id": 2,
            "away_team": "Away",
        },
        "venue_history": {
            "home_team_at_home": aggregate(1.0, 0.0, 0.5),
            "away_team_away": aggregate(0.0, 0.0, 0.5),
        },
        "direct_history": {
            "signal_share": direct_share,
            "home_team_view": aggregate(2.0, 0.0, 0.8),
            "away_team_view": aggregate(0.0, -2.0, 0.8),
        },
        "competition_baseline": {
            "competition_family": "premier_league",
            "proxy_used": False,
            "confidence": 0.9,
            "expected_goals": {
                "home_mean": 1.6,
                "away_mean": 1.2,
                "total_mean": 2.8,
            },
        },
        "quality_flags": [],
    }


def history_rows():
    return [
        {
            "team_id": 1,
            "venue": "home",
            "age_days": 10,
            "history_weight": 1.0,
            "attack_strength_z": 1.0,
            "defense_strength_z": 0.0,
        },
        {
            "team_id": 1,
            "venue": "away",
            "age_days": 20,
            "history_weight": 1.0,
            "attack_strength_z": 0.0,
            "defense_strength_z": 0.0,
        },
        {
            "team_id": 2,
            "venue": "away",
            "age_days": 10,
            "history_weight": 1.0,
            "attack_strength_z": 0.0,
            "defense_strength_z": 0.0,
        },
        {
            "team_id": 2,
            "venue": "home",
            "age_days": 20,
            "history_weight": 1.0,
            "attack_strength_z": 0.0,
            "defense_strength_z": 0.0,
        },
    ]


class FixtureStateTests(unittest.TestCase):
    def test_form_released_z_is_not_confidence_shrunk_twice(self):
        result = form_matchup(form(1, 0.8, 0.1, 0.25), form(2, 0.2, 0.3, 0.25))
        self.assertAlmostEqual(result["raw_matchup_z"], 0.5)
        self.assertAlmostEqual(result["effective_signal_z"], 0.5)
        self.assertEqual(result["confidence"], 0.25)
        self.assertTrue(result["source_confidence_already_applied"])

    def test_lineup_quality_uses_expected_minutes_and_neutral_missing_grades(self):
        source = selection(1, unavailable_strong_player=True)
        source["players"][1]["alpha_ability_z"] = None
        result = lineup_quality(source, CONFIG)
        self.assertAlmostEqual(result["baseline_quality_z"], 90 / 990, places=6)
        self.assertEqual(result["availability_adjusted_quality_z"], 0.0)
        self.assertAlmostEqual(result["quality_delta_z"], -90 / 990, places=6)
        self.assertLess(result["alpha_minute_coverage"], 1.0)

    def test_missing_selection_is_neutral_and_explicit(self):
        result = lineup_quality(None, CONFIG)
        self.assertEqual(result["quality_delta_z"], 0.0)
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("missing_squad_selection_prior", result["quality_flags"])

    def test_history_is_venue_minus_general_and_direct_share_is_capped(self):
        result = historical_residuals(
            historical_fixture(direct_share=0.9), history_rows(), HISTORY_CONFIG
        )["home"]
        self.assertAlmostEqual(result["venue_matchup_z"], 0.5)
        self.assertAlmostEqual(result["general_matchup_z"], 0.25)
        self.assertAlmostEqual(result["venue_residual_z"], 0.25)
        self.assertEqual(result["direct_signal_share"], 0.15)
        self.assertLessEqual(result["maximum_direct_signal_share"], 0.15)

    def test_competition_baseline_stays_outside_60_30_10_and_uncalibrated(self):
        state = build_fixture_state(
            historical_fixture(),
            {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
            {1: selection(1, True), 2: selection(2)},
            history_rows(),
            CONFIG,
            HISTORY_CONFIG,
        )
        self.assertEqual(state["goal_engine_input"]["competition_baseline"]["home_xg"], 1.6)
        self.assertEqual(state["goal_engine_input"]["calibration_coefficient"], None)
        self.assertIsNone(state["goal_engine_input"]["home_calibrated_xg"])
        self.assertAlmostEqual(sum(state["component_weights"].values()), 1.0)
        contributions = state["home"]["weighted_contributions_z"]
        self.assertAlmostEqual(
            state["home"]["fixture_signal_z"], sum(contributions.values()), places=6
        )
        self.assertFalse(state["decision_boundaries"]["probability_ready"])
        self.assertFalse(state["decision_boundaries"]["capital_deployment_ready"])

    def test_builder_rejects_mismatched_as_of_dates(self):
        forms = [form(1, 0.5, 0.4), form(2, 0.1, 0.2)]
        forms[0]["as_of"] = "2026-08-17"
        with self.assertRaisesRegex(ValueError, "different as-of dates"):
            build_fixture_states(
                [historical_fixture()],
                forms,
                [selection(1), selection(2)],
                history_rows(),
                CONFIG,
                HISTORY_CONFIG,
            )

    def test_builder_rejects_weights_that_do_not_sum_to_one(self):
        config = deepcopy(CONFIG)
        config["component_weights"]["historical_residual"] = 0.2
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            build_fixture_states(
                [historical_fixture()],
                [form(1, 0.5, 0.4), form(2, 0.1, 0.2)],
                [selection(1), selection(2)],
                history_rows(),
                config,
                HISTORY_CONFIG,
            )

    def test_fitted_coefficient_materializes_xg_without_changing_baseline(self):
        config = deepcopy(CONFIG)
        config["goal_engine"]["calibration_coefficient"] = 0.5
        state = build_fixture_state(
            historical_fixture(),
            {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
            {1: selection(1), 2: selection(2)},
            history_rows(),
            config,
            HISTORY_CONFIG,
        )
        self.assertEqual(
            state["goal_engine_input"]["competition_baseline"]["home_xg"], 1.6
        )
        self.assertIsNotNone(state["goal_engine_input"]["home_calibrated_xg"])
        self.assertTrue(state["decision_boundaries"]["goal_engine_calibrated"])


if __name__ == "__main__":
    unittest.main()
