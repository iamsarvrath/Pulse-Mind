import requests
import time
import json
import logging
import numpy as np
import unittest

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Service URLs
SIGNAL_SERVICE_URL = "http://localhost:8001"
HSI_SERVICE_URL = "http://localhost:8002"
AI_INFERENCE_URL = "http://localhost:8003"
CONTROL_ENGINE_URL = "http://localhost:8004"

def is_service_running(url):
    try:
        requests.get(f"{url}/health", timeout=1)
        return True
    except requests.exceptions.RequestException:
        return False


class TestPulseMindIntegration(unittest.TestCase):
    
    def setUp(self):
        if not is_service_running(SIGNAL_SERVICE_URL):
            self.skipTest("Signal Service is not running")

    def test_01_health_checks(self):

        """Verify all services are up and healthy."""
        services = [
            ("Signal Service", SIGNAL_SERVICE_URL),
            ("HSI Service", HSI_SERVICE_URL),
            ("AI Inference", AI_INFERENCE_URL),
            ("Control Engine", CONTROL_ENGINE_URL)
        ]
        
        for name, url in services:
            try:
                resp = requests.get(f"{url}/health", timeout=2)
                self.assertEqual(resp.status_code, 200, f"{name} health check failed")
                logger.info(f"✅ {name} is healthy")
            except requests.exceptions.RequestException as e:
                self.fail(f"Could not connect to {name}: {e}")

    def test_02_end_to_end_flow(self):
        """Simulate a complete data flow cycle."""
        logger.info("Starting End-to-End Flow Test...")
        
        # 1. Generate Signal (Normal Sinus Rhythm)
        t = np.linspace(0, 4, 400) # 4 seconds at 100Hz
        signal = 500 * np.sin(2 * np.pi * 1.2 * t) + 2000 # Simple sine wave approx 72 BPM
        signal_payload = {"signal": signal.tolist(), "sampling_rate": 100}
        
        # 2. Call Signal Service
        logger.info("Step 1: Signal Processing...")
        resp = requests.post(f"{SIGNAL_SERVICE_URL}/process", json=signal_payload)
        self.assertEqual(resp.status_code, 200)
        features = resp.json().get("features")
        self.assertIsNotNone(features)
        logger.info(f"   -> Extracted Features: HR={features.get('heart_rate_bpm')}")
        
        # 3. Call HSI Service
        logger.info("Step 2: HSI Computation...")
        hsi_payload = {"features": features}
        resp = requests.post(f"{HSI_SERVICE_URL}/compute-hsi", json=hsi_payload)
        self.assertEqual(resp.status_code, 200)
        hsi_data = resp.json()
        self.assertIn("hsi", hsi_data)
        logger.info(f"   -> HSI Score: {hsi_data['hsi']['hsi_score']}")
        
        # 4. Call AI Inference
        logger.info("Step 3: AI Rhythm Classification...")
        ai_payload = {"features": features}
        resp = requests.post(f"{AI_INFERENCE_URL}/predict", json=ai_payload)
        self.assertEqual(resp.status_code, 200)
        rhythm_data = resp.json().get("prediction")
        self.assertIsNotNone(rhythm_data)
        logger.info(f"   -> Rhythm Class: {rhythm_data['rhythm_class']}")
        
        # 5. Call Control Engine
        logger.info("Step 4: Control Decision...")
        # Prepare full payload as Control Engine expects HSI data + trend + features
        full_hsi_payload = {
            "hsi_score": hsi_data['hsi']['hsi_score'],
            "trend": hsi_data['trend'],
            "input_features": features
        }
        
        control_payload = {
            "rhythm_data": rhythm_data,
            "hsi_data": full_hsi_payload
        }
        
        resp = requests.post(f"{CONTROL_ENGINE_URL}/compute-pacing", json=control_payload)
        self.assertEqual(resp.status_code, 200)
        pacing_cmd = resp.json().get("pacing_command")
        self.assertIsNotNone(pacing_cmd)
        
        logger.info(f"✅ FINAL DECISION: {pacing_cmd['pacing_mode'].upper()}")
        logger.info(f"   Rationale: {pacing_cmd['rationale']}")
        
        # Assertions for safety
        self.assertIn(pacing_cmd['pacing_mode'], ["monitor_only", "minimal", "moderate", "aggressive", "emergency"])
        self.assertTrue(30 <= pacing_cmd['target_rate_bpm'] <= 200)

    def test_03_error_handling(self):
        """Verify services handle bad input gracefully."""
        logger.info("Testing Error Handling...")
        
        # Send garbage to signal service
        resp = requests.post(f"{SIGNAL_SERVICE_URL}/process", json={"signal": "garbage"})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['success'])
        logger.info("✅ Signal Service handled bad input correctly")
        
        # Send garbage to Control Engine (should be critical safety test)
        # Even with garbage, it might 400, but if we send PARTIAL data, it should fail safe if possible 
        # or return a clear error.
        resp = requests.post(f"{CONTROL_ENGINE_URL}/compute-pacing", json={})
        self.assertEqual(resp.status_code, 400)
        logger.info("✅ Control Engine rejected empty body")

if __name__ == '__main__':
    unittest.main()
