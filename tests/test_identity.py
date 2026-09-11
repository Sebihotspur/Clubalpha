import unittest

from clubalpha.identity import (
    attach_v1_identities,
    build_fotmob_index,
    build_typed_provider_bridge_indexes,
    coverage_summary,
    identity_scope_summary,
    resolve_fotmob_entities,
    v1_coverage_summary,
)


PROVIDERS = {
    "transfermarkt": "key_transfermarkt",
    "fbref": "key_fbref",
}


def resolve(targets, sources):
    return resolve_fotmob_entities(
        targets,
        build_fotmob_index(sources, entity_type="player"),
        entity_type="player",
        target_id="player_id",
        target_name="player",
        provider_fields=PROVIDERS,
        source_release="2026.25",
        source_commit="abc123",
    )


class IdentityResolutionTests(unittest.TestCase):
    def test_exact_provider_id_resolves_and_names_are_only_diagnostic(self):
        rows = resolve(
            [{"player_id": 10, "player": "Jorginho", "date_of_birth": "1991-12-20"}],
            [
                {
                    "type": "player",
                    "key_fotmob": "10",
                    "reep_id": "reep_p1",
                    "name": "Jorge Luiz Frello Filho",
                    "date_of_birth": "1991-12-20",
                    "key_transfermarkt": "123",
                    "key_fbref": "abcd",
                }
            ],
        )
        self.assertEqual(rows[0]["resolution"]["status"], "exact")
        self.assertIn(
            "name_differs_on_exact_provider_id",
            rows[0]["resolution"]["quality_flags"],
        )
        self.assertEqual(rows[0]["bridges"]["transfermarkt"], "123")

    def test_name_only_match_is_never_attempted(self):
        rows = resolve(
            [{"player_id": 99, "player": "Same Name", "date_of_birth": "2000-01-01"}],
            [
                {
                    "type": "player",
                    "key_fotmob": "100",
                    "reep_id": "reep_p2",
                    "name": "Same Name",
                    "date_of_birth": "2000-01-01",
                }
            ],
        )
        self.assertEqual(rows[0]["resolution"]["status"], "unmatched")
        self.assertIsNone(rows[0]["legacy_reep"]["reep_id"])

    def test_duplicate_provider_id_is_quarantined(self):
        sources = [
            {"type": "player", "key_fotmob": "10", "reep_id": "reep_p1", "name": "One"},
            {"type": "player", "key_fotmob": "10", "reep_id": "reep_p2", "name": "Two"},
        ]
        rows = resolve([{"player_id": 10, "player": "One"}], sources)
        self.assertEqual(rows[0]["resolution"]["status"], "ambiguous_provider_id")
        self.assertEqual(rows[0]["resolution"]["candidate_count"], 2)

    def test_date_of_birth_conflict_is_quarantined(self):
        rows = resolve(
            [{"player_id": 10, "player": "Player", "date_of_birth": "2000-01-01"}],
            [
                {
                    "type": "player",
                    "key_fotmob": "10",
                    "reep_id": "reep_p1",
                    "name": "Player",
                    "date_of_birth": "2001-01-01",
                }
            ],
        )
        self.assertEqual(rows[0]["resolution"]["status"], "conflict")
        self.assertIn("date_of_birth_conflict", rows[0]["resolution"]["quality_flags"])

    def test_coverage_counts_only_clean_exact_matches(self):
        rows = resolve(
            [
                {"player_id": 10, "player": "One", "date_of_birth": "2000-01-01"},
                {"player_id": 11, "player": "Two", "date_of_birth": "2000-01-02"},
            ],
            [
                {
                    "type": "player",
                    "key_fotmob": "10",
                    "reep_id": "reep_p1",
                    "name": "One",
                    "date_of_birth": "2000-01-01",
                    "key_transfermarkt": "500",
                }
            ],
        )
        summary = coverage_summary(rows, PROVIDERS)
        self.assertEqual(summary["exact_matches"], 1)
        self.assertEqual(summary["exact_coverage_pct"], 50.0)
        self.assertEqual(summary["provider_coverage_among_exact"]["transfermarkt"]["entities"], 1)


class V1HandoffTests(unittest.TestCase):
    def test_typed_namespace_prevents_cross_entity_collision(self):
        indexes = build_typed_provider_bridge_indexes(
            [
                {
                    "provider": "transfermarkt",
                    "namespace": "spieler",
                    "external_id": "123",
                    "reep_id": "rp1",
                },
                {
                    "provider": "transfermarkt",
                    "namespace": "verein",
                    "external_id": "123",
                    "reep_id": "rt1",
                },
            ],
            provider="transfermarkt",
            namespaces_by_type={"player": {"spieler"}, "team": {"verein"}},
            wanted_by_type={"player": {"123"}, "team": {"123"}},
        )
        self.assertEqual(indexes["player"]["123"][0]["reep_id"], "rp1")
        self.assertEqual(indexes["team"]["123"][0]["reep_id"], "rt1")

    def test_current_identity_resolves_through_redirect(self):
        legacy = resolve(
            [{"player_id": 10, "player": "Player", "date_of_birth": "2000-01-01"}],
            [
                {
                    "type": "player",
                    "key_fotmob": "10",
                    "reep_id": "reep_p1",
                    "name": "Player",
                    "date_of_birth": "2000-01-01",
                    "key_transfermarkt": "123",
                }
            ],
        )
        rows = attach_v1_identities(
            legacy,
            {"player": {"123": [{"namespace": "spieler", "external_id": "123", "reep_id": "rp-old"}]}},
            {"rp-new": {"reep_id": "rp-new", "entity_type": "player", "status": "active", "label": "Player"}},
            {"rp-old": {"to_id": "rp-new", "reason": "merged"}},
            release_stamp="20260820T103440Z",
        )
        self.assertEqual(rows[0]["reep_v1"]["status"], "exact")
        self.assertEqual(rows[0]["reep_v1"]["reep_id"], "rp-new")
        self.assertEqual(v1_coverage_summary(rows)["exact_pct_of_universe"], 100.0)
        self.assertEqual(identity_scope_summary(rows)["current_v1_exact"], 1)


if __name__ == "__main__":
    unittest.main()
