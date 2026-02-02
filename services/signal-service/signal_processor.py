"""
PPG Signal Processing Module

Provides bandpass filtering, peak detection, and feature extraction
for photoplethysmography (PPG) signals.
"""

import numpy as np
from scipy import signal
from typing import Dict, List, Tuple, Optional
import sys
import os

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logger import setup_logger

logger = setup_logger("signal-processor", level="INFO")


def bandpass_filter(
    signal_data: np.ndarray,
    sampling_rate: float,
    lowcut: float = 0.5,
    highcut: float = 4.0,
    order: int = 4,
) -> np.ndarray:
    """
    Apply Butterworth bandpass filter to PPG signal.

    Typical PPG signals have frequency components between 0.5-4 Hz,
    corresponding to heart rates of 30-240 BPM.

    Args:
        signal_data: Input signal array
        sampling_rate: Sampling rate in Hz
        lowcut: Low cutoff frequency in Hz (default: 0.5 Hz = 30 BPM)
        highcut: High cutoff frequency in Hz (default: 4 Hz = 240 BPM)
        order: Filter order (default: 4)

    Returns:
        Filtered signal array

    Raises:
        ValueError: If sampling rate is too low or cutoff frequencies are invalid
    """
    logger.info(
        f"Applying bandpass filter: {lowcut}-{highcut} Hz, SR={sampling_rate} Hz"
    )

    # Validate inputs
    if sampling_rate <= 0:
        raise ValueError(f"Sampling rate must be positive, got {sampling_rate}")

    nyquist = sampling_rate / 2.0

    if highcut >= nyquist:
        raise ValueError(
            f"High cutoff ({highcut} Hz) must be less than Nyquist frequency ({nyquist} Hz)"
        )

    if lowcut <= 0 or lowcut >= highcut:
        raise ValueError(
            f"Invalid cutoff frequencies: lowcut={lowcut}, highcut={highcut}"
        )

    # Normalize frequencies
    low = lowcut / nyquist
    high = highcut / nyquist

    # Design Butterworth bandpass filter
    b, a = signal.butter(order, [low, high], btype="band")

    # Apply filter (using filtfilt for zero-phase filtering)
    filtered = signal.filtfilt(b, a, signal_data)

    logger.info(f"Bandpass filter applied successfully")
    return filtered


def detect_peaks(
    signal_data: np.ndarray,
    sampling_rate: float,
    min_distance_sec: float = 0.4,
    prominence_factor: float = 0.3,
) -> Tuple[np.ndarray, Dict]:
    """
    Detect peaks in PPG signal using adaptive thresholding.

    Args:
        signal_data: Filtered signal array
        sampling_rate: Sampling rate in Hz
        min_distance_sec: Minimum time between peaks in seconds (default: 0.4s = 150 BPM max)
        prominence_factor: Prominence threshold as fraction of signal std (default: 0.3)

    Returns:
        Tuple of (peak_indices, properties_dict)
        - peak_indices: Array of peak locations
        - properties_dict: Dictionary with peak properties

    Raises:
        ValueError: If signal is too short or parameters are invalid
    """
    logger.info(f"Detecting peaks with min_distance={min_distance_sec}s")

    if len(signal_data) < 10:
        raise ValueError(
            f"Signal too short for peak detection: {len(signal_data)} samples"
        )

    if min_distance_sec <= 0:
        raise ValueError(f"min_distance_sec must be positive, got {min_distance_sec}")

    # Calculate minimum distance in samples
    min_distance_samples = int(min_distance_sec * sampling_rate)

    # Calculate adaptive prominence threshold
    signal_std = np.std(signal_data)
    prominence_threshold = prominence_factor * signal_std

    # Find peaks
    peaks, properties = signal.find_peaks(
        signal_data, distance=min_distance_samples, prominence=prominence_threshold
    )

    logger.info(f"Detected {len(peaks)} peaks")
    return peaks, properties


def extract_features(
    signal_data: np.ndarray, peaks: np.ndarray, sampling_rate: float
) -> Dict[str, float]:
    """
    Extract physiological features from PPG signal and detected peaks.

    Features extracted:
    - Heart Rate (HR): Average heart rate in BPM
    - HRV (SDNN): Standard deviation of NN intervals in ms
    - Pulse Amplitude: Mean peak-to-trough amplitude

    Args:
        signal_data: Original or filtered signal array
        peaks: Array of peak indices
        sampling_rate: Sampling rate in Hz

    Returns:
        Dictionary with extracted features

    Raises:
        ValueError: If insufficient peaks for feature extraction
    """
    logger.info(f"Extracting features from {len(peaks)} peaks")

    if len(peaks) < 2:
        raise ValueError(
            f"Need at least 2 peaks for feature extraction, got {len(peaks)}"
        )

    # Calculate inter-peak intervals (in samples)
    peak_intervals = np.diff(peaks)

    # Convert to time (seconds)
    peak_intervals_sec = peak_intervals / sampling_rate

    # Heart Rate (BPM)
    mean_interval_sec = np.mean(peak_intervals_sec)
    heart_rate_bpm = 60.0 / mean_interval_sec

    # HRV - SDNN (Standard Deviation of NN intervals in milliseconds)
    peak_intervals_ms = peak_intervals_sec * 1000.0
    hrv_sdnn_ms = np.std(peak_intervals_ms, ddof=1)  # Sample standard deviation

    # Pulse Amplitude - Mean peak-to-trough amplitude
    peak_amplitudes = []
    for i in range(len(peaks) - 1):
        # Get signal segment between consecutive peaks
        start_idx = peaks[i]
        end_idx = peaks[i + 1]
        segment = signal_data[start_idx:end_idx]

        # Peak-to-trough amplitude
        peak_val = signal_data[peaks[i]]
        trough_val = np.min(segment)
        amplitude = peak_val - trough_val
        peak_amplitudes.append(amplitude)

    mean_pulse_amplitude = np.mean(peak_amplitudes)

    features = {
        "heart_rate_bpm": float(heart_rate_bpm),
        "hrv_sdnn_ms": float(hrv_sdnn_ms),
        "pulse_amplitude": float(mean_pulse_amplitude),
        "num_peaks": int(len(peaks)),
    }

    logger.info(
        f"Features extracted: HR={heart_rate_bpm:.1f} BPM, HRV={hrv_sdnn_ms:.1f} ms"
    )
    return features


def process_ppg_signal(
    signal_array: List[float], sampling_rate: float, apply_filter: bool = True
) -> Dict:
    """
    Main pipeline for PPG signal processing.

    Steps:
    1. Convert to numpy array and validate
    2. Apply bandpass filter (optional)
    3. Detect peaks
    4. Extract features

    Args:
        signal_array: List of signal values
        sampling_rate: Sampling rate in Hz
        apply_filter: Whether to apply bandpass filter (default: True)

    Returns:
        Dictionary with success status, features, and metadata

    Raises:
        ValueError: If input validation fails
    """
    logger.info(
        f"Processing PPG signal: {len(signal_array)} samples at {sampling_rate} Hz"
    )

    # Validate inputs
    if not signal_array:
        raise ValueError("Signal array is empty")

    if len(signal_array) < 100:
        raise ValueError(
            f"Signal too short: {len(signal_array)} samples. Need at least 100 samples."
        )

    if sampling_rate <= 0:
        raise ValueError(f"Sampling rate must be positive, got {sampling_rate}")

    if sampling_rate < 10:
        raise ValueError(
            f"Sampling rate too low: {sampling_rate} Hz. Need at least 10 Hz."
        )

    # Convert to numpy array
    try:
        signal_data = np.array(signal_array, dtype=np.float64)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Failed to convert signal to numeric array: {e}")

    # Check for invalid values
    if np.any(np.isnan(signal_data)):
        raise ValueError("Signal contains NaN values")

    if np.any(np.isinf(signal_data)):
        raise ValueError("Signal contains infinite values")

    # Apply bandpass filter
    if apply_filter:
        try:
            filtered_signal = bandpass_filter(signal_data, sampling_rate)
        except Exception as e:
            logger.error(f"Bandpass filter failed: {e}")
            raise ValueError(f"Bandpass filtering failed: {e}")
    else:
        filtered_signal = signal_data

    # Detect peaks
    try:
        peaks, peak_properties = detect_peaks(filtered_signal, sampling_rate)
    except Exception as e:
        logger.error(f"Peak detection failed: {e}")
        raise ValueError(f"Peak detection failed: {e}")

    # Extract features
    try:
        features = extract_features(filtered_signal, peaks, sampling_rate)
    except Exception as e:
        logger.error(f"Feature extraction failed: {e}")
        raise ValueError(f"Feature extraction failed: {e}")

    logger.info("PPG signal processing completed successfully")

    return {
        "success": True,
        "features": features,
        "metadata": {
            "signal_length": len(signal_array),
            "sampling_rate": sampling_rate,
            "filter_applied": apply_filter,
        },
    }
