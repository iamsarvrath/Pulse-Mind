# PulseMind AI Training Workspace

This directory contains the machine learning pipeline for the PulseMind system.
It is completely decoupled from the runtime microservices.

## Workflow

1.  **Ingestion**: `dataset_builder.py` loads ECG/PPG data from MIT-BIH dataset. It augments scarce classes with synthetic data if needed.
2.  **Feature Extraction**: `feature_extraction.py` converts raw signals to features (HR, HRV, Amplitude).
3.  **Training**: `train_model.py` trains a Random Forest Classifier.
4.  **Evaluation**: `evaluate_model.py` generates classification reports and confusion matrices.
5.  **Export**: `export_model.py` moves the trained model to the inference service.

## How to Run

```bash
# Install dependencies
pip install scikit-learn numpy pandas joblib wfdb matplotlib seaborn

# Run the full pipeline
# 1. Build dataset (automatically downloads MIT-BIH or generates synthetic)
# 2. Train model
python train_model.py

# 3. Evaluate
python evaluate_model.py

# 4. Export to Service
python export_model.py
```

## Integration

The trained model `pulsemind_rf_model.pkl` is exported to `services/ai-inference/models/`.
The service loads this model on startup. If the model is missing, a fallback rule-based classifier is used.

**Strict Separation:**

- Training code (`ai_training/`) is NEVER imported by services.
- Only the serialized model (`.pkl`) crosses the boundary.
- `services/ai-inference/rhythm_classifier.py` handles model loading and inference.
