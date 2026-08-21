import unittest

from clubalpha.club_form_snapshot import join_club_form_snapshots


def form(team_id=10, team="Club", as_of="2026-08-18"):
    return {
        "form_version": "form-v1",
        "as_of": as_of,
        "team_id": team_id,
        "team": team,
        "premier_league_2026_27": True,
        "ucl_status": None,
        "overall_form_z": 0.4,
        "attack_z": 0.6,
        "defense_z": 0.2,
        "attack_confidence": 0.8,
        "defense_confidence": 0.6,
        "evidence": {"matches": 10},
        "breakdown": {"preseason": {"matches": 3}},
        "availability": {
            "unavailable": 1,
            "questionable": 2,
            "form_score_modifier": None,
        },
        "quality_flags": [],
    }


def dynamics(team_id=10, team="Club", as_of="2026-08-18"):
    return {
        "dynamics_version": "dynamics-v1",
        "as_of": as_of,
        "team_id": team_id,
        "team": team,
        "style": {"coverage": 1.0, "composite_score": None},
        "strengths_weaknesses": {"coverage": 1.0, "composite_score": None},
        "change_state": {"score_modifier": None},
        "quality_flags": ["first_squad_snapshot"],
    }


class ClubFormSnapshotTests(unittest.TestCase):
    def test_join_preserves_components_without_creating_a_score(self):
        row = join_club_form_snapshots([form()], [dynamics()])[0]
        self.assertEqual(row["performance_form"]["overall_form_z"], 0.4)
        self.assertEqual(row["performance_form"]["confidence"]["average"], 0.7)
        self.assertIsNone(row["club_dynamics"]["style"]["composite_score"])
        self.assertIsNone(row["decision_boundaries"]["combined_club_form_score"])
        self.assertFalse(row["decision_boundaries"]["dynamics_changes_performance_score"])
        self.assertFalse(row["decision_boundaries"]["availability_changes_performance_score"])
        self.assertFalse(row["decision_boundaries"]["projection_ready"])

    def test_component_universes_must_match(self):
        with self.assertRaisesRegex(ValueError, "component universes differ"):
            join_club_form_snapshots([form()], [])

    def test_component_dates_must_match(self):
        with self.assertRaisesRegex(ValueError, "Snapshot date mismatch"):
            join_club_form_snapshots([form()], [dynamics(as_of="2026-08-19")])

    def test_duplicate_component_rows_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate performance form"):
            join_club_form_snapshots([form(), form()], [dynamics()])


if __name__ == "__main__":
    unittest.main()
