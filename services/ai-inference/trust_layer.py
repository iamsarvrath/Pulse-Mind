"""XAI Trust Layer for PulseMind Rhythm Classification.

This module provides a lightweight, deterministic trust assessment layer
that enriches AI inference output with:
  - trust_flag:          Boolean indicating whether the prediction meets
                         the minimum confidence threshold for clinical use.
  - explanation_summary: Human-readable explanation of the key feature(s)
                         that contributed to the model's classification.

Design Principles:
  1. Post-processing only — the underlying model is never modified.
  2. Deterministic — same inputs always produce the same outputs.
  3. Lightweight — pure Python, no external ML-explainability libraries.
  4. Defensive — all inputs accessed via .get() with safe defaults.
  5. Non-mutating — the original prediction dict is never modified in-place.

Usage:
    from ai_training.xai.trust_layer import apply_trust_layer

    enriched = apply_trust_layer(prediction, features)
"""

from typing import Dict


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum confidence required to trust a prediction for clinical decisions.
# Below this threshold the prediction is flagged as untrusted so that
# downstream consumers (e.g. Control Engine) can fall back to safe mode.
TRUST_CONFIDENCE_THRESHOLD: float = 0.60

# Feature-value thresholds used to generate explanations.
HR_TACHYCARDIA_THRESHOLD: float = 120.0
HR_BRADYCARDIA_THRESHOLD: float = 60.0
HRV_IRREGULAR_THRESHOLD: float = 100.0


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def compute_trust_flag(confidence: float) -> bool:
    """Map a model confidence score to a boolean trust flag.

    Args:
        confidence: Model confidence for the predicted class (0.0–1.0).

    Returns:
        True  if confidence >= TRUST_CONFIDENCE_THRESHOLD (trusted).
        False if confidence <  TRUST_CONFIDENCE_THRESHOLD (untrusted).
    """
    return confidence >= TRUST_CONFIDENCE_THRESHOLD


def generate_explanation_summary(
    rhythm_class: str,
    heart_rate_bpm: float,
    hrv_sdnn_ms: float,
) -> str:
    """Generate a concise, human-readable explanation for a classification.

    The explanation highlights the dominant clinical feature that aligns
    with the predicted rhythm class, providing transparency without
    requiring heavy explainability frameworks.

    Args:
        rhythm_class:  The predicted rhythm class string.
        heart_rate_bpm: Heart rate in beats per minute.
        hrv_sdnn_ms:    Heart-rate variability (SDNN) in milliseconds.

    Returns:
        A single-sentence explanation string.
    """
    if rhythm_class == "tachycardia" and heart_rate_bpm > HR_TACHYCARDIA_THRESHOLD:
        return (
            f"Elevated heart rate ({heart_rate_bpm:.1f} BPM) strongly "
            f"contributed to tachycardia classification."
        )

    if rhythm_class == "bradycardia" and heart_rate_bpm < HR_BRADYCARDIA_THRESHOLD:
        return (
            f"Reduced heart rate ({heart_rate_bpm:.1f} BPM) contributed "
            f"to bradycardia classification."
        )

    if rhythm_class == "irregular" and hrv_sdnn_ms > HRV_IRREGULAR_THRESHOLD:
        return (
            f"Increased heart rate variability ({hrv_sdnn_ms:.1f} ms) "
            f"contributed to irregular rhythm classification."
        )

    if rhythm_class == "artifact":
        return (
            "Signal irregularities or noise patterns contributed to "
            "artifact classification."
        )

    # Default: no single dominant feature can be isolated.
    return "Model prediction based on composite feature evaluation."


def apply_trust_layer(prediction: Dict, features: Dict) -> Dict:
    """Enrich a rhythm-classification prediction with trust metadata.

    This is the primary entry point for the XAI Trust Layer.  It accepts
    the raw prediction dictionary produced by ``classify_rhythm()`` and
    the input feature dictionary, then returns a **new** dictionary that
    contains all original fields plus:

      * ``trust_flag``          – bool
      * ``explanation_summary`` – str

    The original *prediction* dict is **never** modified in-place.

    Args:
        prediction: Raw prediction output from the classifier.
            Expected keys (all accessed defensively via ``.get()``):
                - ``rhythm_class``            (str)
                - ``confidence``              (float, 0–1)
                - ``confidence_level``        (str)
                - ``probability_distribution`` (dict)
        features: Input feature dictionary.
            Expected keys:
                - ``heart_rate_bpm``   (float)
                - ``hrv_sdnn_ms``      (float)
                - ``pulse_amplitude``  (float)

    Returns:
        A new dictionary containing every key from *prediction* plus
        ``trust_flag`` and ``explanation_summary``.
    """
    # --- Defensive extraction ------------------------------------------------
    rhythm_class: str = prediction.get("rhythm_class", "unknown")
    confidence: float = float(prediction.get("confidence", 0.0))

    heart_rate_bpm: float = float(features.get("heart_rate_bpm", 0.0))
    hrv_sdnn_ms: float = float(features.get("hrv_sdnn_ms", 0.0))

    # --- Compute trust metadata ----------------------------------------------
    trust_flag: bool = compute_trust_flag(confidence)

    explanation_summary: str = generate_explanation_summary(
        rhythm_class,
        heart_rate_bpm,
        hrv_sdnn_ms,
    )

    # --- Build enriched (non-mutating) copy ----------------------------------
    enriched: Dict = {**prediction}
    enriched["trust_flag"] = trust_flag
    enriched["explanation_summary"] = explanation_summary

    return enriched
