"""
Feature Extraction for Training Pipeline.
MUST match logic in services/signal-service/signal_processor.py
"""
import numpy as np
from scipy.signal import find_peaks

def extract_features(signal, sampling_rate=100.0):
    """
    Extract features from a PPG signal segment.
    
    Args:
        signal (np.array): Raw PPG signal segment
        sampling_rate (float): Sampling rate in Hz
        
    Returns:
        dict: feature dictionary
    """
    # 1. Heart Rate (BPM)
    # Simple peak detection
    peaks, _ = find_peaks(signal, distance=sampling_rate*0.4) # Min 0.4s between beats (max 150 BPM)
    
    if len(peaks) < 2:
        # Not enough peaks to compute HR
        return {
            "heart_rate_bpm": 0.0,
            "hrv_sdnn_ms": 0.0,
            "pulse_amplitude": 0.0
        }
        
    # Calculate RR intervals in ms
    rr_intervals = np.diff(peaks) / sampling_rate * 1000
    
    # Calculate HR
    mean_rr = np.mean(rr_intervals)
    heart_rate_bpm = 60000 / mean_rr if mean_rr > 0 else 0
    
    # 2. HRV (SDNN)
    # Standard deviation of NN intervals
    hrv_sdnn_ms = np.std(rr_intervals)
    
    # 3. Pulse Amplitude
    # Mean peak-to-trough amplitude
    # Simple approximation: standard deviation of signal * 2 approx peak-to-peak
    pulse_amplitude = np.std(signal) * 2
    
    return {
        "heart_rate_bpm": float(heart_rate_bpm),
        "hrv_sdnn_ms": float(hrv_sdnn_ms),
        "pulse_amplitude": float(pulse_amplitude)
    }
