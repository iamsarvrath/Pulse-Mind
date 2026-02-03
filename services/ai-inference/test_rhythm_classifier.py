"""Unit tests for Rhythm Classification Inference Module."""

import unittest
import numpy as np
import os
import sys

# Add the service directory to the path so we can import the module
sys.path.insert(0, os.path.dirname(__file__))

from rhythm_classifier import RhythmClassifier, classify_rhythm, RHYTHM_CLASSES

class TestRhythmClassifier(unittest.TestCase):
    """Test the RhythmClassifier class."""

    def setUp(self):
        """Set up a fresh classifier for each test."""
        self.classifier = RhythmClassifier()
        # Always use the default model for unit tests to ensure predictability
        self.classifier.model = self.classifier.create_default_model()
        self.classifier.is_loaded = True

    def test_predict_normal_sinus(self):
        """Test prediction of normal sinus rhythm."""
        # Features: [heart_rate, hrv, pulse_amplitude]
        features = np.array([[70.0, 50.0, 25.0]])
        rhythm_class, confidence, _ = self.classifier.predict(features)
        self.assertEqual(rhythm_class, "normal_sinus")
        self.assertGreaterEqual(confidence, 0.5)

    def test_predict_tachycardia(self):
        """Test prediction of tachycardia."""
        features = np.array([[115.0, 18.0, 21.0]])
        rhythm_class, confidence, _ = self.classifier.predict(features)
        self.assertEqual(rhythm_class, "tachycardia")

    def test_predict_bradycardia(self):
        """Test prediction of bradycardia."""
        features = np.array([[48.0, 38.0, 14.0]])
        rhythm_class, confidence, _ = self.classifier.predict(features)
        self.assertEqual(rhythm_class, "bradycardia")

    def test_predict_irregular(self):
        """Test prediction of irregular rhythm."""
        features = np.array([[88.0, 11.0, 19.0]])
        rhythm_class, confidence, _ = self.classifier.predict(features)
        self.assertEqual(rhythm_class, "irregular")

    def test_predict_artifact(self):
        """Test prediction of artifact."""
        features = np.array([[140.0, 6.0, 7.0]])
        rhythm_class, confidence, _ = self.classifier.predict(features)
        self.assertEqual(rhythm_class, "artifact")

    def test_predict_unloaded_model(self):
        """Test that predict raises RuntimeError if model is not loaded."""
        unloaded_classifier = RhythmClassifier()
        features = np.array([[70.0, 50.0, 25.0]])
        with self.assertRaises(RuntimeError):
            unloaded_classifier.predict(features)

class TestInferenceFunctions(unittest.TestCase):
    """Test top-level inference functions."""

    def test_classify_rhythm_valid(self):
        """Test classify_rhythm with valid inputs."""
        # Note: This relies on the global classifier being initialized.
        # For unit tests, we'll assume it's loaded with the default model.
        from rhythm_classifier import classifier
        if not classifier.is_loaded:
            classifier.load_model()
            
        result = classify_rhythm(72.0, 45.0, 20.0)
        self.assertIn("rhythm_class", result)
        self.assertIn("confidence", result)
        self.assertIn("confidence_level", result)
        self.assertIn("probability_distribution", result)

    def test_classify_rhythm_invalid_hr(self):
        """Test classify_rhythm with invalid heart rate."""
        with self.assertRaises(ValueError):
            classify_rhythm(-10, 50, 20)
        with self.assertRaises(ValueError):
            classify_rhythm(400, 50, 20)

    def test_classify_rhythm_invalid_hrv(self):
        """Test classify_rhythm with invalid HRV."""
        with self.assertRaises(ValueError):
            classify_rhythm(70, -5, 20)
        with self.assertRaises(ValueError):
            classify_rhythm(70, 600, 20)

    def test_classify_rhythm_invalid_pulse(self):
        """Test classify_rhythm with invalid pulse amplitude."""
        with self.assertRaises(ValueError):
            classify_rhythm(70, 50, -1)

if __name__ == "__main__":
    unittest.main()
