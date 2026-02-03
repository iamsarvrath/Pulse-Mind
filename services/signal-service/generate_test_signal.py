# Generate realistic PPG test signal
import json

import numpy as np

# Parameters
sampling_rate = 100  # Hz
duration = 10  # seconds
heart_rate = 72  # BPM
frequency = heart_rate / 60.0  # Hz

# Time vector
t = np.linspace(0, duration, sampling_rate * duration)

# Generate PPG-like signal (sine wave with some noise)
signal = 100 + 20 * np.sin(2 * np.pi * frequency * t) + 2 * np.random.randn(len(t))

# Create JSON payload
payload = {
    "signal": signal.tolist(),
    "sampling_rate": sampling_rate
}

# Save to file
with open('test_ppg_signal.json', 'w') as f:
    json.dump(payload, f, indent=2)

print(f"Generated {len(signal)} samples at {sampling_rate} Hz")
print(f"Duration: {duration} seconds")
print(f"Expected HR: {heart_rate} BPM")
print("Saved to test_ppg_signal.json")
