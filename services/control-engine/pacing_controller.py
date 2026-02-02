"""
Adaptive Pacing Control Engine

This module implements a medical-grade control system for cardiac pacing decisions.
It uses a finite-state safety controller with deterministic adaptive pacing policy.

MEDICAL SAFETY CRITICAL: This module makes decisions that could affect patient safety.
All logic is deterministic, well-documented, and includes multiple safety layers.

Design Principles:
1. Safety First - Multiple layers of safety constraints
2. Deterministic - No randomness, same input = same output
3. Fail-Safe - Graceful degradation to safe fallback modes
4. Transparent - All decisions clearly logged and explainable
5. Robust - Never crashes, handles all invalid inputs gracefully
"""

import sys
import os
from typing import Dict, Optional, Tuple
from enum import Enum
from datetime import datetime

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logger import setup_logger

logger = setup_logger("pacing-controller", level="INFO")


# ============================================================================
# SAFETY CONSTANTS AND LIMITS
# ============================================================================

# Absolute safety limits - NEVER exceed these
# Rationale: Based on medical device standards and physiological limits
ABSOLUTE_MIN_PACING_RATE = 40  # BPM - Below this is dangerous bradycardia
ABSOLUTE_MAX_PACING_RATE = 180  # BPM - Above this risks tachycardia
ABSOLUTE_MIN_PACING_AMPLITUDE = 0.5  # mA - Minimum to ensure capture
ABSOLUTE_MAX_PACING_AMPLITUDE = 10.0  # mA - Maximum safe amplitude

# Normal operating ranges - preferred bounds
NORMAL_MIN_PACING_RATE = 60  # BPM - Normal resting lower bound
NORMAL_MAX_PACING_RATE = 120  # BPM - Normal activity upper bound
NORMAL_PACING_AMPLITUDE = 2.0  # mA - Standard pacing amplitude

# HSI thresholds for pacing decisions
# Rationale: HSI indicates cardiovascular health, guide pacing aggressiveness
HSI_CRITICAL_LOW = 30.0  # Below this: conservative pacing
HSI_LOW = 50.0  # Below this: moderate pacing
HSI_GOOD = 70.0  # Above this: minimal intervention

# Confidence thresholds for rhythm classification
# Rationale: Only act on high-confidence classifications for safety
CONFIDENCE_THRESHOLD_HIGH = 0.80  # High confidence - trust classification
CONFIDENCE_THRESHOLD_MEDIUM = 0.60  # Medium confidence - be cautious

# Rate adjustment limits per decision cycle
# Rationale: Gradual changes are safer than abrupt changes
MAX_RATE_INCREASE_PER_CYCLE = 10  # BPM - Maximum increase per decision
MAX_RATE_DECREASE_PER_CYCLE = 10  # BPM - Maximum decrease per decision


# ============================================================================
# FINITE-STATE SAFETY CONTROLLER
# ============================================================================


class SafetyState(Enum):
    """
    Finite-state machine states for safety controller.

    State transitions are deterministic and based on input validation
    and system health indicators.
    """

    # Normal operation - all inputs valid, system healthy
    NORMAL = "normal"

    # Degraded operation - some inputs questionable but within bounds
    DEGRADED = "degraded"

    # Safe mode - inputs unreliable, use conservative defaults
    SAFE_MODE = "safe_mode"

    # Emergency fallback - critical safety violation, minimal intervention
    EMERGENCY = "emergency"


class PacingMode(Enum):
    """
    Pacing modes determine the aggressiveness of intervention.

    Modes are selected based on rhythm classification, HSI, and confidence.
    """

    # No pacing - rhythm is normal and stable
    MONITOR_ONLY = "monitor_only"

    # Minimal pacing - slight adjustments for optimization
    MINIMAL = "minimal"

    # Moderate pacing - active rhythm management
    MODERATE = "moderate"

    # Aggressive pacing - significant intervention needed
    AGGRESSIVE = "aggressive"

    # Emergency pacing - life-critical intervention
    EMERGENCY = "emergency"


class SafetyController:
    """
    Finite-state safety controller for pacing decisions.

    This controller ensures all pacing commands are safe and appropriate.
    It maintains state across decisions and can degrade gracefully.

    Medical Safety: This is the primary safety layer. All pacing commands
    must pass through this controller.
    """

    def __init__(self):
        """Initialize safety controller in NORMAL state."""
        self.current_state = SafetyState.NORMAL
        self.consecutive_degraded_cycles = 0
        self.consecutive_safe_cycles = 0

        # Safety violation counters for logging/monitoring
        self.total_safety_violations = 0
        self.total_fallback_activations = 0

    def evaluate_state(
        self,
        rhythm_class: str,
        rhythm_confidence: float,
        hsi_score: float,
        heart_rate: float,
    ) -> SafetyState:
        """
        Evaluate current safety state based on inputs.

        State Transition Logic:
        - NORMAL: All inputs valid and within normal ranges
        - DEGRADED: Inputs valid but concerning (low confidence, poor HSI)
        - SAFE_MODE: Inputs questionable or contradictory
        - EMERGENCY: Critical safety violation detected

        Medical Safety: Conservative state transitions - easier to degrade
        than to upgrade. Requires multiple consecutive good cycles to upgrade.

        Args:
            rhythm_class: Classified rhythm type
            rhythm_confidence: Classification confidence (0-1)
            hsi_score: Hemodynamic surrogate index (0-100)
            heart_rate: Current heart rate in BPM

        Returns:
            Appropriate safety state
        """
        # Check for emergency conditions first
        # Rationale: Life-critical conditions take precedence
        if (
            heart_rate < ABSOLUTE_MIN_PACING_RATE
            or heart_rate > ABSOLUTE_MAX_PACING_RATE
        ):
            logger.warning(f"EMERGENCY: Heart rate {heart_rate} outside safe bounds")
            self.total_safety_violations += 1
            return SafetyState.EMERGENCY

        if hsi_score < 10.0:  # Critically low HSI
            logger.warning(f"EMERGENCY: Critically low HSI {hsi_score}")
            self.total_safety_violations += 1
            return SafetyState.EMERGENCY

        # Check for safe mode conditions
        # Rationale: Low confidence or artifact detection means unreliable data
        if rhythm_confidence < CONFIDENCE_THRESHOLD_MEDIUM:
            logger.info(f"SAFE_MODE: Low confidence {rhythm_confidence}")
            return SafetyState.SAFE_MODE

        if rhythm_class == "artifact":
            logger.info("SAFE_MODE: Artifact detected in rhythm")
            return SafetyState.SAFE_MODE

        # Check for degraded conditions
        # Rationale: Concerning but not critical - proceed with caution
        if hsi_score < HSI_CRITICAL_LOW:
            logger.info(f"DEGRADED: Low HSI {hsi_score}")
            return SafetyState.DEGRADED

        if rhythm_confidence < CONFIDENCE_THRESHOLD_HIGH:
            logger.info(f"DEGRADED: Medium confidence {rhythm_confidence}")
            return SafetyState.DEGRADED

        if rhythm_class in ["irregular", "tachycardia", "bradycardia"]:
            logger.info(f"DEGRADED: Abnormal rhythm {rhythm_class}")
            return SafetyState.DEGRADED

        # All checks passed - normal operation
        return SafetyState.NORMAL

    def update_state(self, new_state: SafetyState):
        """
        Update safety state with hysteresis.

        Medical Safety: Requires multiple consecutive good cycles to upgrade
        state, but degrades immediately on any concerning input.

        Rationale: Conservative approach - easier to be cautious than to
        assume safety too quickly.

        Args:
            new_state: Proposed new state based on current inputs
        """
        if new_state == self.current_state:
            # State unchanged - reset counters
            self.consecutive_degraded_cycles = 0
            self.consecutive_safe_cycles = 0
            return

        # Degradation happens immediately (safety-critical)
        if new_state.value > self.current_state.value:
            logger.warning(
                f"State degrading: {self.current_state.value} -> {new_state.value}"
            )
            self.current_state = new_state
            self.consecutive_degraded_cycles = 0
            self.consecutive_safe_cycles = 0
            self.total_fallback_activations += 1
            return

        # Improvement requires sustained good performance
        # Rationale: Don't trust a single good reading after problems
        if new_state.value < self.current_state.value:
            self.consecutive_safe_cycles += 1

            # Require 3 consecutive safe cycles to upgrade
            if self.consecutive_safe_cycles >= 3:
                logger.info(
                    f"State improving: {self.current_state.value} -> {new_state.value}"
                )
                self.current_state = new_state
                self.consecutive_safe_cycles = 0
            else:
                logger.debug(
                    f"Safe cycle {self.consecutive_safe_cycles}/3 for state improvement"
                )


# ============================================================================
# ADAPTIVE PACING POLICY
# ============================================================================


class AdaptivePacingPolicy:
    """
    Predictive adaptive pacing policy.

    This policy determines optimal pacing parameters based on:
    - Current rhythm classification
    - Hemodynamic status (HSI)
    - Trend information
    - Safety state

    Medical Safety: All decisions are deterministic and explainable.
    Policy includes multiple safety checks and gradual adjustments.
    """

    def __init__(self):
        """Initialize pacing policy."""
        self.safety_controller = SafetyController()
        self.last_pacing_rate = None
        self.last_pacing_amplitude = None

    def determine_pacing_mode(
        self,
        rhythm_class: str,
        rhythm_confidence: float,
        hsi_score: float,
        hsi_trend: str,
        safety_state: SafetyState,
    ) -> PacingMode:
        """
        Determine appropriate pacing mode.

        Decision Logic:
        1. Emergency state -> EMERGENCY mode
        2. Safe mode -> MINIMAL mode (conservative)
        3. Normal sinus + good HSI -> MONITOR_ONLY
        4. Abnormal rhythm + declining HSI -> AGGRESSIVE
        5. Otherwise -> MODERATE

        Medical Safety: Conservative defaults, escalate only when necessary.

        Args:
            rhythm_class: Classified rhythm
            rhythm_confidence: Classification confidence
            hsi_score: Current HSI
            hsi_trend: HSI trend direction
            safety_state: Current safety state

        Returns:
            Appropriate pacing mode
        """
        # Emergency state always uses emergency pacing
        if safety_state == SafetyState.EMERGENCY:
            logger.warning("Pacing mode: EMERGENCY (safety state)")
            return PacingMode.EMERGENCY

        # Safe mode uses minimal intervention
        # Rationale: Don't trust data, use conservative approach
        if safety_state == SafetyState.SAFE_MODE:
            logger.info("Pacing mode: MINIMAL (safe mode)")
            return PacingMode.MINIMAL

        # Normal sinus rhythm with good HSI - minimal intervention
        if rhythm_class == "normal_sinus" and hsi_score >= HSI_GOOD:
            logger.info("Pacing mode: MONITOR_ONLY (normal rhythm, good HSI)")
            return PacingMode.MONITOR_ONLY

        # Declining HSI with abnormal rhythm - aggressive intervention
        if hsi_trend == "declining" and rhythm_class in [
            "tachycardia",
            "bradycardia",
            "irregular",
        ]:
            logger.info(f"Pacing mode: AGGRESSIVE (declining HSI, {rhythm_class})")
            return PacingMode.AGGRESSIVE

        # Bradycardia or low HSI - moderate intervention
        if rhythm_class == "bradycardia" or hsi_score < HSI_LOW:
            logger.info(f"Pacing mode: MODERATE ({rhythm_class}, HSI={hsi_score})")
            return PacingMode.MODERATE

        # Tachycardia - moderate intervention (different strategy)
        if rhythm_class == "tachycardia":
            logger.info("Pacing mode: MODERATE (tachycardia)")
            return PacingMode.MODERATE

        # Default: minimal intervention
        logger.info("Pacing mode: MINIMAL (default)")
        return PacingMode.MINIMAL

    def compute_target_rate(
        self,
        current_hr: float,
        rhythm_class: str,
        hsi_score: float,
        pacing_mode: PacingMode,
    ) -> float:
        """
        Compute target pacing rate.

        Rate Determination Logic:
        - EMERGENCY: Safe default (70 BPM)
        - MONITOR_ONLY: No pacing (return current HR)
        - MINIMAL: Gentle adjustment toward normal
        - MODERATE: Active adjustment based on rhythm
        - AGGRESSIVE: Strong adjustment to stabilize

        Medical Safety: All rates clamped to absolute safe bounds.
        Changes are gradual (limited per cycle).

        Args:
            current_hr: Current heart rate
            rhythm_class: Classified rhythm
            hsi_score: Current HSI
            pacing_mode: Selected pacing mode

        Returns:
            Target pacing rate in BPM
        """
        # Emergency: Use safe default
        if pacing_mode == PacingMode.EMERGENCY:
            target = 70.0  # Safe middle-ground rate
            logger.warning(f"Emergency pacing rate: {target} BPM")
            return self._clamp_rate(target)

        # Monitor only: No pacing needed
        if pacing_mode == PacingMode.MONITOR_ONLY:
            logger.info("Monitor only - no pacing")
            return self._clamp_rate(current_hr)

        # Determine base target based on rhythm
        if rhythm_class == "bradycardia":
            # Increase rate for bradycardia
            # Target depends on HSI - lower HSI = more conservative
            if hsi_score < HSI_CRITICAL_LOW:
                base_target = 65.0  # Conservative for poor health
            else:
                base_target = 70.0  # Normal target

        elif rhythm_class == "tachycardia":
            # Decrease rate for tachycardia
            # Pacing can't directly slow heart, but can stabilize
            base_target = min(current_hr, 100.0)

        elif rhythm_class == "irregular":
            # Stabilize irregular rhythm
            base_target = 70.0  # Stable baseline

        else:  # normal_sinus or unknown
            # Maintain current rate with slight optimization
            base_target = max(60.0, min(current_hr, 80.0))

        # Adjust based on pacing mode aggressiveness
        if pacing_mode == PacingMode.MINIMAL:
            # Gentle adjustment - move 25% toward target
            target = current_hr + 0.25 * (base_target - current_hr)

        elif pacing_mode == PacingMode.MODERATE:
            # Moderate adjustment - move 50% toward target
            target = current_hr + 0.50 * (base_target - current_hr)

        elif pacing_mode == PacingMode.AGGRESSIVE:
            # Aggressive adjustment - move 75% toward target
            target = current_hr + 0.75 * (base_target - current_hr)

        else:
            target = base_target

        # Apply rate change limits (gradual changes only)
        if self.last_pacing_rate is not None:
            max_increase = self.last_pacing_rate + MAX_RATE_INCREASE_PER_CYCLE
            max_decrease = self.last_pacing_rate - MAX_RATE_DECREASE_PER_CYCLE
            target = max(max_decrease, min(max_increase, target))

        # Clamp to absolute safe bounds
        target = self._clamp_rate(target)

        logger.info(
            f"Target pacing rate: {target:.1f} BPM (from {current_hr:.1f}, mode={pacing_mode.value})"
        )
        return target

    def compute_pacing_amplitude(
        self, pacing_mode: PacingMode, hsi_score: float
    ) -> float:
        """
        Compute pacing amplitude.

        Amplitude Logic:
        - Higher HSI = lower amplitude (less intervention needed)
        - Lower HSI = higher amplitude (ensure capture)
        - Emergency = maximum safe amplitude

        Medical Safety: Amplitude always within safe bounds.

        Args:
            pacing_mode: Selected pacing mode
            hsi_score: Current HSI

        Returns:
            Pacing amplitude in mA
        """
        # Emergency: Use maximum safe amplitude
        if pacing_mode == PacingMode.EMERGENCY:
            amplitude = ABSOLUTE_MAX_PACING_AMPLITUDE
            logger.warning(f"Emergency pacing amplitude: {amplitude} mA")
            return amplitude

        # Monitor only: No pacing
        if pacing_mode == PacingMode.MONITOR_ONLY:
            return 0.0

        # Base amplitude on HSI (lower HSI = higher amplitude for safety)
        if hsi_score >= HSI_GOOD:
            base_amplitude = 1.5  # Minimal for good health
        elif hsi_score >= HSI_LOW:
            base_amplitude = 2.0  # Normal amplitude
        elif hsi_score >= HSI_CRITICAL_LOW:
            base_amplitude = 3.0  # Elevated for poor health
        else:
            base_amplitude = 4.0  # High for critical health

        # Adjust for pacing mode
        if pacing_mode == PacingMode.MINIMAL:
            amplitude = base_amplitude * 0.8
        elif pacing_mode == PacingMode.MODERATE:
            amplitude = base_amplitude
        elif pacing_mode == PacingMode.AGGRESSIVE:
            amplitude = base_amplitude * 1.2
        else:
            amplitude = base_amplitude

        # Clamp to safe bounds
        amplitude = max(
            ABSOLUTE_MIN_PACING_AMPLITUDE, min(ABSOLUTE_MAX_PACING_AMPLITUDE, amplitude)
        )

        logger.info(
            f"Pacing amplitude: {amplitude:.2f} mA (HSI={hsi_score:.1f}, mode={pacing_mode.value})"
        )
        return amplitude

    def _clamp_rate(self, rate: float) -> float:
        """
        Clamp rate to absolute safe bounds.

        Medical Safety: NEVER allow rates outside safe physiological range.

        Args:
            rate: Proposed rate

        Returns:
            Clamped rate within safe bounds
        """
        clamped = max(ABSOLUTE_MIN_PACING_RATE, min(ABSOLUTE_MAX_PACING_RATE, rate))
        if clamped != rate:
            logger.warning(f"Rate clamped: {rate:.1f} -> {clamped:.1f} BPM")
        return clamped

    def compute_pacing_command(
        self,
        rhythm_class: str,
        rhythm_confidence: float,
        hsi_score: float,
        hsi_trend: str,
        heart_rate: float,
    ) -> Dict:
        """
        Main entry point: Compute complete pacing command.

        This is the primary decision function that orchestrates:
        1. Safety state evaluation
        2. Pacing mode selection
        3. Target rate computation
        4. Amplitude computation
        5. Safety validation

        Medical Safety: Multiple layers of safety checks. Deterministic
        output for same inputs. Never crashes on invalid input.

        Args:
            rhythm_class: Classified rhythm type
            rhythm_confidence: Classification confidence
            hsi_score: Current HSI
            hsi_trend: HSI trend direction
            heart_rate: Current heart rate

        Returns:
            Dictionary with pacing command and metadata
        """
        logger.info(
            f"Computing pacing command: rhythm={rhythm_class}, confidence={rhythm_confidence:.2f}, HSI={hsi_score:.1f}, HR={heart_rate:.1f}"
        )

        # Step 1: Evaluate safety state
        new_safety_state = self.safety_controller.evaluate_state(
            rhythm_class, rhythm_confidence, hsi_score, heart_rate
        )
        self.safety_controller.update_state(new_safety_state)
        safety_state = self.safety_controller.current_state

        # Step 2: Determine pacing mode
        pacing_mode = self.determine_pacing_mode(
            rhythm_class, rhythm_confidence, hsi_score, hsi_trend, safety_state
        )

        # Step 3: Compute target rate
        target_rate = self.compute_target_rate(
            heart_rate, rhythm_class, hsi_score, pacing_mode
        )

        # Step 4: Compute amplitude
        amplitude = self.compute_pacing_amplitude(pacing_mode, hsi_score)

        # Step 5: Store for next cycle (rate limiting)
        self.last_pacing_rate = target_rate
        self.last_pacing_amplitude = amplitude

        # Step 6: Build command
        command = {
            "pacing_enabled": pacing_mode != PacingMode.MONITOR_ONLY,
            "target_rate_bpm": round(target_rate, 1),
            "pacing_amplitude_ma": round(amplitude, 2),
            "pacing_mode": pacing_mode.value,
            "safety_state": safety_state.value,
            "safety_checks": {
                "rate_within_bounds": ABSOLUTE_MIN_PACING_RATE
                <= target_rate
                <= ABSOLUTE_MAX_PACING_RATE,
                "amplitude_within_bounds": ABSOLUTE_MIN_PACING_AMPLITUDE
                <= amplitude
                <= ABSOLUTE_MAX_PACING_AMPLITUDE,
                "confidence_acceptable": rhythm_confidence
                >= CONFIDENCE_THRESHOLD_MEDIUM,
                "hsi_acceptable": hsi_score >= 10.0,
            },
            "rationale": self._generate_rationale(
                rhythm_class, hsi_score, hsi_trend, pacing_mode, safety_state
            ),
        }

        logger.info(
            f"Pacing command: enabled={command['pacing_enabled']}, rate={target_rate:.1f}, amp={amplitude:.2f}, mode={pacing_mode.value}, state={safety_state.value}"
        )

        return command

    def _generate_rationale(
        self,
        rhythm_class: str,
        hsi_score: float,
        hsi_trend: str,
        pacing_mode: PacingMode,
        safety_state: SafetyState,
    ) -> str:
        """
        Generate human-readable rationale for decision.

        Medical Safety: Transparency is critical for medical devices.
        All decisions must be explainable.

        Args:
            rhythm_class: Classified rhythm
            hsi_score: Current HSI
            hsi_trend: HSI trend
            pacing_mode: Selected mode
            safety_state: Current state

        Returns:
            Human-readable explanation
        """
        parts = []

        # Safety state
        if safety_state == SafetyState.EMERGENCY:
            parts.append("EMERGENCY safety state - using conservative defaults")
        elif safety_state == SafetyState.SAFE_MODE:
            parts.append("Safe mode active - unreliable data, minimal intervention")
        elif safety_state == SafetyState.DEGRADED:
            parts.append("Degraded operation - proceeding with caution")

        # Rhythm
        if rhythm_class == "normal_sinus":
            parts.append("Normal sinus rhythm detected")
        elif rhythm_class == "bradycardia":
            parts.append("Bradycardia detected - increasing pacing rate")
        elif rhythm_class == "tachycardia":
            parts.append("Tachycardia detected - stabilizing rhythm")
        elif rhythm_class == "irregular":
            parts.append("Irregular rhythm - stabilization needed")
        elif rhythm_class == "artifact":
            parts.append("Signal artifact - using safe defaults")

        # HSI
        if hsi_score >= HSI_GOOD:
            parts.append(f"Good cardiovascular status (HSI={hsi_score:.1f})")
        elif hsi_score >= HSI_LOW:
            parts.append(f"Fair cardiovascular status (HSI={hsi_score:.1f})")
        else:
            parts.append(
                f"Poor cardiovascular status (HSI={hsi_score:.1f}) - conservative approach"
            )

        # Trend
        if hsi_trend == "improving":
            parts.append("HSI improving")
        elif hsi_trend == "declining":
            parts.append("HSI declining - increased monitoring")

        # Mode
        parts.append(f"Pacing mode: {pacing_mode.value}")

        return "; ".join(parts)


# ============================================================================
# GLOBAL POLICY INSTANCE
# ============================================================================

# Global policy instance
# Maintains state across requests for rate limiting and hysteresis
pacing_policy = AdaptivePacingPolicy()


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================


def process_pacing_decision(rhythm_data: Dict, hsi_data: Dict) -> Dict:
    """
    Process pacing decision from rhythm and HSI data.

    Medical Safety: This is the main entry point for pacing decisions.
    Includes comprehensive input validation and error handling.
    NEVER crashes - always returns a safe response.

    Args:
        rhythm_data: Rhythm classification data
        hsi_data: HSI computation data

    Returns:
        Pacing command with full metadata

    Raises:
        ValueError: If inputs are invalid (caught and handled gracefully)
    """
    try:
        # Extract and validate rhythm data
        rhythm_class = rhythm_data.get("rhythm_class", "artifact")
        rhythm_confidence = float(rhythm_data.get("confidence", 0.0))

        # Extract and validate HSI data
        hsi_score = float(hsi_data.get("hsi_score", 50.0))
        hsi_trend = hsi_data.get("trend", {}).get("trend_direction", "stable")

        # Extract heart rate (from HSI input features)
        input_features = hsi_data.get("input_features", {})
        heart_rate = float(input_features.get("heart_rate_bpm", 70.0))

        # Validate ranges
        rhythm_confidence = max(0.0, min(1.0, rhythm_confidence))
        hsi_score = max(0.0, min(100.0, hsi_score))
        heart_rate = max(30.0, min(250.0, heart_rate))

        # Compute pacing command
        command = pacing_policy.compute_pacing_command(
            rhythm_class, rhythm_confidence, hsi_score, hsi_trend, heart_rate
        )

        return {
            "success": True,
            "pacing_command": command,
            "input_summary": {
                "rhythm_class": rhythm_class,
                "rhythm_confidence": rhythm_confidence,
                "hsi_score": hsi_score,
                "hsi_trend": hsi_trend,
                "heart_rate_bpm": heart_rate,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        # Medical Safety: NEVER crash - return safe fallback
        logger.error(f"Error in pacing decision: {e}", exc_info=True)

        # Return safe fallback command
        return {
            "success": False,
            "error": str(e),
            "pacing_command": {
                "pacing_enabled": False,
                "target_rate_bpm": 70.0,
                "pacing_amplitude_ma": 0.0,
                "pacing_mode": "monitor_only",
                "safety_state": "emergency",
                "safety_checks": {
                    "rate_within_bounds": True,
                    "amplitude_within_bounds": True,
                    "confidence_acceptable": False,
                    "hsi_acceptable": False,
                },
                "rationale": f"Error occurred: {str(e)} - using safe fallback (no pacing)",
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
