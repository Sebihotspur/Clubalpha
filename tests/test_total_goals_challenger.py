import unittest

from clubalpha.total_goals_challenger import (
    fit_probability_grid,
    historical_observations,
    poisson_over_2_5,
    probability_from_grid,
)


CONFIG = {
    "grid": {"minimum_total_xg": 0.5, "maximum_total_xg": 4.0, "step": 0.5}
}


class TotalGoalsChallengerTests(unittest.TestCase):
    def test_poisson_probability_is_monotone(self):
        values = [poisson_over_2_5(value) for value in (1.0, 2.0, 3.0, 4.0)]
        self.assertEqual(values, sorted(values))
        self.assertAlmostEqual(poisson_over_2_5(0.0), 0.0)

    def test_history_keeps_one_home_row_before_cutoff(self):
        rows = [
            {
                "match_id": 1,
                "competition_id": 47,
                "kickoff_utc": "2025-01-01T12:00:00Z",
                "season": "2024/2025",
                "venue": venue,
                "expected_goals_for": 1.5,
                "expected_goals_against": 1.0,
                "goals_for": 2,
                "goals_against": 1,
            }
            for venue in ("home", "away")
        ]
        result = historical_observations(rows, competition_id=47, before="2026-07-01")
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["over_2_5"])

    def test_fitted_grid_is_monotone_and_interpolates(self):
        observations = []
        for index in range(40):
            observations.append(
                {
                    "match_id": index,
                    "kickoff_utc": f"2025-01-{index % 28 + 1:02d}T12:00:00Z",
                    "season": "2024/2025",
                    "total_xg": 1.0 + (index % 8) * 0.4,
                    "over_2_5": index % 8 >= 4,
                }
            )
        grid = fit_probability_grid(
            observations,
            bandwidth=0.5,
            prior_strength=25.0,
            half_life_days=730.0,
            cutoff="2026-07-01",
            config=CONFIG,
        )
        probabilities = [row["over_2_5"] for row in grid]
        self.assertEqual(probabilities, sorted(probabilities))
        middle = probability_from_grid(2.25, grid)
        self.assertGreater(middle, probabilities[0])
        self.assertLess(middle, probabilities[-1])


if __name__ == "__main__":
    unittest.main()
