import sys
import os
from datetime import datetime
from flask import Flask, jsonify, request
import time

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.logger import setup_logger
from shared.shutdown import register_shutdown_handler
from signal_processor import process_ppg_signal

# Initialize logger
logger = setup_logger("signal-service", level="INFO")

app = Flask(__name__)


@app.route('/health')
def health_check():
    """Health check endpoint for container orchestration."""
    logger.info("Health check requested")
    return jsonify({
        "status": "healthy",
        "service": "signal-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }), 200


@app.route('/')
def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return jsonify({
        "service": "signal-service",
        "version": "1.0.0",
        "status": "running",
        "description": "Signal Processing Service",
        "endpoints": {
            "/health": "Health check",
            "/process": "POST - Process PPG signal"
        },
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    })


@app.route('/process', methods=['POST'])
def process_signal():
    """
    Process PPG signal and extract features.
    
    Expected JSON payload:
    {
        "signal": [100, 102, 105, ...],  # Array of signal values
        "sampling_rate": 100              # Sampling rate in Hz
    }
    
    Returns:
    {
        "success": true/false,
        "features": {
            "heart_rate_bpm": 72.5,
            "hrv_sdnn_ms": 45.3,
            "pulse_amplitude": 15.2,
            "num_peaks": 12
        },
        "metadata": {...},
        "error": "..." (only if success=false)
    }
    """
    start_time = time.time()
    logger.info("Signal processing request received")
    
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
    if 'signal' not in data:
        logger.warning("Missing 'signal' field in request")
        return jsonify({
            "success": False,
            "error": "Missing required field: 'signal'"
        }), 400
    
    if 'sampling_rate' not in data:
        logger.warning("Missing 'sampling_rate' field in request")
        return jsonify({
            "success": False,
            "error": "Missing required field: 'sampling_rate'"
        }), 400
    
    signal_array = data['signal']
    sampling_rate = data['sampling_rate']
    
    # Validate types
    if not isinstance(signal_array, list):
        logger.warning(f"Invalid signal type: {type(signal_array)}")
        return jsonify({
            "success": False,
            "error": "Field 'signal' must be an array"
        }), 400
    
    try:
        sampling_rate = float(sampling_rate)
    except (ValueError, TypeError):
        logger.warning(f"Invalid sampling_rate: {sampling_rate}")
        return jsonify({
            "success": False,
            "error": "Field 'sampling_rate' must be a number"
        }), 400
    
    # Process signal
    try:
        result = process_ppg_signal(signal_array, sampling_rate)
        
        # Add processing time to metadata
        processing_time_ms = (time.time() - start_time) * 1000
        result['metadata']['processing_time_ms'] = round(processing_time_ms, 2)
        
        logger.info(f"Signal processed successfully in {processing_time_ms:.2f}ms")
        return jsonify(result), 200
        
    except ValueError as e:
        # Validation or processing errors
        logger.warning(f"Signal processing validation error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error during signal processing: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Internal processing error: {str(e)}"
        }), 500


if __name__ == '__main__':
    register_shutdown_handler(logger)
    logger.info("Starting signal-service on port 8001")
    app.run(host='0.0.0.0', port=8001)
