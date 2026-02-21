"""Centralized logging utility for PulseMind services.

Provides structured JSON logging with consistent formatting.
"""
import logging
import sys
from datetime import datetime

from pythonjsonlogger import jsonlogger


# Sensitive fields to scrub from logs for HIPAA/GDPR compliance
PHI_FIELDS = {'patient_id', 'ssn', 'birth_date', 'signal', 'raw_data'}

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields and PHI scrubbing."""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        log_record['level'] = record.levelname
        if not log_record.get('service'):
            log_record['service'] = 'unknown'
            
        # PHI Scrubbing
        for field in PHI_FIELDS:
            if field in log_record:
                log_record[field] = "[MASKED_PHI]"
            if 'message' in log_record and isinstance(log_record['message'], str):
                if field in log_record['message'].lower():
                    log_record['message'] = "[REDACTED_POTENTIAL_PHI]"


def setup_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """Setup structured JSON logger for a service.

    Args:
        service_name: Name of the service
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(service)s %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Add service name to all log records
    adapter = logging.LoggerAdapter(logger, {"service": service_name})

    return adapter  # type: ignore[return-value]
