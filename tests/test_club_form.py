import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from clubalpha.club_form import (
    aggregate_form,
    build_club_forms,
    build_match_observations,
    classify_availability,
    dedupe_fixtures,
    score_match_observations,
)
from clubalpha.fotmob import flatten_match_team_stats


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/club-form-v1.json").read_text(encoding="utf-8"))


def fixture(match_id=1, kickoff="2026-08-10T15:00:00Z", score="2 - 1"):
    return {
        "match_id": match_id,
        "source_scope": "premier_league_previous",
        "competition_id": 47,
        "competition": "Premier League",
        "kickoff_utc": kickoff,
        "home_team_id": 10,
        "home_team": "Home",
        "away_team_id": 20,
        "away_team": "Away",
        "score": score,
        "finished": True,
    }


def payload():
    return {
        "header": {"teams": [{"score": 2}, {"score": 1}]},
        "content": {
            "stats": {
                "Periods": {
                    "All": {
                        "stats": [
                            {
                                "stats": [
                                    {"key": "expected_goals", "stats": ["1.75", "0.60"]},
                                    {"key": "ShotsOnTarget", "stats": [5, 2]},
                                    {"key": "big_chance", "stats": ["3", "1"]},
                                    {"key": "total_shots", "stats": [12, 7]},
                                    {"key": "touches_opp_box", "stats": ["22", "10"]},
                                ]
                            }
                        ]
                    }
                }
            }
        },
    }


class TeamMatchNormalizationTests(unittest.TestCase):
    def test_flattens_both_sides_without_losing_against_values(self):
        rows = flatten_match_team_stats(payload(), fixture())
        self.assertEqual(len(rows), 2)
        home, away = rows
        self.assertEqual(home["goals_for"], 2)
        self.assertEqual(home["expected_goals_for"], 1.75)
        self.assertEqual(home["shots_on_target_against"], 2)
        self.assertEqual(away["expected_goals_for"], 0.6)
        self.assertEqual(away["big_chances_against"], 3)

    def test_score_only_match_keeps_missing_metrics_missing(self):
        rows = flatten_match_team_stats({}, fixture(score="4 - 0"))
        self.assertEqual(rows[0]["goals_for"], 4)
        self.assertIsNone(rows[0]["expected_goals_for"])
        self.assertIsNone(rows[0]["shots_on_target_for"])
        self.assertEqual(rows[0]["detailed_metric_count"], 0)

    def test_duplicate_fixture_prefers_first_normalized_source(self):
        first = fixture()
        second = {**fixture(), "source_scope": "duplicate"}
        result = dedupe_fixtures([first], [second])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_scope"], "premier_league_previous")

    def test_as_of_filter_blocks_future_information(self):
        past = fixture(match_id=1, kickoff="2026-08-10T15:00:00Z")
        future = fixture(match_id=2, kickoff="2026-08-20T15:00:00Z")
        with tempfile.TemporaryDirectory() as temp:
            rows, missing = build_match_observations(
                [past, future], Path(temp), date(2026, 8, 18)
            )
        self.assertEqual({row["match_id"] for row in rows}, {1})
        self.assertEqual(missing, [1])


class FormScoringTests(unittest.TestCase):
    def test_opponent_baseline_excludes_the_same_match(self):
        config = copy.deepcopy(CONFIG)
        config["normalisation"]["minimum_peer_team_rows"] = 2
        fixtures = []
        for match_id, score in ((1, "4 - 0"), (2, "0 - 1")):
            current = fixture(match_id=match_id, score=score)
            if match_id == 2:
                current.update(
                    {
                        "home_team_id": 10,
                        "home_team": "Home",
                        "away_team_id": 30,
                        "away_team": "Third",
                    }
                )
            fixtures.extend(flatten_match_team_stats({}, current))
        scored, _ = score_match_observations(fixtures, date(2026, 8, 18), config)
        first_home = next(
            row for row in scored if row["match_id"] == 1 and row["team_id"] == 10
        )
        self.assertEqual(first_home["opponent_baseline_matches"]["defense"], 0)
        self.assertEqual(first_home["opponent_defense_baseline_z"], 0.0)

    def test_preseason_cannot_exceed_twenty_percent_of_weight(self):
        competitive = {
            "match_id": 1,
            "kickoff_utc": "2026-08-01T00:00:00Z",
            "source_scope": "premier_league_previous",
            "base_match_weight": 1.0,
            "attack_metric_coverage": 1.0,
            "defense_metric_coverage": 1.0,
            "attack_match_z_adjusted": 0.0,
            "defense_match_z_adjusted": 0.0,
        }
        preseason = [
            {
                **competitive,
                "match_id": index + 2,
                "source_scope": "preseason_2026",
                "base_match_weight": 0.25,
                "attack_match_z_adjusted": 3.0,
                "defense_match_z_adjusted": 3.0,
            }
            for index in range(8)
        ]
        result = aggregate_form([competitive, *preseason], CONFIG)
        self.assertTrue(result["preseason_weight_capped"])
        self.assertAlmostEqual(result["preseason_weight_share"], 0.2, places=4)
        self.assertAlmostEqual(result["attack_z_raw"], 0.6, places=4)

    def test_missing_detail_reduces_evidence_not_the_score_to_zero(self):
        row = {
            "match_id": 1,
            "kickoff_utc": "2026-08-01T00:00:00Z",
            "source_scope": "premier_league_previous",
            "base_match_weight": 1.0,
            "attack_metric_coverage": 0.25,
            "defense_metric_coverage": 0.25,
            "attack_match_z_adjusted": 1.0,
            "defense_match_z_adjusted": -1.0,
        }
        result = aggregate_form([row], CONFIG)
        self.assertEqual(result["attack_z_raw"], 1.0)
        self.assertEqual(result["weighted_match_evidence"], 0.25)
        self.assertLess(result["attack_confidence"], 0.05)


class AvailabilityTests(unittest.TestCase):
    def test_conservative_injury_classification(self):
        self.assertEqual(
            classify_availability({"expectedReturn": "Doubtful"}, CONFIG),
            "questionable",
        )
        self.assertEqual(
            classify_availability({"expectedReturn": "Late October 2026"}, CONFIG),
            "unavailable",
        )
        self.assertIsNone(classify_availability(None, CONFIG))

    def test_availability_never_changes_club_form_score(self):
        forms, _ = build_club_forms(
            [],
            [{"team_id": 10, "name": "Home"}],
            [
                {
                    "team_id": 10,
                    "player_id": 100,
                    "player": "Star",
                    "position": "ST",
                    "injury": {"expectedReturn": "Late October 2026"},
                }
            ],
            [
                {
                    "player_id": 100,
                    "alpha_ability_z": 2.0,
                    "scoring_position": "FW",
                }
            ],
            date(2026, 8, 18),
            CONFIG,
        )
        self.assertIsNone(forms[0]["overall_form_z"])
        self.assertEqual(forms[0]["availability"]["unavailable"], 1)
        self.assertIsNone(forms[0]["availability"]["form_score_modifier"])


if __name__ == "__main__":
    unittest.main()
