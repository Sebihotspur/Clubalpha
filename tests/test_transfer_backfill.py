import unittest

from clubalpha.transfer_backfill import (
    backfill_coverage,
    expected_ledger,
    filter_backfill_rows,
    find_gaps,
    held_appearances,
    player_gap_summary,
    season_entries,
    targets_by_competition,
)


def payload(*entries):
    return {"careerHistory": {"careerItems": {"senior": {"seasonEntries": list(entries)}}}}


def entry(team_id, team, season, *tournaments):
    return {
        "seasonName": season,
        "teamId": team_id,
        "team": team,
        "tournamentStats": [
            {
                "leagueId": league_id,
                "leagueName": name,
                "seasonName": season,
                "appearances": str(appearances),
                "isFriendly": friendly,
            }
            for league_id, name, appearances, friendly in tournaments
        ],
    }


# Shape taken from Mamadou Sarr's real 2025/26 record: 7 Chelsea appearances
# across three competitions plus an unresolvable exhibition tie, and 18 at
# Strasbourg that the club-filtered collectors never see.
SARR = payload(
    entry(
        8455,
        "Chelsea",
        "2025/2026",
        (47, "Premier League", 3, False),
        (132, "FA Cup", 2, False),
        (42, "Champions League", 1, False),
        (None, "Sydney Super Cup", 1, False),
    ),
    entry(
        9848,
        "Strasbourg",
        "2025/2026",
        (53, "Ligue 1", 15, False),
        (10216, "Conference League", 3, False),
    ),
    entry(9848, "Strasbourg", "2024/2025", (53, "Ligue 1", 20, False)),
)


class LedgerTests(unittest.TestCase):
    def test_only_the_requested_season_is_read(self):
        self.assertEqual(len(season_entries(SARR, "2025/2026")), 2)
        self.assertEqual(len(season_entries(SARR, "2024/2025")), 1)

    def test_multi_club_season_flattens_to_competition_rows(self):
        ledger = expected_ledger(SARR, "2025/2026")
        self.assertEqual(len(ledger), 6)
        self.assertEqual(sum(row["expected_appearances"] for row in ledger), 25)
        self.assertEqual({row["team"] for row in ledger}, {"Chelsea", "Strasbourg"})

    def test_competition_without_a_league_id_is_kept_but_unresolvable(self):
        """It cannot be collected, so it must be visible rather than silently dropped."""

        ledger = expected_ledger(SARR, "2025/2026")
        exhibition = next(row for row in ledger if row["league"] == "Sydney Super Cup")
        self.assertFalse(exhibition["resolvable"])
        self.assertEqual(exhibition["expected_appearances"], 1)

    def test_friendlies_are_not_resolvable(self):
        data = payload(entry(1, "Club", "2025/2026", (999, "Preseason Cup", 4, True)))
        ledger = expected_ledger(data, "2025/2026")
        self.assertFalse(ledger[0]["resolvable"])

    def test_zero_appearance_competitions_are_skipped(self):
        data = payload(entry(1, "Club", "2025/2026", (47, "Premier League", 0, False)))
        self.assertEqual(expected_ledger(data, "2025/2026"), [])


class GapTests(unittest.TestCase):
    def _held(self):
        return held_appearances(
            [
                {"team_id": 8455, "competition_id": 47, "match_id": 1},
                {"team_id": 8455, "competition_id": 47, "match_id": 2},
                {"team_id": 8455, "competition_id": 47, "match_id": 3},
                {"team_id": 8455, "competition_id": 42, "match_id": 99},
            ]
        )

    def test_status_reflects_how_much_is_actually_held(self):
        gaps = {
            (row["team"], row["league"]): row
            for row in find_gaps(expected_ledger(SARR, "2025/2026"), self._held())
        }
        self.assertEqual(gaps[("Chelsea", "Premier League")]["status"], "complete")
        self.assertEqual(gaps[("Chelsea", "Champions League")]["status"], "complete")
        self.assertEqual(gaps[("Chelsea", "FA Cup")]["status"], "absent")
        self.assertEqual(gaps[("Strasbourg", "Ligue 1")]["status"], "absent")
        self.assertEqual(gaps[("Strasbourg", "Ligue 1")]["missing_appearances"], 15)

    def test_partial_is_distinguished_from_absent(self):
        held = held_appearances([{"team_id": 9848, "competition_id": 53, "match_id": 5}])
        gaps = find_gaps(expected_ledger(SARR, "2025/2026"), held)
        ligue1 = next(row for row in gaps if row["league"] == "Ligue 1")
        self.assertEqual(ligue1["status"], "partial")
        self.assertEqual(ligue1["missing_appearances"], 14)

    def test_holding_more_than_the_ledger_is_not_a_negative_gap(self):
        """Match detail is more trustworthy than the season leaderboard."""

        held = held_appearances(
            [{"team_id": 8455, "competition_id": 47, "match_id": index} for index in range(10)]
        )
        gaps = find_gaps(expected_ledger(SARR, "2025/2026"), held)
        pl = next(row for row in gaps if row["league"] == "Premier League")
        self.assertEqual(pl["status"], "complete")
        self.assertEqual(pl["missing_appearances"], 0)

    def test_summary_reports_the_real_shortfall(self):
        gaps = find_gaps(expected_ledger(SARR, "2025/2026"), self._held())
        summary = player_gap_summary(1426170, "Mamadou Sarr", 8455, gaps)
        self.assertTrue(summary["multi_club_season"])
        self.assertEqual(summary["clubs_in_season"], 2)
        self.assertEqual(summary["expected_appearances"], 25)
        self.assertEqual(summary["held_appearances"], 4)
        self.assertEqual(summary["missing_appearances"], 21)
        self.assertEqual(summary["coverage_pct"], 16.0)
        self.assertEqual(len(summary["collectable_gaps"]), 3)
        self.assertEqual(len(summary["unresolvable_gaps"]), 1)


class BatchingTests(unittest.TestCase):
    def test_gaps_group_into_one_fetch_per_competition_season(self):
        gaps = find_gaps(expected_ledger(SARR, "2025/2026"), held_appearances([]))
        summary = player_gap_summary(1426170, "Mamadou Sarr", 8455, gaps)
        batches = targets_by_competition([summary])
        self.assertIn((53, "2025/2026"), batches)
        self.assertEqual(batches[(53, "2025/2026")]["team_ids"], {9848})
        self.assertNotIn(None, {key[0] for key in batches})

    def test_players_sharing_a_club_season_share_one_batch(self):
        other = payload(
            entry(9848, "Strasbourg", "2025/2026", (53, "Ligue 1", 3, False))
        )
        summaries = [
            player_gap_summary(
                1,
                "Sarr",
                8455,
                find_gaps(expected_ledger(SARR, "2025/2026"), held_appearances([])),
            ),
            player_gap_summary(
                2,
                "Anselmino",
                8455,
                find_gaps(expected_ledger(other, "2025/2026"), held_appearances([])),
            ),
        ]
        batches = targets_by_competition(summaries)
        self.assertEqual(batches[(53, "2025/2026")]["player_ids"], {1, 2})
        self.assertEqual(batches[(53, "2025/2026")]["team_ids"], {9848})


class RowFilterTests(unittest.TestCase):
    COMPETITION = {"league_id": 53, "league": "Ligue 1", "season": "2025/2026"}

    def test_only_backfilled_players_are_retained(self):
        """Opponents must never enter the population on a one-match sample."""

        rows = [
            {"match_id": 1, "player_id": 1426170, "team_id": 9848, "metrics": {}},
            {"match_id": 1, "player_id": 999999, "team_id": 9848, "metrics": {}},
            {"match_id": 1, "player_id": 888888, "team_id": 5000, "metrics": {}},
        ]
        kept = filter_backfill_rows(rows, {1426170}, self.COMPETITION, set())
        self.assertEqual([row["player_id"] for row in kept], [1426170])
        self.assertEqual(kept[0]["source_scope"], "transfer_backfill")
        self.assertEqual(kept[0]["competition_id"], 53)

    def test_rows_already_held_are_not_duplicated(self):
        rows = [
            {"match_id": 1, "player_id": 1426170, "team_id": 9848, "metrics": {}},
            {"match_id": 2, "player_id": 1426170, "team_id": 9848, "metrics": {}},
        ]
        kept = filter_backfill_rows(rows, {1426170}, self.COMPETITION, {(1, 1426170)})
        self.assertEqual([row["match_id"] for row in kept], [2])


class CoverageTests(unittest.TestCase):
    def test_coverage_counts_what_the_backfill_actually_closed(self):
        gaps = find_gaps(expected_ledger(SARR, "2025/2026"), held_appearances([]))
        summary = player_gap_summary(1426170, "Mamadou Sarr", 8455, gaps)
        collected = [
            {"match_id": index, "player_id": 1426170} for index in range(15)
        ]
        coverage = backfill_coverage([summary], collected)
        self.assertEqual(coverage["players_examined"], 1)
        self.assertEqual(coverage["multi_club_players"], 1)
        self.assertEqual(coverage["rows_collected"], 15)
        self.assertEqual(coverage["players_backfilled"], 1)
        # 25 expected, none held, 15 collected: still short, and it must say so.
        self.assertEqual(coverage["players_still_incomplete"], 1)
        self.assertEqual(coverage["unresolvable_gap_players"], 1)


if __name__ == "__main__":
    unittest.main()
