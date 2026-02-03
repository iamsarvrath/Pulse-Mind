"""Unit tests for the Adaptive Pacing Control Engine."""

import unittest
from pacing_controller import (
    SafetyController, 
    AdaptivePacingPolicy, 
    SafetyState, 
    PacingMode, 
    process_pacing_decision,
    ABSOLUTE_MIN_PACING_RATE,
    ABSOLUTE_MAX_PACING_RATE,
    ABSOLUTE_MAX_PACING_AMPLITUDE
)

class TestSafetyController(unittest.TestCase):
    """Test the SafetyController finite-state machine."""

    def setUp(self):
        self.controller = SafetyController()

    def test_initial_state(self):
        """Test that the controller starts in NORMAL state."""
        self.assertEqual(self.controller.current_state, SafetyState.NORMAL)

    def test_emergency_degradation(self):
        """Test immediate degradation to EMERGENCY on critical HR."""
        # Critical low HR
        state = self.controller.evaluate_state("normal_sinus", 0.9, 70.0, 35.0)
        self.assertEqual(state, SafetyState.EMERGENCY)
        
        self.controller.update_state(state)
        self.assertEqual(self.controller.current_state, SafetyState.EMERGENCY)

    def test_safe_mode_unreliable_data(self):
        """Test transition to SAFE_MODE on low confidence."""
        state = self.controller.evaluate_state("normal_sinus", 0.5, 70.0, 70.0)
        self.assertEqual(state, SafetyState.SAFE_MODE)

    def test_state_improvement_hysteresis(self):
        """Test that improvement requires 3 consecutive cycles."""
        # Force into SAFE_MODE
        self.controller.current_state = SafetyState.SAFE_MODE
        
        # Good data - cycle 1
        state = self.controller.evaluate_state("normal_sinus", 0.9, 80.0, 72.0)
        self.controller.update_state(state)
        self.assertEqual(self.controller.current_state, SafetyState.SAFE_MODE) # Still in SAFE_MODE
        
        # Good data - cycle 2
        self.controller.update_state(state)
        self.assertEqual(self.controller.current_state, SafetyState.SAFE_MODE) # Still in SAFE_MODE
        
        # Good data - cycle 3
        self.controller.update_state(state)
        self.assertEqual(self.controller.current_state, SafetyState.NORMAL) # Finally NORMAL

class TestAdaptivePacingPolicy(unittest.TestCase):
    """Test the AdaptivePacingPolicy decision logic."""

    def setUp(self):
        self.policy = AdaptivePacingPolicy()

    def test_pacing_mode_bradycardia(self):
        """Test mode selection for bradycardia."""
        mode = self.policy.determine_pacing_mode(
            "bradycardia", 0.9, 45.0, "stable", SafetyState.NORMAL
        )
        self.assertEqual(mode, PacingMode.MODERATE)

    def test_pacing_mode_aggressive(self):
        """Test aggressive mode on declining health."""
        mode = self.policy.determine_pacing_mode(
            "bradycardia", 0.9, 40.0, "declining", SafetyState.DEGRADED
        )
        self.assertEqual(mode, PacingMode.AGGRESSIVE)

    def test_target_rate_clamping(self):
        """Test that target rate is always within safe bounds."""
        # Attempt to set a very low rate
        rate = self.policy.compute_target_rate(
            35.0, "bradycardia", 70.0, PacingMode.EMERGENCY
        )
        self.assertGreaterEqual(rate, ABSOLUTE_MIN_PACING_RATE)
        
        # Attempt to set a very high rate
        rate = self.policy.compute_target_rate(
            190.0, "tachycardia", 70.0, PacingMode.MODERATE
        )
        self.assertLessEqual(rate, ABSOLUTE_MAX_PACING_RATE)

    def test_amplitude_safety(self):
        """Test amplitude safety limits."""
        amp = self.policy.compute_pacing_amplitude(PacingMode.EMERGENCY, 20.0)
        self.assertEqual(amp, ABSOLUTE_MAX_PACING_AMPLITUDE)

class TestPacingDecisionEntry(unittest.TestCase):
    """Test the main entry point for pacing decisions."""

    def test_process_pacing_decision_success(self):
        """Test full successful decision flow."""
        rhythm_data = {"rhythm_class": "normal_sinus", "confidence": 0.95}
        hsi_data = {
            "hsi_score": 75.0,
            "trend": {"trend_direction": "stable"},
            "input_features": {"heart_rate_bpm": 72.0}
        }
        
        result = process_pacing_decision(rhythm_data, hsi_data)
        self.assertTrue(result["success"])
        self.assertIn("pacing_command", result)
        self.assertEqual(result["pacing_command"]["pacing_mode"], "monitor_only")

    def test_process_pacing_decision_error_recovery(self):
        """Test that the system returns a safe command on error."""
        # Pass invalid data that would cause a crash if not handled
        result = process_pacing_decision(None, {})
        self.assertFalse(result["success"])
        self.assertEqual(result["pacing_command"]["pacing_mode"], "monitor_only")
        self.assertEqual(result["pacing_command"]["safety_state"], "emergency")

if __name__ == "__main__":
    unittest.main()
