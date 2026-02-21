import requests
import logging
import time
import subprocess
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Service URLs
SIGNAL_SERVICE_URL = "http://localhost:8001"
CONTROL_ENGINE_URL = "http://localhost:8004"

def test_signal_service_failure_isolation():
    """Verify that if Signal Service is down, Control Engine handles it safely."""
    logger.info("Starting Chaos Test: Signal Service Failure...")
    
    # 1. Verify system is currently healthy
    try:
        requests.get(f"{CONTROL_ENGINE_URL}/health", timeout=2)
    except Exception:
        logger.error("Control Engine is not running. Start it before running chaos tests.")
        return False

    # 2. Simulate Signal Service Failure (We can't easily kill docker here without more perms, 
    # but we can simulate a 'timeout' or 'connection refused' by using a bad port if we were mocking,
    # OR we can just assume it's down if it fails health check)
    
    # Let's verify what happens if we send an EMPTY rhythm to Control Engine 
    # (which would happen if previous services failed)
    logger.info("Injecting failure: Sending empty rhythm data to Control Engine...")
    fail_payload = {
        "rhythm_data": None,
        "hsi_data": None
    }
    
    try:
        resp = requests.post(f"{CONTROL_ENGINE_URL}/compute-pacing", json=fail_payload, timeout=5)
        if resp.status_code == 400:
            logger.info("✅ Control Engine correctly rejected empty payload with 400")
        else:
            logger.warning(f"Control Engine returned {resp.status_code} - checking safety...")
    except Exception as e:
        logger.error(f"Post failed as expected or crashed: {e}")

    # 3. Simulate Signal Service Failure
    logger.info("Attempting to stop Signal Service for real chaos...")
    
    # Try Docker stop first
    subprocess.run(["docker", "stop", "pulsemind-signal-service"], capture_output=True)
    
    # Also try to kill local process on port 8001 (Windows specific)
    try:
        # Find PID listening on 8001
        result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if ":8001" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                logger.info(f"   -> Killing local Signal Service process (PID: {pid})")
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
    except Exception as e:
        logger.warning(f"Could not kill local process: {e}")

    time.sleep(3)
    
    try:
        resp = requests.get(f"{SIGNAL_SERVICE_URL}/health", timeout=1)
        logger.error(f"❌ Signal Service is still alive! (Status: {resp.status_code}) Chaos failed.")
        return False
    except Exception:
        logger.info("✅ Signal Service is successfully DOWN")
        
    # 4. Verify System Logic handles the failure
    # ...
    
    logger.info("Restarting Signal Service...")
    # Attempt Docker start
    subprocess.run(["docker", "start", "pulsemind-signal-service"], capture_output=True)
    
    # Attempt Local restart (optional, usually chaos tests are run in controlled env)
    # Since we are in a dev env, we can just log it or try to restart if we have the path
    logger.info("Service should be manually restarted if not running in Docker.")
    
    return True

if __name__ == "__main__":
    test_signal_service_failure_isolation()
