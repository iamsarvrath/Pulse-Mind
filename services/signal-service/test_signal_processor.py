"""Unit tests for PPG signal processing module.

Tests bandpass filtering, peak detection, and feature extraction.
"""
import unittest

import numpy as np
from signal_processor import (
    bandpass_filter,
    detect_peaks,
    extract_features,
    process_ppg_signal
)


class TestBandpassFilter(unittest.TestCase):
    """Test bandpass filtering functionality."""
    
    def test_filter_basic(self):
        """Test basic bandpass filter operation."""
        # Create a simple signal
        sampling_rate = 100
        duration = 5
        t = np.linspace(0, duration, sampling_rate * duration)
        
        # Signal with 1 Hz component (60 BPM)
        signal_data = np.sin(2 * np.pi * 1.0 * t)
        
        # Apply filter
        filtered = bandpass_filter(signal_data, sampling_rate)
        
        # Check output shape matches input
        self.assertEqual(len(filtered), len(signal_data))
        
        # Check output is not all zeros
        self.assertGreater(np.std(filtered), 0)
    
    def test_filter_invalid_sampling_rate(self):
        """Test filter with invalid sampling rate."""
        signal_data = np.array([1, 2, 3, 4, 5])
        
        with self.assertRaises(ValueError):
            bandpass_filter(signal_data, sampling_rate=0)
        
        with self.assertRaises(ValueError):
            bandpass_filter(signal_data, sampling_rate=-10)
    
    def test_filter_high_cutoff_too_high(self):
        """Test filter with high cutoff above Nyquist frequency."""
        signal_data = np.array([1, 2, 3, 4, 5])
        sampling_rate = 10  # Nyquist = 5 Hz
        
        with self.assertRaises(ValueError):
            bandpass_filter(signal_data, sampling_rate, lowcut=0.5, highcut=6)
    
    def test_filter_invalid_cutoffs(self):
        """Test filter with invalid cutoff frequencies."""
        signal_data = np.array([1, 2, 3, 4, 5])
        sampling_rate = 100
        
        # Low cutoff >= high cutoff
        with self.assertRaises(ValueError):
            bandpass_filter(signal_data, sampling_rate, lowcut=4, highcut=2)
        
        # Negative low cutoff
        with self.assertRaises(ValueError):
            bandpass_filter(signal_data, sampling_rate, lowcut=-1, highcut=4)


class TestPeakDetection(unittest.TestCase):
    """Test peak detection functionality."""
    
    def test_detect_peaks_synthetic_signal(self):
        """Test peak detection on synthetic PPG-like signal."""
        # Create synthetic signal with known peaks
        sampling_rate = 100
        duration = 10
        t = np.linspace(0, duration, sampling_rate * duration)
        
        # Simulate 1 Hz signal (60 BPM)
        signal_data = np.sin(2 * np.pi * 1.0 * t) + 0.1 * np.random.randn(len(t))
        
        peaks, properties = detect_peaks(signal_data, sampling_rate)
        
        # Should detect approximately 10 peaks (1 Hz * 10 seconds)
        self.assertGreater(len(peaks), 5)
        self.assertLess(len(peaks), 15)
        
        # Peaks should be numpy array
        self.assertIsInstance(peaks, np.ndarray)
    
    def test_detect_peaks_too_short(self):
        """Test peak detection with signal too short."""
        signal_data = np.array([1, 2, 3])
        
        with self.assertRaises(ValueError):
            detect_peaks(signal_data, sampling_rate=100)
    
    def test_detect_peaks_invalid_min_distance(self):
        """Test peak detection with invalid min_distance."""
        signal_data = np.random.randn(1000)
        
        with self.assertRaises(ValueError):
            detect_peaks(signal_data, sampling_rate=100, min_distance_sec=-1)
        
        with self.assertRaises(ValueError):
            detect_peaks(signal_data, sampling_rate=100, min_distance_sec=0)


class TestFeatureExtraction(unittest.TestCase):
    """Test feature extraction functionality."""
    
    def test_extract_features_basic(self):
        """Test basic feature extraction."""
        # Create synthetic signal
        sampling_rate = 100
        duration = 10
        t = np.linspace(0, duration, sampling_rate * duration)
        signal_data = np.sin(2 * np.pi * 1.0 * t)
        
        # Detect peaks
        peaks, _ = detect_peaks(signal_data, sampling_rate)
        
        # Extract features
        features = extract_features(signal_data, peaks, sampling_rate)
        
        # Check all expected features are present
        self.assertIn('heart_rate_bpm', features)
        self.assertIn('hrv_sdnn_ms', features)
        self.assertIn('pulse_amplitude', features)
        self.assertIn('num_peaks', features)
        
        # Check heart rate is reasonable (should be ~60 BPM for 1 Hz signal)
        self.assertGreater(features['heart_rate_bpm'], 50)
        self.assertLess(features['heart_rate_bpm'], 70)
        
        # Check HRV is non-negative
        self.assertGreaterEqual(features['hrv_sdnn_ms'], 0)
        
        # Check pulse amplitude is positive
        self.assertGreater(features['pulse_amplitude'], 0)
        
        # Check num_peaks matches
        self.assertEqual(features['num_peaks'], len(peaks))
    
    def test_extract_features_insufficient_peaks(self):
        """Test feature extraction with insufficient peaks."""
        signal_data = np.array([1, 2, 3, 4, 5])
        peaks = np.array([2])  # Only 1 peak
        
        with self.assertRaises(ValueError):
            extract_features(signal_data, peaks, sampling_rate=100)
    
    def test_extract_features_known_hr(self):
        """Test feature extraction with known heart rate."""
        # Create signal with exactly 72 BPM (1.2 Hz)
        sampling_rate = 100
        duration = 10
        t = np.linspace(0, duration, sampling_rate * duration)
        signal_data = np.sin(2 * np.pi * 1.2 * t)
        
        peaks, _ = detect_peaks(signal_data, sampling_rate)
        features = extract_features(signal_data, peaks, sampling_rate)
        
        # Heart rate should be close to 72 BPM
        self.assertAlmostEqual(features['heart_rate_bpm'], 72, delta=5)


class TestProcessPPGSignal(unittest.TestCase):
    """Test main signal processing pipeline."""
    
    def test_process_valid_signal(self):
        """Test processing a valid PPG signal."""
        # Create synthetic PPG signal
        sampling_rate = 100
        duration = 10
        t = np.linspace(0, duration, sampling_rate * duration)
        signal_array = list(np.sin(2 * np.pi * 1.0 * t) + 0.1 * np.random.randn(len(t)))
        
        result = process_ppg_signal(signal_array, sampling_rate)
        
        # Check success
        self.assertTrue(result['success'])
        
        # Check features are present
        self.assertIn('features', result)
        self.assertIn('metadata', result)
        
        features = result['features']
        self.assertIn('heart_rate_bpm', features)
        self.assertIn('hrv_sdnn_ms', features)
        self.assertIn('pulse_amplitude', features)
        self.assertIn('num_peaks', features)
        
        # Check metadata
        metadata = result['metadata']
        self.assertEqual(metadata['signal_length'], len(signal_array))
        self.assertEqual(metadata['sampling_rate'], sampling_rate)
    
    def test_process_empty_signal(self):
        """Test processing empty signal."""
        with self.assertRaises(ValueError) as context:
            process_ppg_signal([], sampling_rate=100)
        
        self.assertIn("empty", str(context.exception).lower())
    
    def test_process_signal_too_short(self):
        """Test processing signal that's too short."""
        signal_array = [1, 2, 3, 4, 5]
        
        with self.assertRaises(ValueError) as context:
            process_ppg_signal(signal_array, sampling_rate=100)
        
        self.assertIn("too short", str(context.exception).lower())
    
    def test_process_invalid_sampling_rate(self):
        """Test processing with invalid sampling rate."""
        signal_array = list(range(200))
        
        with self.assertRaises(ValueError):
            process_ppg_signal(signal_array, sampling_rate=0)
        
        with self.assertRaises(ValueError):
            process_ppg_signal(signal_array, sampling_rate=-10)
        
        with self.assertRaises(ValueError):
            process_ppg_signal(signal_array, sampling_rate=5)  # Too low
    
    def test_process_signal_with_nan(self):
        """Test processing signal with NaN values."""
        signal_array = [1, 2, float('nan'), 4, 5] * 20
        
        with self.assertRaises(ValueError) as context:
            process_ppg_signal(signal_array, sampling_rate=100)
        
        self.assertIn("nan", str(context.exception).lower())
    
    def test_process_signal_with_inf(self):
        """Test processing signal with infinite values."""
        signal_array = [1, 2, float('inf'), 4, 5] * 20
        
        with self.assertRaises(ValueError) as context:
            process_ppg_signal(signal_array, sampling_rate=100)
        
        self.assertIn("infinite", str(context.exception).lower())
    
    def test_process_non_numeric_signal(self):
        """Test processing signal with non-numeric values."""
        signal_array = [1, 2, "three", 4, 5] * 20
        
        with self.assertRaises(ValueError) as context:
            process_ppg_signal(signal_array, sampling_rate=100)
        
        self.assertIn("numeric", str(context.exception).lower())
    
    def test_process_without_filter(self):
        """Test processing without applying bandpass filter."""
        sampling_rate = 100
        duration = 10
        t = np.linspace(0, duration, sampling_rate * duration)
        signal_array = list(np.sin(2 * np.pi * 1.0 * t))
        
        result = process_ppg_signal(signal_array, sampling_rate, apply_filter=False)
        
        self.assertTrue(result['success'])
        self.assertFalse(result['metadata']['filter_applied'])


if __name__ == '__main__':
    unittest.main()
