import unittest

from clubalpha.archetype_memory import build_archetype_memory, evidence_tier


def card(match_id=1, score="2-1", home_xg=1.7, away_xg=0.9):
    return {
        "match_id": match_id,
        "kickoff_utc": "2026-09-01T15:00:00Z",
        "observed": {
            "score": score,
            "actual_xg": {"home": home_xg, "away": away_xg},
        },
        "pre_match_fingerprint": {
            "contextual_predicted_xg": {"home": 1.4, "away": 1.1},
            "directional_context": {
                "home_attack": {
                    "attacker_archetype": "Controller",
                    "defender_archetype": "Transition",
                    "preferred_route": {
                        "key": "box_pressure",
                        "verdict": "strong_route",
                        "challenger_signal_z": 0.4,
                    },
                },
                "away_attack": {
                    "attacker_archetype": "Transition",
                    "defender_archetype": "Controller",
                    "preferred_route": {
                        "key": "direct_transition",
                        "verdict": "leans_favorable",
                        "challenger_signal_z": 0.2,
                    },
                },
            },
        },
        "team_memory_signals": [
            {
                "venue": "home",
                "team_id": 10,
                "team": "Home",
                "opponent": "Away",
                "process_learning_weight": 0.8,
                "xi_hit_rate": 0.9,
            },
            {
                "venue": "away",
                "team_id": 20,
                "team": "Away",
                "opponent": "Home",
                "process_learning_weight": 0.8,
                "xi_hit_rate": 0.8,
            },
        ],
    }


class ArchetypeMemoryTests(unittest.TestCase):
    def test_evidence_tiers(self):
        self.assertEqual(evidence_tier(2), "descriptive")
        self.assertEqual(evidence_tier(3), "tentative")
        self.assertEqual(evidence_tier(5), "challenger_eligible")
        self.assertEqual(evidence_tier(8), "human_promotion_review")

    def test_builds_team_and_league_ledgers(self):
        memory = build_archetype_memory([card()], as_of="2026-10-06")
        self.assertEqual(len(memory["observations"]), 2)
        home = next(
            row for row in memory["team_vs_opponent_archetype"] if row["team"] == "Home"
        )
        self.assertEqual(home["opponent_archetype"], "Transition")
        self.assertEqual(home["record"], {"wins": 1, "draws": 0, "losses": 0})
        self.assertEqual(home["weighted_process"]["xg_difference"], 0.8)
        self.assertEqual(memory["decision_boundaries"]["automatic_probability_weight"], 0)


if __name__ == "__main__":
    unittest.main()

