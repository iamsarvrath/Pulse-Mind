"""JSON Schemas for Pulse-Mind API Contract Verification."""

SIGNAL_RESP_SCHEMA = {
    "type": "object",
    "required": ["success", "features", "timestamp"],
    "properties": {
        "success": {"type": "boolean"},
        "features": {
            "type": "object",
            "required": ["heart_rate_bpm", "hrv_sdnn_ms", "pulse_amplitude"],
            "properties": {
                "heart_rate_bpm": {"type": "number"},
                "hrv_sdnn_ms": {"type": "number"},
                "pulse_amplitude": {"type": "number"}
            }
        },
        "timestamp": {"type": "string"}
    }
}

HSI_RESP_SCHEMA = {
    "type": "object",
    "required": ["success", "hsi", "trend", "timestamp"],
    "properties": {
        "success": {"type": "boolean"},
        "hsi": {
            "type": "object",
            "required": ["hsi_score"],
            "properties": {
                "hsi_score": {"type": "number"}
            }
        },
        "trend": {
            "type": "object",
            "required": ["trend_direction"],
            "properties": {
                "trend_direction": {"type": "string", "enum": ["stable", "improving", "declining"]}
            }
        },
        "timestamp": {"type": "string"}
    }
}

AI_RESP_SCHEMA = {
    "type": "object",
    "required": ["success", "prediction", "timestamp"],
    "properties": {
        "success": {"type": "boolean"},
        "prediction": {
            "type": "object",
            "required": ["rhythm_class", "confidence"],
            "properties": {
                "rhythm_class": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            }
        },
        "timestamp": {"type": "string"}
    }
}

CONTROL_RESP_SCHEMA = {
    "type": "object",
    "required": ["success", "pacing_command", "timestamp"],
    "properties": {
        "success": {"type": "boolean"},
        "pacing_command": {
            "type": "object",
            "required": ["pacing_enabled", "target_rate_bpm", "pacing_mode", "safety_state"],
            "properties": {
                "pacing_enabled": {"type": "boolean"},
                "target_rate_bpm": {"type": "number"},
                "pacing_amplitude_ma": {"type": "number"},
                "pacing_mode": {"type": "string"},
                "safety_state": {"type": "string"}
            }
        },
        "timestamp": {"type": "string"}
    }
}
