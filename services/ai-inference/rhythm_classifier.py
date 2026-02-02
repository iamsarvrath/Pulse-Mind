"""
Rhythm Classification Inference Module

This module provides lightweight rhythm classification using a pretrained model.
Designed for low-latency inference without GPU requirements.

Design Decisions:
1. Async model loading - doesn't block Flask startup
2. Graceful fallback - service runs even if model fails to load
3. Model warm-up - pre-allocates resources for consistent latency
4. CPU-optimized - no GPU assumptions, works on any hardware
5. Lightweight model - Random Forest for fast inference (<10ms)
"""

import sys
import os
import numpy as np
import pickle
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logger import setup_logger

logger = setup_logger("rhythm-classifier", level="INFO")


# ============================================================================
# RHYTHM CLASSES
# ============================================================================

# Supported rhythm classifications
# These are common cardiac rhythm patterns detected from PPG features
RHYTHM_CLASSES = [
    "normal_sinus",  # Normal sinus rhythm (healthy)
    "tachycardia",  # Elevated heart rate
    "bradycardia",  # Low heart rate
    "irregular",  # Irregular rhythm (possible arrhythmia)
    "artifact",  # Signal artifact/poor quality
]

# Confidence thresholds
CONFIDENCE_HIGH = 0.80  # High confidence threshold
CONFIDENCE_MEDIUM = 0.60  # Medium confidence threshold
# Below 0.60 is considered low confidence


# ============================================================================
# LIGHTWEIGHT MODEL IMPLEMENTATION
# ============================================================================


class RhythmClassifier:
    """
    Lightweight rhythm classification model.

    Design: Uses Random Forest for fast, CPU-efficient inference.
    No GPU required, consistent low latency (<10ms typical).
    """

    def __init__(self):
        """Initialize classifier with no model loaded."""
        self.model = None
        self.is_loaded = False
        self.model_path = os.path.join(
            os.path.dirname(__file__), "models", "pulsemind_rf_model.pkl"
        )
        self.warmup_complete = False

    def create_default_model(self):
        """
        Create a simple rule-based model as fallback.

        This is used when the pretrained model file is missing.
        Provides basic rhythm classification based on feature thresholds.

        Design Decision: Always have a working classifier, even without
        a trained model file. This ensures the service is always functional.
        """
        from sklearn.ensemble import RandomForestClassifier

        logger.info("Creating default rule-based model")

        # Create a simple Random Forest with default parameters
        # In production, this would be replaced with a pretrained model
        model = RandomForestClassifier(
            n_estimators=10,  # Small number for fast inference
            max_depth=5,  # Shallow trees for speed
            random_state=42,
            n_jobs=1,  # Single thread for predictable latency
        )

        # Create synthetic training data for basic rhythm patterns
        # Features: [heart_rate, hrv, pulse_amplitude]
        X_train = np.array(
            [
                # Normal sinus rhythm (HR 60-100, good HRV, good pulse)
                [70, 50, 25],
                [75, 55, 28],
                [65, 48, 22],
                [80, 52, 26],
                # Tachycardia (HR >100, low HRV, variable pulse)
                [110, 20, 18],
                [120, 15, 20],
                [105, 22, 19],
                [115, 18, 21],
                # Bradycardia (HR <60, variable HRV, weak pulse)
                [45, 35, 15],
                [50, 40, 12],
                [48, 38, 14],
                [52, 42, 16],
                # Irregular (variable HR, very low HRV, variable pulse)
                [85, 12, 20],
                [90, 10, 22],
                [88, 11, 19],
                [92, 13, 21],
                # Artifact (extreme values, very low HRV, very low pulse)
                [150, 5, 8],
                [30, 8, 6],
                [140, 6, 7],
                [35, 7, 9],
            ]
        )

        y_train = np.array(
            [
                0,
                0,
                0,
                0,  # normal_sinus
                1,
                1,
                1,
                1,  # tachycardia
                2,
                2,
                2,
                2,  # bradycardia
                3,
                3,
                3,
                3,  # irregular
                4,
                4,
                4,
                4,  # artifact
            ]
        )

        # Train the model
        model.fit(X_train, y_train)

        logger.info("Default model created and trained")
        return model

    def load_model(self) -> bool:
        """
        Load pretrained model from disk.

        Design Decision: Async loading pattern - this is called in a background
        thread so it doesn't block Flask startup. Service can handle requests
        immediately, even while model is loading.

        Returns:
            True if model loaded successfully, False otherwise
        """
        try:
            logger.info(f"Attempting to load model from {self.model_path}")

            # Check if model file exists
            if os.path.exists(self.model_path):
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                logger.info("Pretrained model loaded successfully")
            else:
                logger.warning(f"Model file not found at {self.model_path}")
                logger.info("Creating default model as fallback")
                self.model = self.create_default_model()

            self.is_loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            logger.info("Creating default model as fallback")
            try:
                self.model = self.create_default_model()
                self.is_loaded = True
                return True
            except Exception as e2:
                logger.error(f"Failed to create default model: {e2}")
                self.is_loaded = False
                return False

    def warm_up(self):
        """
        Warm up the model with dummy predictions.

        Design Decision: Pre-allocate resources and JIT compile code paths
        to ensure consistent latency for real requests. First prediction is
        often slower due to lazy initialization - we do this during startup.
        """
        if not self.is_loaded:
            logger.warning("Cannot warm up - model not loaded")
            return

        logger.info("Starting model warm-up")

        try:
            # Run several dummy predictions to warm up
            dummy_features = np.array([[70.0, 50.0, 25.0]])

            for i in range(5):
                _ = self.model.predict(dummy_features)
                _ = self.model.predict_proba(dummy_features)

            self.warmup_complete = True
            logger.info("Model warm-up completed")

        except Exception as e:
            logger.error(f"Model warm-up failed: {e}")
            self.warmup_complete = False

    def predict(self, features: np.ndarray) -> Tuple[str, float, List[float]]:
        """
        Predict rhythm class from feature vector.

        Design Decision: Returns both class and confidence for transparency.
        Caller can decide how to handle low-confidence predictions.

        Args:
            features: Feature vector [heart_rate, hrv, pulse_amplitude]

        Returns:
            Tuple of (rhythm_class, confidence, all_probabilities)

        Raises:
            RuntimeError: If model is not loaded
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded - cannot perform inference")

        # Ensure features are 2D array (sklearn requirement)
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Get prediction and probabilities
        # Design: predict_proba gives us confidence scores for all classes
        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]

        # Get predicted class and confidence
        rhythm_class = RHYTHM_CLASSES[prediction]
        confidence = float(probabilities[prediction])
        all_probs = [float(p) for p in probabilities]

        return rhythm_class, confidence, all_probs


# ============================================================================
# GLOBAL CLASSIFIER INSTANCE
# ============================================================================

# Global classifier instance
# Design Decision: Single global instance to avoid reloading model for each request
# Thread-safe for read operations (predictions)
classifier = RhythmClassifier()


def load_model_async():
    """
    Load model asynchronously in background thread.

    Design Decision: Non-blocking startup - Flask can start serving requests
    immediately while model loads in background. Health endpoint works even
    if model loading is slow or fails.
    """
    logger.info("Starting async model loading")
    success = classifier.load_model()

    if success:
        # Warm up the model after loading
        classifier.warm_up()
        logger.info("Model loading and warm-up complete")
    else:
        logger.error("Model loading failed - inference will not be available")


# ============================================================================
# INFERENCE FUNCTIONS
# ============================================================================


def classify_rhythm(
    heart_rate_bpm: float, hrv_sdnn_ms: float, pulse_amplitude: float
) -> Dict:
    """
    Classify cardiac rhythm from PPG-derived features.

    Design Decision: Simple feature vector (3 features) for fast inference.
    More features would increase accuracy but also latency.

    Args:
        heart_rate_bpm: Heart rate in BPM
        hrv_sdnn_ms: HRV SDNN in milliseconds
        pulse_amplitude: Pulse amplitude in arbitrary units

    Returns:
        Dictionary with classification results

    Raises:
        RuntimeError: If model is not loaded
        ValueError: If features are invalid
    """
    logger.info(
        f"Classifying rhythm: HR={heart_rate_bpm}, HRV={hrv_sdnn_ms}, Pulse={pulse_amplitude}"
    )

    # Validate inputs
    if heart_rate_bpm <= 0 or heart_rate_bpm > 300:
        raise ValueError(f"Invalid heart rate: {heart_rate_bpm} BPM")
    if hrv_sdnn_ms < 0 or hrv_sdnn_ms > 500:
        raise ValueError(f"Invalid HRV: {hrv_sdnn_ms} ms")
    if pulse_amplitude < 0:
        raise ValueError(f"Invalid pulse amplitude: {pulse_amplitude}")

    # Create feature vector
    features = np.array([heart_rate_bpm, hrv_sdnn_ms, pulse_amplitude])

    # Perform inference
    start_time = time.time()
    rhythm_class, confidence, all_probs = classifier.predict(features)
    inference_time_ms = (time.time() - start_time) * 1000

    # Determine confidence level
    if confidence >= CONFIDENCE_HIGH:
        confidence_level = "high"
    elif confidence >= CONFIDENCE_MEDIUM:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    # Build probability distribution
    prob_distribution = {
        RHYTHM_CLASSES[i]: all_probs[i] for i in range(len(RHYTHM_CLASSES))
    }

    result = {
        "rhythm_class": rhythm_class,
        "confidence": round(confidence, 4),
        "confidence_level": confidence_level,
        "probability_distribution": {
            k: round(v, 4) for k, v in prob_distribution.items()
        },
        "inference_time_ms": round(inference_time_ms, 3),
    }

    logger.info(
        f"Classification: {rhythm_class} (confidence: {confidence:.2f}, {inference_time_ms:.2f}ms)"
    )

    return result


def get_model_status() -> Dict:
    """
    Get current model loading status.

    Design Decision: Expose model status so clients can know if predictions
    are available. Useful for health checks and debugging.

    Returns:
        Dictionary with model status information
    """
    return {
        "model_loaded": classifier.is_loaded,
        "warmup_complete": classifier.warmup_complete,
        "model_path": classifier.model_path,
        "supported_classes": RHYTHM_CLASSES,
    }
