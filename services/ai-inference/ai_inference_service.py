import os
import sys
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rhythm_classifier import (  # noqa: E402
    classify_rhythm,
    get_model_status,
    load_model_async,
)
from shared.logger import setup_logger  # noqa: E402
from shared.shutdown import register_shutdown_handler  # noqa: E402

# Initialize logger
logger = setup_logger("ai-inference", level="INFO")

app = Flask(__name__)

# Start async model loading in background thread
# Design Decision: Non-blocking startup - service can handle health checks
# immediately while model loads. This prevents container orchestration from
# thinking the service is unhealthy during model loading.
logger.info("Initiating async model loading")
model_thread = threading.Thread(target=load_model_async, daemon=True)
model_thread.start()


@app.route("/health")
def health_check():
    """Health check endpoint for container orchestration.

    Design Decision: Returns healthy even if model isn't loaded yet.
    This allows the service to start and be discovered while model loads.
    Clients should check /model-status if they need to know model state.
    """
    logger.info("Health check requested")

    # Get model status for additional info
    model_status = get_model_status()

    return (
        jsonify(
            {
                "status": "healthy",
                "service": "ai-inference",
                "version": "1.0.0",
                "model_loaded": model_status["model_loaded"],
                "warmup_complete": model_status["warmup_complete"],
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ),
        200,
    )


@app.route("/")
def root():
    """Root endpoint with service information."""
    logger.info("Root endpoint accessed")

    model_status = get_model_status()

    return jsonify(
        {
            "service": "ai-inference",
            "version": "1.0.0",
            "status": "running",
            "description": "Rhythm Classification Inference Engine",
            "endpoints": {
                "/health": "Health check",
                "/model-status": "GET - Model loading status",
                "/predict": "POST - Classify rhythm from features",
            },
            "model_loaded": model_status["model_loaded"],
            "supported_classes": model_status["supported_classes"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.route("/model-status")
def model_status():
    """Get detailed model status.

    Design Decision: Separate endpoint for model status so clients can
    check if model is ready before sending prediction requests.
    """
    logger.info("Model status requested")

    status = get_model_status()

    return (
        jsonify(
            {
                "success": True,
                "status": status,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ),
        200,
    )


@app.route("/predict", methods=["POST"])
def predict():
    """Predict rhythm class from feature vector.

    Expected JSON payload:
    {
        "features": {
            "heart_rate_bpm": 72.5,
            "hrv_sdnn_ms": 45.3,
            "pulse_amplitude": 15.2
        }
    }

    Returns:
    {
        "success": true,
        "prediction": {
            "rhythm_class": "normal_sinus",
            "confidence": 0.8542,
            "confidence_level": "high",
            "probability_distribution": {
                "normal_sinus": 0.8542,
                "tachycardia": 0.0821,
                ...
            },
            "inference_time_ms": 2.34
        },
        "timestamp": "...",
        "processing_time_ms": 3.12
    }

    Design Decision: Accepts same features as signal-service outputs,
    making it easy to chain services together.
    """
    start_time = time.time()
    logger.info("Rhythm prediction request received")

    # Validate request has JSON content
    if not request.is_json:
        logger.warning("Request missing JSON content-type")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Request must have Content-Type: application/json",
                }
            ),
            400,
        )

    try:
        data = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return jsonify({"success": False, "error": f"Invalid JSON: {str(e)}"}), 400

    # Validate required fields
    if "features" not in data:
        logger.warning("Missing 'features' field in request")
        return (
            jsonify({"success": False, "error": "Missing required field: 'features'"}),
            400,
        )

    features = data["features"]

    # Validate features is a dictionary
    if not isinstance(features, dict):
        logger.warning(f"Invalid features type: {type(features)}")
        return (
            jsonify({"success": False, "error": "Field 'features' must be an object"}),
            400,
        )

    # Extract required features
    required_fields = ["heart_rate_bpm", "hrv_sdnn_ms", "pulse_amplitude"]
    for field in required_fields:
        if field not in features:
            logger.warning(f"Missing feature: {field}")
            return (
                jsonify(
                    {"success": False, "error": f"Missing required feature: '{field}'"}
                ),
                400,
            )

    # Extract and validate feature values
    try:
        hr = float(features["heart_rate_bpm"])
        hrv = float(features["hrv_sdnn_ms"])
        pulse = float(features["pulse_amplitude"])
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid feature value: {e}")
        return (
            jsonify({"success": False, "error": f"Invalid feature value: {str(e)}"}),
            400,
        )

    # Perform classification
    try:
        prediction = classify_rhythm(hr, hrv, pulse)

        # Add processing time
        processing_time_ms = (time.time() - start_time) * 1000

        result = {
            "success": True,
            "prediction": prediction,
            "input_features": {
                "heart_rate_bpm": hr,
                "hrv_sdnn_ms": hrv,
                "pulse_amplitude": pulse,
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "processing_time_ms": round(processing_time_ms, 2),
        }

        logger.info(f"Prediction completed in {processing_time_ms:.2f}ms")
        return jsonify(result), 200

    except RuntimeError as e:
        # Model not loaded
        logger.error(f"Model not available: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": (
                        "Model not loaded - please wait for model initialization "
                        "or check /model-status"
                    ),
                }
            ),
            503,
        )

    except ValueError as e:
        # Validation error
        logger.warning(f"Feature validation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error during prediction: {e}", exc_info=True)
        return (
            jsonify(
                {"success": False, "error": f"Internal processing error: {str(e)}"}
            ),
            500,
        )


if __name__ == "__main__":
    register_shutdown_handler(logger)
    logger.info("Starting ai-inference on port 8003")

    # Wait a moment for model loading to start
    # Design Decision: Give model loading thread a head start before
    # Flask starts accepting requests. Not critical, but improves UX.
    time.sleep(0.5)

    app.run(host="0.0.0.0", port=8003)  # nosec B104
