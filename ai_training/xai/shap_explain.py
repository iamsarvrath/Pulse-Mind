import os
import numpy as np
import joblib
import shap

_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    os.pardir,
    os.pardir,
    "services",
    "ai-inference",
    "models",
    "pulsemind_rf_model.pkl",
)

_model = joblib.load(os.path.normpath(_MODEL_PATH))
_explainer = shap.TreeExplainer(_model)

FEATURE_NAMES = [
    "heart_rate_bpm",
    "hrv_sdnn_ms",
    "pulse_amplitude",
]


def explain_prediction(input_features: dict) -> dict:
    """Return per-feature SHAP values for a single prediction input.

    Parameters
    ----------
    input_features : dict
        Mapping of feature name to numeric value, e.g.
        ``{"heart_rate_bpm": 78.0, "hrv_sdnn_ms": 42.5, "pulse_amplitude": 1.2}``

    Returns
    -------
    dict
        JSON-serializable dict mapping each feature name to its SHAP
        contribution (positive-class, index 1) as a Python float.
    """
    row = np.array([[input_features[f] for f in FEATURE_NAMES]])

    shap_values = _explainer.shap_values(row)

    # Binary classification: shap_values is a list of two arrays.
    if isinstance(shap_values, list):
        raw = shap_values[1]
    else:
        raw = shap_values

    arr = np.asarray(raw)
    sample = arr[0]
    flat = sample.flatten()

    return {FEATURE_NAMES[i]: float(flat[i]) for i in range(len(FEATURE_NAMES))}
