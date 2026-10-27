import unittest

from research.build_ucl_alpha_cycle_v1 import raw_ucl_forecast


class UclAlphaCycleTests(unittest.TestCase):
    def test_raw_forecast_is_explicitly_uncalibrated(self):
        contextual = {
            "fixture": {"match_id": 1},
            "contextual": {
                "predicted_xg": {"home": 1.4, "away": 1.2, "total": 2.6},
                "probabilities": {
                    "home_win": 0.39,
                    "draw": 0.36,
                    "away_win": 0.25,
                    "over": {"2.5": 0.51},
                    "under": {"2.5": 0.49},
                },
            },
        }
        config = {
            "draw": {
                "draw_zone_max_probability_gap": 0.04,
                "draw_zone_max_side_probability": 0.5,
            }
        }
        result = raw_ucl_forecast(contextual, config)
        self.assertTrue(result["calibration_read"]["draw_zone"])
        self.assertFalse(
            result["calibration_read"]["ucl_specific_calibration_applied"]
        )
        self.assertEqual(
            result["probabilities"], contextual["contextual"]["probabilities"]
        )


if __name__ == "__main__":
    unittest.main()
