import os
import sys
import time
from datetime import datetime

from flask import Flask, jsonify, request

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pacing_controller import process_pacing_decision  # noqa: E402
from shared.logger import setup_logger  # noqa: E402
from shared.shutdown import register_shutdown_handler  # noqa: E402

# Initialize logger
logger = setup_logger("control-engine", level="INFO")

app = Flask(__name__)


@app.route('/health')
def health_check():
    """Health check endpoint for container orchestration."""
    logger.info("Health check requested")
    return jsonify({
        "status": "healthy",
        "service": "control-engine",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }), 200


@app.route('/')
def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return jsonify(
        {
            "service": "control-engine",
            "version": "1.0.0",
            "status": "running",
            "description": "Adaptive Pacing Control Engine",
            "endpoints": {
                "/health": "Health check",
                "/compute-pacing": (
                    "POST - Compute pacing command from rhythm and HSI data"
                ),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.route('/compute-pacing', methods=['POST'])
def compute_pacing():
    """Compute pacing command from rhythm classification and HSI data.

    Expected JSON payload:
    {
        "rhythm_data": {
            "rhythm_class": "normal_sinus",
            "confidence": 0.85,
            ...
        },
        "hsi_data": {
            "hsi_score": 65.4,
            "trend": {
                "trend_direction": "stable",
                ...
            },
            "input_features": {
                "heart_rate_bpm": 72.0,
                ...
            }
        }
    }
    
    Returns:
    {
        "success": true,
        "pacing_command": {
            "pacing_enabled": true,
            "target_rate_bpm": 70.0,
            "pacing_amplitude_ma": 2.0,
            "pacing_mode": "moderate",
            "safety_state": "normal",
            "safety_checks": {...},
            "rationale": "..."
        },
        "input_summary": {...},
        "timestamp": "...",
        "processing_time_ms": 1.23
    }
    
    Medical Safety: This endpoint makes medical-grade decisions.
    All inputs are validated, all outputs are safe, never crashes.
    """
    start_time = time.time()
    logger.info("Pacing computation request received")
    
    # Validate request has JSON content
    if not request.is_json:
        logger.warning("Request missing JSON content-type")
        return jsonify({
            "success": False,
            "error": "Request must have Content-Type: application/json"
        }), 400
    
    try:
        data = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return jsonify({
            "success": False,
            "error": f"Invalid JSON: {str(e)}"
        }), 400
    
    # Validate required fields
    if 'rhythm_data' not in data:
        logger.warning("Missing 'rhythm_data' field in request")
        return jsonify({
            "success": False,
            "error": "Missing required field: 'rhythm_data'"
        }), 400
    
    if 'hsi_data' not in data:
        logger.warning("Missing 'hsi_data' field in request")
        return jsonify({
            "success": False,
            "error": "Missing required field: 'hsi_data'"
        }), 400
    
    rhythm_data = data['rhythm_data']
    hsi_data = data['hsi_data']
    
    # Validate data types
    if not isinstance(rhythm_data, dict):
        logger.warning(f"Invalid rhythm_data type: {type(rhythm_data)}")
        return jsonify({
            "success": False,
            "error": "Field 'rhythm_data' must be an object"
        }), 400
    
    if not isinstance(hsi_data, dict):
        logger.warning(f"Invalid hsi_data type: {type(hsi_data)}")
        return jsonify({
            "success": False,
            "error": "Field 'hsi_data' must be an object"
        }), 400
    
    # Process pacing decision
    # Medical Safety: process_pacing_decision NEVER crashes, always returns
    # safe response
    try:
        result = process_pacing_decision(rhythm_data, hsi_data)
        
        # Add processing time
        processing_time_ms = (time.time() - start_time) * 1000
        result['processing_time_ms'] = round(processing_time_ms, 2)
        
        logger.info(f"Pacing command computed in {processing_time_ms:.2f}ms")
        
        # Return appropriate status code
        if result['success']:
            return jsonify(result), 200
        else:
            # Error occurred but safe fallback returned
            logger.warning(f"Pacing computation error (safe fallback): {result.get('error')}")
            return jsonify(result), 200  # Still 200 because we have a safe response
        
    except Exception as e:
        # This should never happen (process_pacing_decision catches everything)
        # But include as ultimate safety net
        logger.error(f"Unexpected error in pacing endpoint: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Internal error: {str(e)}",
                    "pacing_command": {
                        "pacing_enabled": False,
                        "target_rate_bpm": 70.0,
                        "pacing_amplitude_ma": 0.0,
                        "pacing_mode": "monitor_only",
                        "safety_state": "emergency",
                        "safety_checks": {
                            "rate_within_bounds": True,
                            "amplitude_within_bounds": True,
                            "confidence_acceptable": False,
                            "hsi_acceptable": False,
                        },
                        "rationale": (
                            "Critical error - using emergency fallback (no pacing)"
                        ),
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            ),
            500,
        )


if __name__ == '__main__':
    register_shutdown_handler(logger)
    logger.info("Starting control-engine on port 8004")
    app.run(host="0.0.0.0", port=8004)  # nosec B104
