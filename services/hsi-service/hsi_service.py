import os
import sys
import time
from datetime import datetime

from flask import Flask, jsonify, request

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hsi_computer import process_hsi_computation  # noqa: E402
from shared.logger import setup_logger  # noqa: E402
from shared.shutdown import register_shutdown_handler  # noqa: E402

# Initialize logger
logger = setup_logger("hsi-service", level="INFO")

app = Flask(__name__)


@app.route("/health")
def health_check():
    """Health check endpoint for container orchestration."""
    logger.info("Health check requested")
    return (
        jsonify(
            {
                "status": "healthy",
                "service": "hsi-service",
                "version": "1.0.0",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ),
        200,
    )


@app.route("/")
def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return jsonify(
        {
            "service": "hsi-service",
            "version": "1.0.0",
            "status": "running",
            "description": "Hemodynamic Surrogate Index (HSI) Computation Service",
            "endpoints": {
                "/health": "Health check",
                "/compute-hsi": "POST - Compute HSI from PPG features",
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.route("/compute-hsi", methods=["POST"])
def compute_hsi():
    """Compute Hemodynamic Surrogate Index from PPG-derived features.

    Expected JSON payload:
    {
        "features": {
            "heart_rate_bpm": 72.5,
            "hrv_sdnn_ms": 45.3,
            "pulse_amplitude": 15.2
        },
        "previous_measurement": {  // Optional
            "hsi_score": 65.4,
            "timestamp": "2026-01-01T14:30:00.000000Z"
        },
        "timestamp": "2026-01-01T14:35:00.000000Z"  // Optional
    }

    Returns:
    {
        "success": true,
        "hsi": {
            "hsi_score": 67.82,
            "hr_contribution": 0.3245,
            "hrv_contribution": 0.3612,
            "pulse_contribution": 0.2156,
            ...
        },
        "interpretation": "good",
        "trend": {
            "delta_hsi": 2.42,
            "delta_per_minute": 0.48,
            "trend_direction": "improving",
            "is_significant": false,
            ...
        },
        "timestamp": "...",
        "input_features": {...}
    }
    """
    start_time = time.time()
    logger.info("HSI computation request received")

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

    # Extract optional fields
    previous_measurement = data.get("previous_measurement")
    timestamp = data.get("timestamp")

    # Validate previous_measurement if provided
    if previous_measurement is not None:
        if not isinstance(previous_measurement, dict):
            logger.warning(
                f"Invalid previous_measurement type: {type(previous_measurement)}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Field 'previous_measurement' must be an object",
                    }
                ),
                400,
            )

        # Validate required fields in previous_measurement
        if (
            "hsi_score" not in previous_measurement
            or "timestamp" not in previous_measurement
        ):
            logger.warning("previous_measurement missing required fields")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": (
                            "previous_measurement must contain "
                            "'hsi_score' and 'timestamp'"
                        ),
                    }
                ),
                400,
            )

    # Process HSI computation
    try:
        result = process_hsi_computation(features, previous_measurement, timestamp)

        # Add processing time
        processing_time_ms = (time.time() - start_time) * 1000
        result["processing_time_ms"] = round(processing_time_ms, 2)
        
        # Add timestamp (required by schema)
        result["timestamp"] = datetime.utcnow().isoformat() + "Z"

        logger.info(f"HSI computed successfully in {processing_time_ms:.2f}ms")
        return jsonify(result), 200

    except ValueError as e:
        # Validation or processing errors
        logger.warning(f"HSI computation validation error: {e}")
        return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error during HSI computation: {e}", exc_info=True)
        return (
            jsonify(
                {"success": False, "error": f"Internal processing error: {str(e)}"}
            ),
            500,
        )


if __name__ == "__main__":
    register_shutdown_handler(logger)
    logger.info("Starting hsi-service on port 8002")
    app.run(host="0.0.0.0", port=8002)  # nosec B104
