# PulseMind Test Scenarios

## Overview

These scenarios validate the end-to-end functionality of the PulseMind system, ensuring safety and reliability.

## Scenarios

### 1. Normal Rhythm + Stable HSI

- **Input**:
  - Signal: Synthetic Normal Sinus Rhythm (60-100 BPM)
  - HSI: Stable values (high oxygenation, low stress)
- **Expected Output**:
  - AI: "normal_sinus" (High Confidence)
  - Control: "monitoring" status, No alerts
- **Safety**: System remains in monitoring mode.

### 2. Tachycardia + Declining HSI

- **Input**:
  - Signal: Synthetic Tachycardia (>100 BPM)
  - HSI: Declining oxygenation
- **Expected Output**:
  - AI: "tachycardia" (High/Medium Confidence)
  - Control: "alert" status (Pacing Required?)
- **Safety**: Alarm triggered, latency < 200ms.

### 3. Bradycardia + Stable HSI

- **Input**:
  - Signal: Synthetic Bradycardia (<60 BPM)
  - HSI: Stable
- **Expected Output**:
  - AI: "bradycardia" or "arrhythmia"
  - Control: "alert" status
- **Safety**: Low heart rate detected reliably.

### 4. Noisy / Corrupted Signal

- **Input**:
  - Signal: High amplitude random noise
  - HSI: N/A
- **Expected Output**:
  - AI: "artifact" or Low Confidence prediction
  - Control: "warning" status (Signal check required)
- **Safety**: No false pacing triggered.

### 5. AI Service Unavailable (Fallback)

- **Input**:
  - Signal: Normal Rhythm
  - Action: Stop `ai-inference` container
- **Expected Output**:
  - System: Graceful degradation.
  - Control: Receives "unknown" or manual fallback status.
- **Safety**: System does not crash; fails safe.

## Execution / Data Flow

Logic for validation script:

1.  **Generate** synthetic raw signal (10s window).
2.  **Send** to `signal-service` (/process).
3.  **Receive** features (HR, HRV, Amp).
4.  **Send** features to `ai-inference` (/predict).
5.  **Receive** classification.
6.  **Send** classification + HSI to `control-engine` (/decision).
7.  **Log** all inputs/outputs.
