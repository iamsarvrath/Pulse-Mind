import logging
import signal
import sys
import time

def register_shutdown_handler(logger: logging.Logger):
    """Register signal handlers for graceful shutdown.

    Args:
        logger: Logger instance to use
    """
    def graceful_shutdown(signum, frame):
        logger.info(f"Received signal {signum}. Shutting down...")
        # Perform any necessary cleanup here (e.g., closing DB
        # connections, stopping threads)
        # For now, we just log and exit, but this hook allows future expansion.
        
        # Give a moment for current requests to finish (simple heuristic)
        time.sleep(1) 
        
        logger.info("Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)
    logger.info("Registered graceful shutdown handlers")
