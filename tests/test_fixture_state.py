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
    "component_scaling": {
        "method": "past_only_training_standard_deviation",
        "require_trained_before_as_of": True,
        "required_components": [
            "club_form",
            "player_quality_lineup",
            "historical_residual",
        ],
    },
    "decision_boundaries": {
        "probability_ready": False,
        "market_ready": False,
        "capital_deployment_ready": False,
    },
}

HISTORY_CONFIG = {
    "version": "history-v2",
    "recency": {"team_max_age_days": 1095},
    "venue_history": {"prior_weighted_matches": 1.0},
    "direct_history": {
        "prior_weighted_matches": 1.0,
        "same_venue_multiplier": 1.25,
        "maximum_signal_share": 0.15,
    },
}


def historical_manifest(history_count=4):
    return {
        "historical_fixtures_version": "history-v2",
        "as_of": "2026-08-18",
        "outputs": {"fixtures": 1, "historical_team_match_rows": history_count},
    }


def scaling_artifact(trained_through="2026-08-17"):
    return {
        "version": "test-scales-v1",
        "method": "past_only_training_standard_deviation",
        "trained_through": trained_through,
        "training_snapshot_count": 20,
        "training_fixture_sides": 400,
        "scales": {
            "club_form": 0.5,
            "player_quality_lineup": 0.25,
            "historical_residual": 0.1,
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
            "kickoff_utc": "2026-08-08T15:00:00Z",
            "age_days": 10,
            "history_weight": 1.0,
            "attack_strength_z": 1.0,
            "defense_strength_z": 0.0,
        },
        {
            "team_id": 1,
            "venue": "away",
            "kickoff_utc": "2026-07-29T15:00:00Z",
            "age_days": 20,
            "history_weight": 1.0,
            "attack_strength_z": 0.0,
            "defense_strength_z": 0.0,
        },
        {
            "team_id": 2,
            "venue": "away",
            "kickoff_utc": "2026-08-08T15:00:00Z",
            "age_days": 10,
            "history_weight": 1.0,
            "attack_strength_z": 0.0,
            "defense_strength_z": 0.0,
        },
        {
            "team_id": 2,
            "venue": "home",
            "kickoff_utc": "2026-07-29T15:00:00Z",
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
        self.assertEqual(result["projected_quality_z"], 0.0)
        self.assertAlmostEqual(result["availability_delta_z"], -90 / 990, places=6)
        self.assertLess(result["alpha_minute_coverage"], 1.0)

    def test_missing_selection_is_neutral_and_explicit(self):
        result = lineup_quality(None, CONFIG)
        self.assertEqual(result["projected_quality_z"], 0.0)
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("missing_squad_selection_prior", result["quality_flags"])

    def test_player_quality_uses_absolute_projected_xi_not_only_availability_delta(self):
        home = selection(1)
        away = selection(2)
        away["players"][0]["alpha_ability_z"] = -1.0
        state = build_fixture_state(
            historical_fixture(),
            {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
            {1: home, 2: away},
            history_rows(),
            CONFIG,
            HISTORY_CONFIG,
        )
        component = state["home"]["components"]["player_quality_lineup"]
        self.assertGreater(component["raw_projected_quality_edge_z"], 0)
        self.assertGreater(component["effective_signal_z"], 0)
        self.assertEqual(home["players"][0]["baseline_expected_minutes"], 90.0)

    def test_incomplete_lineup_matchup_is_fully_neutral(self):
        state = build_fixture_state(
            historical_fixture(),
            {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
            {1: selection(1)},
            history_rows(),
            CONFIG,
            HISTORY_CONFIG,
        )
        component = state["home"]["components"]["player_quality_lineup"]
        self.assertFalse(component["available"])
        self.assertEqual(component["effective_signal_z"], 0.0)

    def test_history_is_venue_minus_general_and_direct_share_is_capped(self):
        result = historical_residuals(
            historical_fixture(direct_share=0.9), history_rows(), HISTORY_CONFIG
        )["home"]
        self.assertAlmostEqual(result["venue_matchup_z"], 0.5)
        self.assertAlmostEqual(result["general_matchup_z"], 0.25)
        self.assertAlmostEqual(result["venue_residual_z"], 0.25)
        self.assertEqual(result["direct_signal_share"], 0.15)
        self.assertLessEqual(result["maximum_direct_signal_share"], 0.15)

    def test_future_historical_row_is_rejected_even_when_age_looks_recent(self):
        future = {
            **history_rows()[0],
            "kickoff_utc": "2026-08-20T15:00:00Z",
            "age_days": 1,
        }
        with self.assertRaisesRegex(ValueError, "after Fixture State as-of"):
            historical_residuals(
                historical_fixture(), history_rows() + [future], HISTORY_CONFIG
            )

    def test_competition_baseline_stays_outside_composite_and_no_xg_is_fitted(self):
        state = build_fixture_state(
            historical_fixture(),
            {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
            {1: selection(1, True), 2: selection(2)},
            history_rows(),
            CONFIG,
            HISTORY_CONFIG,
        )
        self.assertEqual(state["goal_model_handoff"]["competition_baseline"]["home_xg"], 1.6)
        self.assertNotIn("home_calibrated_xg", state["goal_model_handoff"])
        self.assertTrue(state["goal_model_handoff"]["calibration_owned_by_separate_layer"])
        self.assertAlmostEqual(sum(state["component_weights"].values()), 1.0)
        self.assertIsNone(state["home"]["fixture_signal_z"])
        self.assertTrue(
            all(
                value is None
                for value in state["home"]["weighted_contributions_z"].values()
            )
        )
        self.assertFalse(state["decision_boundaries"]["component_scaling_ready"])
        self.assertAlmostEqual(
            state["goal_model_handoff"]["competition_baseline"]["total_xg"], 2.8
        )
        self.assertFalse(state["decision_boundaries"]["probability_ready"])
        self.assertFalse(state["decision_boundaries"]["capital_deployment_ready"])

    def test_past_only_scale_artifact_activates_60_30_10_composite(self):
        state = build_fixture_state(
            historical_fixture(),
            {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
            {1: selection(1, True), 2: selection(2)},
            history_rows(),
            CONFIG,
            HISTORY_CONFIG,
            scaling_artifact(),
        )
        contributions = state["home"]["weighted_contributions_z"]
        self.assertAlmostEqual(
            state["home"]["fixture_signal_z"], sum(contributions.values()), places=6
        )
        self.assertTrue(state["decision_boundaries"]["component_scaling_ready"])

    def test_scale_artifact_must_precede_fixture_state_date(self):
        with self.assertRaisesRegex(ValueError, "strictly before"):
            build_fixture_state(
                historical_fixture(),
                {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
                {1: selection(1), 2: selection(2)},
                history_rows(),
                CONFIG,
                HISTORY_CONFIG,
                scaling_artifact("2026-08-18"),
            )

    def test_scale_artifact_requires_training_sample_provenance(self):
        artifact = scaling_artifact()
        artifact.pop("training_fixture_sides")
        with self.assertRaisesRegex(ValueError, "positive training_fixture_sides"):
            build_fixture_state(
                historical_fixture(),
                {1: form(1, 0.5, 0.4), 2: form(2, 0.1, 0.2)},
                {1: selection(1), 2: selection(2)},
                history_rows(),
                CONFIG,
                HISTORY_CONFIG,
                artifact,
            )

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
                historical_manifest(),
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
                historical_manifest(),
            )

    def test_builder_rejects_mismatched_historical_manifest(self):
        manifest = historical_manifest()
        manifest["as_of"] = "2026-08-19"
        with self.assertRaisesRegex(ValueError, "manifest as-of"):
            build_fixture_states(
                [historical_fixture()],
                [form(1, 0.5, 0.4), form(2, 0.1, 0.2)],
                [selection(1), selection(2)],
                history_rows(),
                CONFIG,
                HISTORY_CONFIG,
                manifest,
            )


if __name__ == "__main__":
    unittest.main()
