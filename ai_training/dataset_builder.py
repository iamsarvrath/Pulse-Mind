import os

import numpy as np
import pandas as pd
import wfdb
from feature_extraction import extract_features

# Configuration
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "mit_bih")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mapping MIT-BIH annotations to our classes
# N: Normal
# S: Supraventricular premature beat (often Tachycardia context)
# V: Premature ventricular contraction (Arrhythmia)
# F: Fusion of ventricular and normal beat (Arrhythmia)
# Q: Unclassifiable beat (Unknown/Noise)
# A: Atrial premature beat (Arrhythmia)
# L: Left bundle branch block beat (Arrhythmia)
# R: Right bundle branch block beat (Arrhythmia)

# Simplified mapping for PulseMind demo purposes
# In a real clinical setting, this would be much more complex.
LABEL_MAP = {
    "N": "normal_sinus",
    "L": "arrhythmia",
    "R": "arrhythmia",
    "V": "arrhythmia",
    "A": "tachycardia",  # Simplification
    "/": "arrhythmia",
    "f": "arrhythmia",
    "F": "arrhythmia",
}


def download_mit_bih():
    """Download MIT-BIH dataset if not present.

    Using a small subset of records for demonstration speed.
    """
    records = ["100", "101", "102", "103", "200", "201"]
    print(f"Checking for MIT-BIH data in {DATA_DIR}...")

    try:
        # Check if first record exists
        if not os.path.exists(os.path.join(DATA_DIR, "100.dat")):
            print("Downloading MIT-BIH Arrhythmia Database subset...")
            wfdb.dl_database("mitdb", DATA_DIR, records=records)
            print("Download complete.")
        else:
            print("Data already exists.")
    except Exception as e:
        print(f"Warning: Failed to download MIT-BIH data: {e}")
        print("Will proceed to use SYNTHETIC data for demonstration.")
        return False
    return True


def generate_synthetic_data(num_samples=500):
    """Generate synthetic data if real data download fails or for quick testing."""
    print("Generating synthetic dataset...")
    data = []

    # Normal Sinus
    for _ in range(num_samples // 3):
        data.append(
            {
                "heart_rate_bpm": np.random.normal(70, 5),
                "hrv_sdnn_ms": np.random.normal(50, 10),
                "pulse_amplitude": np.random.normal(15, 2),
                "label": "normal_sinus",
            }
        )

    # Tachycardia
    for _ in range(num_samples // 3):
        data.append(
            {
                "heart_rate_bpm": np.random.normal(110, 10),
                "hrv_sdnn_ms": np.random.normal(30, 8),
                "pulse_amplitude": np.random.normal(12, 3),
                "label": "tachycardia",
            }
        )

    # Arrhythmia (High HRV, Irregular)
    for _ in range(num_samples // 3):
        data.append(
            {
                "heart_rate_bpm": np.random.normal(80, 20),
                "hrv_sdnn_ms": np.random.normal(100, 30),
                "pulse_amplitude": np.random.normal(10, 5),
                "label": "arrhythmia",
            }
        )

    return pd.DataFrame(data)


def process_record(record_name):
    """Process a single MIT-BIH record."""
    try:
        record = wfdb.rdrecord(os.path.join(DATA_DIR, record_name))
        annotation = wfdb.rdann(os.path.join(DATA_DIR, record_name), "atr")

        # Signal (usually lead II is index 0)
        signal = record.p_signal[:, 0]
        fs = record.fs

        extracted_data = []

        # Segment signal around annotations
        # We'll take windows of 10 seconds (approx 10 beats) to calculate HR/HRV
        window_size_sec = 10
        window_samples = int(window_size_sec * fs)
        step_samples = int(window_samples / 2)  # 50% overlap

        for i in range(0, len(signal) - window_samples, step_samples):
            segment = signal[i : i + window_samples]

            # Find annotations within this window
            start_sample = i
            end_sample = i + window_samples

            # Get indices of annotations in this window
            ann_indices = [
                idx
                for idx, samp in enumerate(annotation.sample)
                if start_sample <= samp < end_sample
            ]

            if not ann_indices:
                continue

            # Determine majority label
            labels_in_window = [annotation.symbol[idx] for idx in ann_indices]

            # Filter for labels we care about
            mapped_labels = [
                LABEL_MAP.get(label_sym)
                for label_sym in labels_in_window
                if label_sym in LABEL_MAP
            ]

            if not mapped_labels:
                continue

            # Majority vote
            majority_label = max(set(mapped_labels), key=mapped_labels.count)

            # Extract features
            features = extract_features(segment, sampling_rate=fs)

            # Build row
            row = features.copy()
            row["label"] = majority_label
            extracted_data.append(row)

        return extracted_data

    except Exception as e:
        print(f"Error processing record {record_name}: {e}")
        return []


def build_dataset():
    """Main function to build the dataset."""
    # Try to download real data
    has_real_data = download_mit_bih()

    if not has_real_data:
        df = generate_synthetic_data()
    else:
        print("Processing real MIT-BIH records...")
        all_data = []
        records = ["100", "101", "102", "103", "200", "201"]

        for rec in records:
            print(f"Processing {rec}...")
            data = process_record(rec)
            all_data.extend(data)

    # Augment with synthetic data if classes are scarce
    print("Checking class distribution...")
    counts = pd.DataFrame(all_data)["label"].value_counts() if all_data else pd.Series()
    print(counts)

    needed_augmentation = False
    synthetic_samples_needed = {}

    required_classes = ["normal_sinus", "tachycardia", "arrhythmia"]
    min_samples = 50

    for cls in required_classes:
        count = counts.get(cls, 0)
        if count < min_samples:
            needed = min_samples - count
            synthetic_samples_needed[cls] = needed
            needed_augmentation = True
            print(
                f"Class '{cls}' has only {count} samples. "
                f"Augmenting with {needed} synthetic samples."
            )

    if needed_augmentation:
        aug_data = []
        for cls, count in synthetic_samples_needed.items():
            # Parameters based on generate_synthetic_data logic
            if cls == "normal_sinus":
                params = (70, 5, 50, 10, 15, 2)
            elif cls == "tachycardia":
                params = (110, 10, 30, 8, 12, 3)
            elif cls == "arrhythmia":
                params = (80, 20, 100, 30, 10, 5)
            else:
                continue

            hr_mean, hr_std, hrv_mean, hrv_std, amp_mean, amp_std = params

            for _ in range(count):
                aug_data.append(
                    {
                        "heart_rate_bpm": np.max(
                            [0, np.random.normal(hr_mean, hr_std)]
                        ),
                        "hrv_sdnn_ms": np.max([0, np.random.normal(hrv_mean, hrv_std)]),
                        "pulse_amplitude": np.max(
                            [0, np.random.normal(amp_mean, amp_std)]
                        ),
                        "label": cls,
                    }
                )

        all_data.extend(aug_data)
        df = pd.DataFrame(all_data)
    else:
        df = pd.DataFrame(all_data)

    # Clean dataset
    print(f"Raw dataset shape: {df.shape}")
    df = df.dropna()
    print(f"Cleaned dataset shape: {df.shape}")

    # Save
    output_path = os.path.join(OUTPUT_DIR, "pulsemind_dataset.csv")
    df.to_csv(output_path, index=False)
    print(f"Dataset saved to {output_path}")

    return df


if __name__ == "__main__":
    build_dataset()
