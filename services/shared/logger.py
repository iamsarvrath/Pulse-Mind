"""
Centralized logging utility for PulseMind services.
Provides structured JSON logging with consistent formatting.
"""
import logging
import sys
from datetime import datetime
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        log_record['level'] = record.levelname
        if not log_record.get('service'):
            log_record['service'] = 'unknown'


def setup_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Setup structured JSON logger for a service.
    
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
    logger = logging.LoggerAdapter(logger, {'service': service_name})
    
    return logger
