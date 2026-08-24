import unittest
from copy import deepcopy
from datetime import date

from clubalpha.historical_fixtures import (
    aggregate_competition_baseline,
    aggregate_history,
    build_fixture_history,
    build_historical_fixture_intelligence,
    dedupe_team_match_rows,
    score_history_rows,
    select_target_fixtures,
)


class HistoricalFixturesTests(unittest.TestCase):
    def setUp(self):
        self.as_of = date(2026, 8, 18)
        self.config = {
            "version": "test_historical_fixtures",
            "target_fixtures": {
                "source_scopes": ["premier_league_current"],
                "horizon_days": 14,
            },
            "performance_metrics": ["goals", "expected_goals"],
            "normalisation": {"minimum_peer_values": 2, "z_cap": 3.0},
            "recency": {"half_life_days": 180},
            "source_weights": {"default": 1.0},
            "venue_history": {"prior_weighted_matches": 1.0},
            "direct_history": {
                "prior_weighted_matches": 1.0,
                "same_venue_multiplier": 1.25,
                "maximum_signal_share": 0.25,
                "recent_meetings_limit": 5,
            },
            "quality": {
                "minimum_venue_confidence": 0.2,
                "minimum_direct_confidence": 0.2,
            },
        }
        self.league_policy = {
            "default_key": "Other",
            "default_offset": -0.9,
            "offsets": {
                "PL": 0.45,
                "Championship": -0.42,
                "Champions League": 0.36,
                "Other": -0.9,
            },
            "fotmob_league_id_to_key": {"47": "PL", "48": "Championship"},
        }

    def row(
        self,
        match_id,
        team_id,
        opponent_id,
        venue,
        goals_for,
        goals_against,
        *,
        competition_id=47,
        kickoff="2026-05-01T15:00:00Z",
        xg_for=1.5,
        xg_against=1.0,
        scope="premier_league_previous",
    ):
        return {
            "match_id": match_id,
            "source_scope": scope,
            "competition_id": competition_id,
            "competition": "Premier League" if competition_id == 47 else "Championship",
            "kickoff_utc": kickoff,
            "team_id": team_id,
            "team": f"Team {team_id}",
            "opponent_id": opponent_id,
            "opponent": f"Team {opponent_id}",
            "venue": venue,
            "cache_detail_available": True,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "expected_goals_for": xg_for,
            "expected_goals_against": xg_against,
        }

    def fixture(self, match_id=100, kickoff="2026-08-21T19:00:00Z"):
        return {
            "match_id": match_id,
            "source_scope": "premier_league_current",
            "competition_id": 47,
            "competition": "Premier League",
            "round": 1,
            "kickoff_utc": kickoff,
            "home_team_id": 1,
            "home_team": "Home",
            "away_team_id": 2,
            "away_team": "Away",
            "finished": False,
            "cancelled": False,
        }

    def test_dedupe_prefers_detailed_team_match_row(self):
        thin = {**self.row(1, 1, 2, "home", 1, 0), "cache_detail_available": False}
        detailed = self.row(1, 1, 2, "home", 1, 0, xg_for=2.0)
        result = dedupe_team_match_rows([thin], [detailed])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["expected_goals_for"], 2.0)

    def test_target_selection_respects_scope_as_of_and_horizon(self):
        fixtures = [
            self.fixture(100, "2026-08-21T19:00:00Z"),
            self.fixture(101, "2026-09-10T19:00:00Z"),
            {**self.fixture(102), "source_scope": "club_friendly"},
            {**self.fixture(103), "finished": True},
        ]
        result = select_target_fixtures(fixtures, self.as_of, self.config)
        self.assertEqual([row["match_id"] for row in result], [100])

    def test_scoring_excludes_future_history_and_applies_league_strength(self):
        rows = [
            self.row(1, 1, 9, "home", 2, 0, competition_id=47, xg_for=2.0),
            self.row(2, 9, 1, "away", 0, 2, competition_id=47, xg_for=0.5),
            self.row(3, 3, 8, "home", 2, 0, competition_id=48, xg_for=2.0),
            self.row(4, 8, 3, "away", 0, 2, competition_id=48, xg_for=0.5),
            self.row(
                5,
                1,
                9,
                "home",
                5,
                0,
                competition_id=47,
                kickoff="2026-08-19T15:00:00Z",
            ),
        ]
        scored, _ = score_history_rows(rows, self.as_of, self.config, self.league_policy)
        self.assertEqual({row["match_id"] for row in scored}, {1, 2, 3, 4})
        pl = next(row for row in scored if row["match_id"] == 1)
        championship = next(row for row in scored if row["match_id"] == 3)
        self.assertGreater(pl["attack_strength_z"], championship["attack_strength_z"])
        self.assertEqual(pl["league_strength_key"], "PL")
        self.assertEqual(championship["league_strength_key"], "Championship")

    def test_direct_history_same_venue_receives_more_evidence(self):
        base = {
            **self.row(1, 1, 2, "home", 2, 0),
            "history_weight": 1.0,
            "target_venue": "home",
            "attack_strength_z": 1.0,
            "defense_strength_z": 1.0,
        }
        opposite = {**base, "match_id": 2, "venue": "away"}
        same = aggregate_history([base], self.config, direct=True)
        other = aggregate_history([opposite], self.config, direct=True)
        self.assertGreater(same["weighted_match_evidence"], other["weighted_match_evidence"])

    def test_direct_and_team_history_can_use_different_decay_clocks(self):
        config = deepcopy(self.config)
        config["recency"] = {
            "team_half_life_days": 180,
            "direct_half_life_days": 360,
            "competition_baseline_half_life_days": 720,
        }
        rows = [
            self.row(1, 1, 2, "home", 2, 0, kickoff="2025-08-18T15:00:00Z"),
            self.row(2, 2, 1, "away", 0, 2, kickoff="2025-08-18T15:00:00Z"),
        ]
        scored, _ = score_history_rows(rows, self.as_of, config, self.league_policy)
        self.assertGreater(
            scored[0]["direct_history_weight"], scored[0]["history_weight"]
        )
        self.assertGreater(
            scored[0]["competition_baseline_weight"],
            scored[0]["direct_history_weight"],
        )

    def test_team_and_direct_context_respect_maximum_age(self):
        config = deepcopy(self.config)
        config["recency"] = {
            "half_life_days": 180,
            "team_max_age_days": 100,
            "direct_max_age_days": 100,
        }
        scored = [
            {
                **self.row(1, 1, 9, "home", 2, 0),
                "age_days": 30,
                "history_weight": 1.0,
                "attack_strength_z": 1.0,
                "defense_strength_z": 0.5,
            },
            {
                **self.row(2, 1, 2, "home", 5, 0),
                "age_days": 500,
                "history_weight": 1.0,
                "attack_strength_z": 3.0,
                "defense_strength_z": 3.0,
            },
            {
                **self.row(3, 2, 8, "away", 1, 1),
                "age_days": 30,
                "history_weight": 1.0,
                "attack_strength_z": 0.0,
                "defense_strength_z": 0.0,
            },
            {
                **self.row(4, 2, 1, "away", 0, 5),
                "age_days": 500,
                "history_weight": 1.0,
                "attack_strength_z": -3.0,
                "defense_strength_z": -3.0,
            },
        ]
        result = build_fixture_history(self.fixture(), scored, self.as_of, config)
        self.assertEqual(result["venue_history"]["home_team_at_home"]["matches"], 1)
        self.assertEqual(result["venue_history"]["away_team_away"]["matches"], 1)
        self.assertEqual(result["direct_history"]["meetings"], 0)

    def test_competition_baseline_uses_one_home_row_per_match(self):
        config = deepcopy(self.config)
        config["competition_baseline"] = {
            "enabled": True,
            "prior_weighted_matches": 1.0,
        }
        config["recency"]["competition_baseline_half_life_days"] = 730
        rows = [
            {
                **self.row(1, 1, 2, "home", 2, 1, xg_for=1.8, xg_against=0.9),
                "season": "2025/2026",
                "history_weight": 1.0,
                "competition_baseline_weight": 1.0,
            },
            {
                **self.row(1, 2, 1, "away", 1, 2, xg_for=0.9, xg_against=1.8),
                "season": "2025/2026",
                "history_weight": 1.0,
                "competition_baseline_weight": 1.0,
            },
            {
                **self.row(2, 3, 4, "home", 0, 0, xg_for=0.7, xg_against=0.6),
                "season": "2024/2025",
                "history_weight": 1.0,
                "competition_baseline_weight": 1.0,
            },
        ]
        baseline = aggregate_competition_baseline(self.fixture(), rows, config)
        self.assertIsNotNone(baseline)
        self.assertEqual(baseline["matches"], 2)
        self.assertEqual(baseline["goals"]["home_mean"], 1.0)
        self.assertEqual(baseline["goals"]["away_mean"], 0.5)
        self.assertEqual(baseline["seasons"], ["2024/2025", "2025/2026"])

    def test_no_direct_history_stays_explicit(self):
        scored = [
            {
                **self.row(1, 1, 9, "home", 2, 0),
                "history_weight": 1.0,
                "attack_strength_z": 1.0,
                "defense_strength_z": 0.5,
            },
            {
                **self.row(2, 2, 8, "away", 1, 1),
                "history_weight": 1.0,
                "attack_strength_z": 0.0,
                "defense_strength_z": 0.0,
            },
        ]
        result = build_fixture_history(self.fixture(), scored, self.as_of, self.config)
        self.assertEqual(result["direct_history"]["meetings"], 0)
        self.assertEqual(result["direct_history"]["signal_share"], 0.0)
        self.assertIn("no_direct_head_to_head", result["quality_flags"])
        self.assertFalse(result["decision_boundaries"]["probability_ready"])

    def test_direct_signal_share_never_exceeds_cap(self):
        scored = []
        for match_id in range(1, 21):
            home = {
                **self.row(match_id, 1, 2, "home", 3, 0, xg_for=3.0, xg_against=0.2),
                "history_weight": 1.0,
                "attack_strength_z": 2.0,
                "defense_strength_z": 2.0,
            }
            away = {
                **self.row(match_id, 2, 1, "away", 0, 3, xg_for=0.2, xg_against=3.0),
                "history_weight": 1.0,
                "attack_strength_z": -2.0,
                "defense_strength_z": -2.0,
            }
            scored.extend([home, away])
        result = build_fixture_history(self.fixture(), scored, self.as_of, self.config)
        self.assertEqual(result["direct_history"]["signal_share"], 0.25)

    def test_missing_xg_is_never_interpreted_as_zero(self):
        scored = [
            {
                **self.row(1, 1, 9, "home", 2, 0, xg_for=None, xg_against=None),
                "history_weight": 1.0,
                "attack_strength_z": 1.0,
                "defense_strength_z": 1.0,
            },
            {
                **self.row(2, 2, 8, "away", 1, 1, xg_for=None, xg_against=None),
                "history_weight": 1.0,
                "attack_strength_z": 0.0,
                "defense_strength_z": 0.0,
            },
        ]
        result = build_fixture_history(self.fixture(), scored, self.as_of, self.config)
        baseline = result["historical_signals"]["descriptive_xg_baseline"]
        self.assertIsNone(baseline["home"])
        self.assertIsNone(baseline["away"])
        self.assertIn("missing_xg_baseline", result["quality_flags"])

    def test_end_to_end_build_only_emits_selected_fixtures(self):
        rows = [
            self.row(1, 1, 9, "home", 2, 0),
            self.row(2, 9, 1, "away", 0, 2),
            self.row(3, 2, 8, "away", 1, 1),
            self.row(4, 8, 2, "home", 1, 1),
        ]
        outputs, scored, scales = build_historical_fixture_intelligence(
            [self.fixture(), self.fixture(101, "2026-09-10T19:00:00Z")],
            rows,
            self.as_of,
            self.config,
            self.league_policy,
        )
        self.assertEqual([row["fixture"]["match_id"] for row in outputs], [100])
        self.assertEqual(len(scored), 4)
        self.assertTrue(scales)


if __name__ == "__main__":
    unittest.main()
