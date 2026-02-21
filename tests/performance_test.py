import time
import requests
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Service URLs
SIGNAL_SERVICE_URL = "http://localhost:8001"
HSI_SERVICE_URL = "http://localhost:8002"
AI_INFERENCE_URL = "http://localhost:8003"
CONTROL_ENGINE_URL = "http://localhost:8004"

def measure_pipeline_latency(iterations=20):
    """Measure the end-to-end latency of the system."""
    logger.info(f"Measuring pipeline latency over {iterations} iterations...")
    
    latencies = []
    
    # Pre-generate signal
    t = np.linspace(0, 4, 400)
    signal = 500 * np.sin(2 * np.pi * 1.2 * t) + 2000
    payload = {"signal": signal.tolist(), "sampling_rate": 100}

    for i in range(iterations):
        start_time = time.perf_counter()
        
        try:
            # 1. Signal
            s_resp = requests.post(f"{SIGNAL_SERVICE_URL}/process", json=payload, timeout=5)
            features = s_resp.json().get("features")
            
            # 2. HSI
            h_resp = requests.post(f"{HSI_SERVICE_URL}/compute-hsi", json={"features": features}, timeout=5)
            hsi_data = h_resp.json()
            
            # 3. AI
            a_resp = requests.post(f"{AI_INFERENCE_URL}/predict", json={"features": features}, timeout=5)
            rhythm_data = a_resp.json().get("prediction")
            
            # 4. Control
            c_payload = {
                "rhythm_data": rhythm_data,
                "hsi_data": {
                    "hsi_score": hsi_data["hsi"]["hsi_score"],
                    "trend": hsi_data["trend"],
                    "input_features": features
                }
            }
            requests.post(f"{CONTROL_ENGINE_URL}/compute-pacing", json=c_payload, timeout=5)
            
            end_time = time.perf_counter()
            latencies.append((end_time - start_time) * 1000) # ms
            
        except Exception as e:
            logger.error(f"Iteration {i} failed: {e}")

    if latencies:
        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        logger.info(f"Average Latency: {avg_latency:.2f} ms")
        logger.info(f"P95 Latency: {p95_latency:.2f} ms")
        return avg_latency, p95_latency
    return None

def measure_signal_throughput(duration_sec=5):
    """Measure how many signals the signal service can process per second."""
    logger.info(f"Measuring Signal Service throughput for {duration_sec} seconds...")
    
    t = np.linspace(0, 4, 400)
    signal = 500 * np.sin(2 * np.pi * 1.2 * t) + 2000
    payload = {"signal": signal.tolist(), "sampling_rate": 100}
    
    count = 0
    start_time = time.time()
    while (time.time() - start_time) < duration_sec:
        try:
            requests.post(f"{SIGNAL_SERVICE_URL}/process", json=payload, timeout=2)
            count += 1
        except Exception:
            break
            
    elapsed = time.time() - start_time
    tps = count / elapsed
    logger.info(f"Throughput: {tps:.2f} requests/sec")
    return tps

if __name__ == "__main__":
    measure_pipeline_latency()
    measure_signal_throughput()
