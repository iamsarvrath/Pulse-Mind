"""
Hemodynamic Surrogate Index (HSI) Computation Module

This module computes a time-aware hemodynamic surrogate index from PPG-derived features.
The HSI provides an estimate of cardiovascular health status based on heart rate,
heart rate variability, and pulse amplitude.

All formulas and constants are documented for transparency and reproducibility.
"""

import sys
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logger import setup_logger

logger = setup_logger("hsi-computer", level="INFO")


# ============================================================================
# CONSTANTS AND NORMALIZATION PARAMETERS
# ============================================================================

# Heart Rate (HR) normalization parameters
# Based on typical resting heart rate ranges for adults
HR_MIN = 40.0  # bpm - Lower bound (athletic/bradycardia threshold)
HR_MAX = 120.0  # bpm - Upper bound (tachycardia threshold)
HR_OPTIMAL = 70.0  # bpm - Optimal resting heart rate

# Heart Rate Variability (HRV) normalization parameters
# SDNN values in milliseconds - higher indicates better autonomic function
HRV_MIN = 10.0  # ms - Poor HRV (high stress/poor health)
HRV_MAX = 100.0  # ms - Excellent HRV (low stress/good health)
HRV_OPTIMAL = 50.0  # ms - Good HRV baseline

# Pulse Amplitude normalization parameters
# Relative values - higher indicates better perfusion
PULSE_AMP_MIN = 5.0  # Weak pulse (poor perfusion)
PULSE_AMP_MAX = 50.0  # Strong pulse (good perfusion)
PULSE_AMP_OPTIMAL = 25.0  # Normal pulse amplitude

# Feature weights for HSI calculation
# These weights determine the relative importance of each feature
# Total should sum to 1.0 for interpretability
WEIGHT_HR = 0.35  # Heart rate contributes 35% (primary indicator)
WEIGHT_HRV = 0.40  # HRV contributes 40% (most sensitive to stress/health)
WEIGHT_PULSE = 0.25  # Pulse amplitude contributes 25% (perfusion indicator)

# HSI score ranges (0-100 scale)
HSI_EXCELLENT = 80.0  # Excellent cardiovascular status
HSI_GOOD = 60.0  # Good cardiovascular status
HSI_FAIR = 40.0  # Fair cardiovascular status
HSI_POOR = 20.0  # Poor cardiovascular status

# Trend calculation parameters
TREND_SIGNIFICANT_THRESHOLD = 5.0  # HSI points - minimum change to be "significant"
TREND_TIME_WINDOW_SECONDS = 300.0  # 5 minutes - time window for trend rate calculation


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================


def normalize_heart_rate(hr_bpm: float) -> float:
    """
    Normalize heart rate to 0-1 scale with optimal weighting.

    Formula:
    - If HR < HR_OPTIMAL: score = 1.0 - ((HR_OPTIMAL - HR) / (HR_OPTIMAL - HR_MIN))^2
    - If HR >= HR_OPTIMAL: score = 1.0 - ((HR - HR_OPTIMAL) / (HR_MAX - HR_OPTIMAL))^2

    This creates a parabolic curve with peak at HR_OPTIMAL, penalizing
    both bradycardia and tachycardia.

    Args:
        hr_bpm: Heart rate in beats per minute

    Returns:
        Normalized score between 0 and 1 (1 = optimal)
    """
    # Clamp to valid range
    hr_clamped = max(HR_MIN, min(HR_MAX, hr_bpm))

    if hr_clamped < HR_OPTIMAL:
        # Below optimal - penalize deviation from optimal
        deviation = (HR_OPTIMAL - hr_clamped) / (HR_OPTIMAL - HR_MIN)
        score = 1.0 - (deviation**2)
    else:
        # Above optimal - penalize deviation from optimal
        deviation = (hr_clamped - HR_OPTIMAL) / (HR_MAX - HR_OPTIMAL)
        score = 1.0 - (deviation**2)

    return max(0.0, min(1.0, score))


def normalize_hrv(hrv_sdnn_ms: float) -> float:
    """
    Normalize HRV (SDNN) to 0-1 scale.

    Formula:
    - score = (HRV - HRV_MIN) / (HRV_MAX - HRV_MIN)

    Higher HRV is better (indicates good autonomic function and low stress).
    Linear normalization is used as HRV benefits scale linearly.

    Args:
        hrv_sdnn_ms: HRV SDNN in milliseconds

    Returns:
        Normalized score between 0 and 1 (1 = excellent HRV)
    """
    # Clamp to valid range
    hrv_clamped = max(HRV_MIN, min(HRV_MAX, hrv_sdnn_ms))

    # Linear normalization
    score = (hrv_clamped - HRV_MIN) / (HRV_MAX - HRV_MIN)

    return max(0.0, min(1.0, score))


def normalize_pulse_amplitude(pulse_amp: float) -> float:
    """
    Normalize pulse amplitude to 0-1 scale.

    Formula:
    - score = (PULSE_AMP - PULSE_AMP_MIN) / (PULSE_AMP_MAX - PULSE_AMP_MIN)

    Higher amplitude indicates better peripheral perfusion.
    Linear normalization is appropriate for perfusion indicators.

    Args:
        pulse_amp: Pulse amplitude in arbitrary units

    Returns:
        Normalized score between 0 and 1 (1 = strong pulse)
    """
    # Clamp to valid range
    amp_clamped = max(PULSE_AMP_MIN, min(PULSE_AMP_MAX, pulse_amp))

    # Linear normalization
    score = (amp_clamped - PULSE_AMP_MIN) / (PULSE_AMP_MAX - PULSE_AMP_MIN)

    return max(0.0, min(1.0, score))


# ============================================================================
# HSI COMPUTATION
# ============================================================================


def compute_hsi(
    heart_rate_bpm: float, hrv_sdnn_ms: float, pulse_amplitude: float
) -> Dict[str, float]:
    """
    Compute Hemodynamic Surrogate Index from PPG-derived features.

    The HSI is a weighted combination of normalized cardiovascular features:

    Formula:
    HSI = 100 * (
        WEIGHT_HR * normalize_hr(HR) +
        WEIGHT_HRV * normalize_hrv(HRV) +
        WEIGHT_PULSE * normalize_pulse(PULSE)
    )

    The result is scaled to 0-100 for interpretability:
    - 80-100: Excellent cardiovascular status
    - 60-80: Good cardiovascular status
    - 40-60: Fair cardiovascular status
    - 20-40: Poor cardiovascular status
    - 0-20: Very poor cardiovascular status

    Args:
        heart_rate_bpm: Heart rate in BPM
        hrv_sdnn_ms: HRV SDNN in milliseconds
        pulse_amplitude: Pulse amplitude in arbitrary units

    Returns:
        Dictionary containing:
        - hsi_score: Overall HSI score (0-100)
        - hr_contribution: HR component contribution
        - hrv_contribution: HRV component contribution
        - pulse_contribution: Pulse component contribution
        - normalized_hr: Normalized HR score (0-1)
        - normalized_hrv: Normalized HRV score (0-1)
        - normalized_pulse: Normalized pulse score (0-1)
    """
    logger.info(
        f"Computing HSI: HR={heart_rate_bpm}, HRV={hrv_sdnn_ms}, Pulse={pulse_amplitude}"
    )

    # Normalize each feature
    norm_hr = normalize_heart_rate(heart_rate_bpm)
    norm_hrv = normalize_hrv(hrv_sdnn_ms)
    norm_pulse = normalize_pulse_amplitude(pulse_amplitude)

    # Calculate weighted contributions
    hr_contrib = WEIGHT_HR * norm_hr
    hrv_contrib = WEIGHT_HRV * norm_hrv
    pulse_contrib = WEIGHT_PULSE * norm_pulse

    # Compute final HSI score (0-100 scale)
    hsi_score = 100.0 * (hr_contrib + hrv_contrib + pulse_contrib)

    logger.info(
        f"HSI computed: {hsi_score:.2f} (HR:{hr_contrib:.3f}, HRV:{hrv_contrib:.3f}, Pulse:{pulse_contrib:.3f})"
    )

    return {
        "hsi_score": round(hsi_score, 2),
        "hr_contribution": round(hr_contrib, 4),
        "hrv_contribution": round(hrv_contrib, 4),
        "pulse_contribution": round(pulse_contrib, 4),
        "normalized_hr": round(norm_hr, 4),
        "normalized_hrv": round(norm_hrv, 4),
        "normalized_pulse": round(norm_pulse, 4),
    }


def interpret_hsi(hsi_score: float) -> str:
    """
    Provide human-readable interpretation of HSI score.

    Args:
        hsi_score: HSI score (0-100)

    Returns:
        Interpretation string
    """
    if hsi_score >= HSI_EXCELLENT:
        return "excellent"
    elif hsi_score >= HSI_GOOD:
        return "good"
    elif hsi_score >= HSI_FAIR:
        return "fair"
    elif hsi_score >= HSI_POOR:
        return "poor"
    else:
        return "very_poor"


# ============================================================================
# TREND CALCULATION
# ============================================================================


def compute_trend(
    current_measurement: Dict, previous_measurement: Optional[Dict] = None
) -> Dict:
    """
    Compute time-aware trend analysis between measurements.

    Calculates:
    1. Absolute change (delta) in HSI
    2. Rate of change (delta per minute)
    3. Trend direction and significance

    Args:
        current_measurement: Current measurement dict with 'hsi_score' and 'timestamp'
        previous_measurement: Previous measurement dict (optional)

    Returns:
        Dictionary containing:
        - delta_hsi: Change in HSI score
        - delta_per_minute: Rate of change (HSI points per minute)
        - trend_direction: 'improving', 'stable', or 'declining'
        - is_significant: Whether change exceeds threshold
        - time_elapsed_seconds: Time between measurements
    """
    if previous_measurement is None:
        logger.info("No previous measurement - trend cannot be computed")
        return {
            "delta_hsi": 0.0,
            "delta_per_minute": 0.0,
            "trend_direction": "stable",
            "is_significant": False,
            "time_elapsed_seconds": 0.0,
        }

    # Extract HSI scores
    current_hsi = current_measurement.get("hsi_score", 0.0)
    previous_hsi = previous_measurement.get("hsi_score", 0.0)

    # Calculate delta
    delta_hsi = current_hsi - previous_hsi

    # Parse timestamps and calculate time elapsed
    current_time = datetime.fromisoformat(
        current_measurement["timestamp"].replace("Z", "+00:00")
    )
    previous_time = datetime.fromisoformat(
        previous_measurement["timestamp"].replace("Z", "+00:00")
    )
    time_elapsed = (current_time - previous_time).total_seconds()

    # Calculate rate of change (per minute)
    if time_elapsed > 0:
        delta_per_minute = (delta_hsi / time_elapsed) * 60.0
    else:
        delta_per_minute = 0.0

    # Determine trend direction
    if abs(delta_hsi) < TREND_SIGNIFICANT_THRESHOLD:
        trend_direction = "stable"
        is_significant = False
    elif delta_hsi > 0:
        trend_direction = "improving"
        is_significant = True
    else:
        trend_direction = "declining"
        is_significant = True

    logger.info(
        f"Trend: {trend_direction}, delta={delta_hsi:.2f}, rate={delta_per_minute:.2f}/min"
    )

    return {
        "delta_hsi": round(delta_hsi, 2),
        "delta_per_minute": round(delta_per_minute, 3),
        "trend_direction": trend_direction,
        "is_significant": is_significant,
        "time_elapsed_seconds": round(time_elapsed, 1),
    }


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================


def process_hsi_computation(
    features: Dict,
    previous_measurement: Optional[Dict] = None,
    timestamp: Optional[str] = None,
) -> Dict:
    """
    Main stateless function to compute HSI and trends.

    This function is completely stateless - all required data must be provided
    in the input parameters. No internal state is maintained.

    Args:
        features: Dictionary with 'heart_rate_bpm', 'hrv_sdnn_ms', 'pulse_amplitude'
        previous_measurement: Optional previous measurement for trend calculation
        timestamp: Optional ISO timestamp (defaults to current UTC time)

    Returns:
        Dictionary with HSI results, interpretation, and trend analysis

    Raises:
        ValueError: If required features are missing or invalid
    """
    logger.info("Processing HSI computation request")

    # Validate required features
    required_fields = ["heart_rate_bpm", "hrv_sdnn_ms", "pulse_amplitude"]
    for field in required_fields:
        if field not in features:
            raise ValueError(f"Missing required field: '{field}'")

    # Extract and validate feature values
    try:
        hr = float(features["heart_rate_bpm"])
        hrv = float(features["hrv_sdnn_ms"])
        pulse = float(features["pulse_amplitude"])
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid feature value: {e}")

    # Validate ranges
    if hr <= 0 or hr > 300:
        raise ValueError(f"Heart rate out of valid range: {hr} BPM")
    if hrv < 0 or hrv > 500:
        raise ValueError(f"HRV out of valid range: {hrv} ms")
    if pulse < 0:
        raise ValueError(f"Pulse amplitude must be non-negative: {pulse}")

    # Use provided timestamp or generate current one
    if timestamp is None:
        timestamp = datetime.utcnow().isoformat() + "Z"

    # Compute HSI
    hsi_result = compute_hsi(hr, hrv, pulse)
    hsi_score = hsi_result["hsi_score"]

    # Interpret HSI
    interpretation = interpret_hsi(hsi_score)

    # Create current measurement for trend calculation
    current_measurement = {"hsi_score": hsi_score, "timestamp": timestamp}

    # Compute trend
    trend = compute_trend(current_measurement, previous_measurement)

    # Assemble result
    result = {
        "success": True,
        "hsi": hsi_result,
        "interpretation": interpretation,
        "trend": trend,
        "timestamp": timestamp,
        "input_features": {
            "heart_rate_bpm": hr,
            "hrv_sdnn_ms": hrv,
            "pulse_amplitude": pulse,
        },
    }

    logger.info(
        f"HSI computation completed: score={hsi_score:.2f}, interpretation={interpretation}"
    )

    return result
