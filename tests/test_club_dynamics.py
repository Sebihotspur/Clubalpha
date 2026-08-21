import json
import unittest
from datetime import date
from pathlib import Path

from clubalpha.club_dynamics import (
    build_change_state,
    build_club_dynamics,
    build_strength_profile,
    derive_dynamic_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/club-dynamics-v1.json").read_text(encoding="utf-8"))


class DynamicMetricTests(unittest.TestCase):
    def test_style_and_strength_metrics_are_separate(self):
        row = derive_dynamic_metrics(
            {
                "possession_pct_for": 60,
                "own_half_passes_for": 200,
                "opposition_half_passes_for": 300,
                "long_balls_attempted_est_for": 50,
                "crosses_attempted_est_for": 30,
                "passes_for": 600,
                "expected_goals_for": 2.0,
                "expected_goals_against": 0.8,
                "expected_goals_set_play_for": 0.5,
                "expected_goals_set_play_against": 0.1,
                "total_shots_for": 10,
                "total_shots_against": 8,
                "goals_for": 3,
                "touches_opp_box_for": 30,
                "touches_opp_box_against": 12,
            }
        )
        self.assertEqual(row["style_raw"]["territory"], 60)
        self.assertAlmostEqual(row["style_raw"]["directness"], 8.3333, places=3)
        self.assertEqual(row["style_raw"]["set_piece_reliance"], 25)
        self.assertEqual(row["strength_raw"]["shot_quality"], 0.2)
        self.assertEqual(row["strength_raw"]["finishing"], 1.0)

    def test_strength_signal_remains_visible_while_confidence_shrinks_z(self):
        rows = [
            {
                "kickoff_utc": f"2026-08-{day:02d}T15:00:00Z",
                "source_scope": "premier_league_previous",
                "strength_z": {item["key"]: (1.0 if item["key"] == "chance_creation" else None) for item in CONFIG["strengths"]["axes"]},
            }
            for day in range(13, 18)
        ]
        profile = build_strength_profile(rows, date(2026, 8, 18), CONFIG)
        chance_creation = profile["axes"]["chance_creation"]
        self.assertEqual(chance_creation["raw_z"], 1.0)
        self.assertLess(chance_creation["z"], 0.6)
        self.assertEqual(chance_creation["classification"], "strength")
        self.assertIsNone(profile["composite_score"])

    def test_as_of_filter_excludes_future_match_from_scales_and_profiles(self):
        profiles, scored, _ = build_club_dynamics(
            [
                {
                    "match_id": 99,
                    "team_id": 10,
                    "kickoff_utc": "2026-08-20T15:00:00Z",
                    "source_scope": "premier_league_current",
                }
            ],
            [{"team_id": 10, "name": "Club"}],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            date(2026, 8, 18),
            CONFIG,
        )
        self.assertEqual(scored, [])
        self.assertEqual(profiles[0]["style"]["coverage"], 0.0)


class ChangeStateTests(unittest.TestCase):
    def test_manager_and_transfer_changes_describe_uncertainty_without_modifier(self):
        team = {"team_id": 10, "name": "Club"}
        snapshot = {
            "team_id": 10,
            "snapshot_date": "2026-08-18",
            "current_coach": {"coach_id": 2, "coach": "New Coach"},
            "squad_player_ids": [9],
        }
        history = [
            {"team_id": 10, "coach_id": 1, "coach": "Old Coach", "season": "2025/2026", "wins": 10, "draws": 5, "losses": 5}
        ]
        transfers = [
            {
                "team_id": 10,
                "direction": "in",
                "player_id": 9,
                "player": "Forward",
                "effective_date": "2026-07-01",
                "reported_at_utc": "2026-06-20T10:00:00Z",
                "fee_eur": 100000000,
            },
            {
                "team_id": 10,
                "direction": "in",
                "player_id": 9,
                "player": "Forward",
                "effective_date": "2026-07-01",
                "reported_at_utc": "2026-06-10T10:00:00Z",
                "counterparty": "Superseded report",
            },
            {
                "team_id": 10,
                "direction": "in",
                "player_id": 11,
                "player": "Future",
                "effective_date": "2026-08-01",
                "reported_at_utc": "2026-08-20T10:00:00Z",
            },
        ]
        team_matches = [
            {"team_id": 10, "match_id": 1, "source_scope": "preseason_2026", "kickoff_utc": "2026-08-10T15:00:00Z"}
        ]
        player_matches = [
            {"team_id": 10, "match_id": 1, "player_id": 9, "metrics": {"minutes_played": {"value": 45}}}
        ]
        change = build_change_state(
            team,
            snapshot,
            {"team_id": 10, "snapshot_date": "2026-08-01", "squad_player_ids": [9, 10]},
            history,
            transfers,
            {9: {"alpha_ability_z": 1.5, "scoring_position": "FW"}},
            player_matches,
            team_matches,
            date(2026, 8, 18),
            CONFIG,
        )
        self.assertTrue(change["manager"]["changed_since_previous_season"])
        self.assertEqual(change["manager"]["state"], "early_transition")
        self.assertEqual(change["manager"]["stability_confidence"], 0.1429)
        self.assertEqual(change["transfers"]["incoming"], 1)
        self.assertNotEqual(
            change["transfers"]["events"][0].get("counterparty"),
            "Superseded report",
        )
        self.assertEqual(change["transfers"]["incoming_integration_confidence"], 0.5)
        self.assertEqual(change["transfers"]["incoming_integration_coverage"], 1.0)
        self.assertEqual(change["transfers"]["events"][0]["impact_state"], "partially_integrated")
        self.assertFalse(change["transfers"]["fee_and_market_value_used_in_model"])
        self.assertEqual(change["squad_continuity"]["retained_share"], 0.5)
        self.assertEqual(change["squad_continuity"]["removed_since_snapshot"], 1)
        self.assertIsNone(change["score_modifier"])

    def test_unknown_transfer_quality_remains_missing_not_zero(self):
        change = build_change_state(
            {"team_id": 10, "name": "Club"},
            None,
            None,
            [],
            [
                {
                    "team_id": 10,
                    "direction": "in",
                    "player_id": 9,
                    "effective_date": "2026-07-01",
                    "reported_at_utc": "2026-06-20T10:00:00Z",
                }
            ],
            {},
            [],
            [],
            date(2026, 8, 18),
            CONFIG,
        )
        self.assertEqual(change["transfers"]["alpha_coverage"], 0.0)
        self.assertIsNone(change["transfers"]["incoming_alpha_z_sum"])
        self.assertIsNone(change["transfers"]["net_known_alpha_z"])
        self.assertIsNone(change["transfers"]["minutes_weighted_known_incoming_alpha_z"])


if __name__ == "__main__":
    unittest.main()
