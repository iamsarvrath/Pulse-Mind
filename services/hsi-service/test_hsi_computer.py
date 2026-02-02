"""
Unit tests for HSI (Hemodynamic Surrogate Index) computation module.

Tests normalization functions, HSI computation, trend analysis, and stateless behavior.
"""

import unittest
from datetime import datetime, timedelta
from hsi_computer import (
    normalize_heart_rate,
    normalize_hrv,
    normalize_pulse_amplitude,
    compute_hsi,
    interpret_hsi,
    compute_trend,
    process_hsi_computation,
    HR_OPTIMAL,
    HRV_MIN,
    HRV_MAX,
    PULSE_AMP_MIN,
    PULSE_AMP_MAX,
)


class TestNormalizationFunctions(unittest.TestCase):
    """Test normalization functions for individual features."""

    def test_normalize_hr_optimal(self):
        """Test HR normalization at optimal value."""
        score = normalize_heart_rate(HR_OPTIMAL)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_normalize_hr_below_optimal(self):
        """Test HR normalization below optimal."""
        score = normalize_heart_rate(60.0)
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

    def test_normalize_hr_above_optimal(self):
        """Test HR normalization above optimal."""
        score = normalize_heart_rate(90.0)
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

    def test_normalize_hr_extreme_low(self):
        """Test HR normalization at extreme low value."""
        score = normalize_heart_rate(40.0)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 0.5)

    def test_normalize_hr_extreme_high(self):
        """Test HR normalization at extreme high value."""
        score = normalize_heart_rate(120.0)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 0.5)

    def test_normalize_hrv_min(self):
        """Test HRV normalization at minimum."""
        score = normalize_hrv(HRV_MIN)
        self.assertAlmostEqual(score, 0.0, places=4)

    def test_normalize_hrv_max(self):
        """Test HRV normalization at maximum."""
        score = normalize_hrv(HRV_MAX)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_normalize_hrv_mid(self):
        """Test HRV normalization at mid-range."""
        score = normalize_hrv(50.0)
        self.assertGreater(score, 0.3)
        self.assertLess(score, 0.7)

    def test_normalize_pulse_min(self):
        """Test pulse amplitude normalization at minimum."""
        score = normalize_pulse_amplitude(PULSE_AMP_MIN)
        self.assertAlmostEqual(score, 0.0, places=4)

    def test_normalize_pulse_max(self):
        """Test pulse amplitude normalization at maximum."""
        score = normalize_pulse_amplitude(PULSE_AMP_MAX)
        self.assertAlmostEqual(score, 1.0, places=4)

    def test_normalize_pulse_mid(self):
        """Test pulse amplitude normalization at mid-range."""
        score = normalize_pulse_amplitude(25.0)
        self.assertGreater(score, 0.3)
        self.assertLess(score, 0.7)


class TestHSIComputation(unittest.TestCase):
    """Test HSI computation and interpretation."""

    def test_compute_hsi_optimal_values(self):
        """Test HSI computation with optimal values."""
        result = compute_hsi(
            heart_rate_bpm=70.0, hrv_sdnn_ms=50.0, pulse_amplitude=25.0
        )

        # Check all expected fields are present
        self.assertIn("hsi_score", result)
        self.assertIn("hr_contribution", result)
        self.assertIn("hrv_contribution", result)
        self.assertIn("pulse_contribution", result)

        # HSI should be high for optimal values
        self.assertGreater(result["hsi_score"], 60.0)
        self.assertLessEqual(result["hsi_score"], 100.0)

    def test_compute_hsi_poor_values(self):
        """Test HSI computation with poor values."""
        result = compute_hsi(
            heart_rate_bpm=110.0,  # High HR
            hrv_sdnn_ms=15.0,  # Low HRV
            pulse_amplitude=8.0,  # Low pulse
        )

        # HSI should be low for poor values
        self.assertLess(result["hsi_score"], 50.0)
        self.assertGreaterEqual(result["hsi_score"], 0.0)

    def test_compute_hsi_contributions_sum(self):
        """Test that HSI contributions sum correctly."""
        result = compute_hsi(
            heart_rate_bpm=72.0, hrv_sdnn_ms=45.0, pulse_amplitude=20.0
        )

        total_contribution = (
            result["hr_contribution"]
            + result["hrv_contribution"]
            + result["pulse_contribution"]
        )

        # Should sum to HSI score / 100
        expected = result["hsi_score"] / 100.0
        self.assertAlmostEqual(total_contribution, expected, places=3)

    def test_interpret_hsi_excellent(self):
        """Test HSI interpretation for excellent score."""
        interpretation = interpret_hsi(85.0)
        self.assertEqual(interpretation, "excellent")

    def test_interpret_hsi_good(self):
        """Test HSI interpretation for good score."""
        interpretation = interpret_hsi(65.0)
        self.assertEqual(interpretation, "good")

    def test_interpret_hsi_fair(self):
        """Test HSI interpretation for fair score."""
        interpretation = interpret_hsi(45.0)
        self.assertEqual(interpretation, "fair")

    def test_interpret_hsi_poor(self):
        """Test HSI interpretation for poor score."""
        interpretation = interpret_hsi(25.0)
        self.assertEqual(interpretation, "poor")

    def test_interpret_hsi_very_poor(self):
        """Test HSI interpretation for very poor score."""
        interpretation = interpret_hsi(10.0)
        self.assertEqual(interpretation, "very_poor")


class TestTrendCalculation(unittest.TestCase):
    """Test trend calculation functionality."""

    def test_trend_no_previous(self):
        """Test trend calculation with no previous measurement."""
        current = {"hsi_score": 65.0, "timestamp": datetime.utcnow().isoformat() + "Z"}

        trend = compute_trend(current, None)

        self.assertEqual(trend["delta_hsi"], 0.0)
        self.assertEqual(trend["delta_per_minute"], 0.0)
        self.assertEqual(trend["trend_direction"], "stable")
        self.assertFalse(trend["is_significant"])

    def test_trend_improving(self):
        """Test trend calculation with improving HSI."""
        previous = {
            "hsi_score": 60.0,
            "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z",
        }
        current = {"hsi_score": 70.0, "timestamp": datetime.utcnow().isoformat() + "Z"}

        trend = compute_trend(current, previous)

        self.assertGreater(trend["delta_hsi"], 0)
        self.assertEqual(trend["trend_direction"], "improving")
        self.assertTrue(trend["is_significant"])

    def test_trend_declining(self):
        """Test trend calculation with declining HSI."""
        previous = {
            "hsi_score": 70.0,
            "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z",
        }
        current = {"hsi_score": 60.0, "timestamp": datetime.utcnow().isoformat() + "Z"}

        trend = compute_trend(current, previous)

        self.assertLess(trend["delta_hsi"], 0)
        self.assertEqual(trend["trend_direction"], "declining")
        self.assertTrue(trend["is_significant"])

    def test_trend_stable(self):
        """Test trend calculation with stable HSI."""
        previous = {
            "hsi_score": 65.0,
            "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z",
        }
        current = {
            "hsi_score": 67.0,  # Change < 5 points
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        trend = compute_trend(current, previous)

        self.assertEqual(trend["trend_direction"], "stable")
        self.assertFalse(trend["is_significant"])

    def test_trend_rate_calculation(self):
        """Test trend rate calculation per minute."""
        previous = {
            "hsi_score": 60.0,
            "timestamp": (datetime.utcnow() - timedelta(minutes=10)).isoformat() + "Z",
        }
        current = {"hsi_score": 70.0, "timestamp": datetime.utcnow().isoformat() + "Z"}

        trend = compute_trend(current, previous)

        # Delta is 10 points over 10 minutes = 1 point/minute
        self.assertAlmostEqual(trend["delta_per_minute"], 1.0, places=1)


class TestProcessHSIComputation(unittest.TestCase):
    """Test main HSI processing function."""

    def test_process_valid_features(self):
        """Test processing with valid features."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 20.0,
        }

        result = process_hsi_computation(features)

        self.assertTrue(result["success"])
        self.assertIn("hsi", result)
        self.assertIn("interpretation", result)
        self.assertIn("trend", result)
        self.assertIn("timestamp", result)
        self.assertIn("input_features", result)

    def test_process_with_previous_measurement(self):
        """Test processing with previous measurement for trend."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 20.0,
        }
        previous = {
            "hsi_score": 60.0,
            "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat() + "Z",
        }

        result = process_hsi_computation(features, previous)

        self.assertTrue(result["success"])
        self.assertNotEqual(result["trend"]["delta_hsi"], 0.0)

    def test_process_missing_feature(self):
        """Test processing with missing required feature."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            # Missing pulse_amplitude
        }

        with self.assertRaises(ValueError) as context:
            process_hsi_computation(features)

        self.assertIn("pulse_amplitude", str(context.exception))

    def test_process_invalid_hr(self):
        """Test processing with invalid heart rate."""
        features = {
            "heart_rate_bpm": -10.0,  # Invalid
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 20.0,
        }

        with self.assertRaises(ValueError) as context:
            process_hsi_computation(features)

        self.assertIn("Heart rate", str(context.exception))

    def test_process_invalid_hrv(self):
        """Test processing with invalid HRV."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": -5.0,  # Invalid
            "pulse_amplitude": 20.0,
        }

        with self.assertRaises(ValueError) as context:
            process_hsi_computation(features)

        self.assertIn("HRV", str(context.exception))

    def test_process_invalid_pulse(self):
        """Test processing with invalid pulse amplitude."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": -10.0,  # Invalid
        }

        with self.assertRaises(ValueError) as context:
            process_hsi_computation(features)

        self.assertIn("Pulse amplitude", str(context.exception))

    def test_process_non_numeric_feature(self):
        """Test processing with non-numeric feature."""
        features = {
            "heart_rate_bpm": "seventy-two",  # Invalid
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 20.0,
        }

        with self.assertRaises(ValueError) as context:
            process_hsi_computation(features)

        self.assertIn("Invalid feature value", str(context.exception))

    def test_stateless_behavior(self):
        """Test that function is truly stateless."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 20.0,
        }

        # Call twice with same inputs
        result1 = process_hsi_computation(features)
        result2 = process_hsi_computation(features)

        # Results should be identical (except timestamp if not provided)
        self.assertEqual(result1["hsi"]["hsi_score"], result2["hsi"]["hsi_score"])
        self.assertEqual(result1["interpretation"], result2["interpretation"])

    def test_custom_timestamp(self):
        """Test processing with custom timestamp."""
        features = {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 20.0,
        }
        custom_timestamp = "2026-01-01T12:00:00.000000Z"

        result = process_hsi_computation(features, timestamp=custom_timestamp)

        self.assertEqual(result["timestamp"], custom_timestamp)


if __name__ == "__main__":
    unittest.main()
