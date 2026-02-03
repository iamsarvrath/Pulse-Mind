"""Stress Test Script.

This script aggressively floods the services to identify breaking points.
It targets Signal, HSI, and AI services with high concurrency.
"""

import time
import requests
import concurrent.futures
import statistics
import sys
import numpy as np

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

SERVICES = {
    "signal": "http://localhost:8001/process",
    "hsi": "http://localhost:8002/compute-hsi",
    "ai": "http://localhost:8003/predict"
}

# Aggressive Concurrency
CONCURRENCY = 100
DURATION = 10

def generate_signal_payload():
    t = np.linspace(0, 4, 400) # 4 seconds
    signal = 100 * np.sin(2 * np.pi * 1.2 * t) + 2048
    return {"signal": signal.tolist(), "sampling_rate": 100}

def generate_features_payload():
    return {
        "features": {
            "heart_rate_bpm": 72.0,
            "hrv_sdnn_ms": 45.0,
            "pulse_amplitude": 15.0
        }
    }

def stress_endpoint(name, url, payload_gen):
    print(f"\n{BOLD}Stress Testing {name.upper()} Service...{RESET}")
    print(f"Target: {url} | Concurrency: {CONCURRENCY}")
    
    session = requests.Session()
    payload = payload_gen()
    
    success_count = 0
    fail_count = 0
    errors = {}
    
    start_time = time.time()
    end_time = start_time + DURATION
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = []
        while time.time() < end_time:
            if len(futures) < CONCURRENCY * 2: # Keep queue full but not exploding
                futures.append(executor.submit(session.post, url, json=payload, timeout=5))
            
            # Process completed
            done, not_done = concurrent.futures.wait(futures, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED)
            futures = list(not_done)
            
            for future in done:
                try:
                    resp = future.result()
                    if resp.status_code == 200:
                        success_count += 1
                    else:
                        fail_count += 1
                        code = resp.status_code
                        errors[code] = errors.get(code, 0) + 1
                except Exception as e:
                    fail_count += 1
                    etype = type(e).__name__
                    errors[etype] = errors.get(etype, 0) + 1

    total_time = time.time() - start_time
    rps = success_count / total_time
    
    print(f"  {BOLD}Results:{RESET}")
    print(f"  - RPS: {GREEN if fail_count == 0 else YELLOW}{rps:.2f} req/s{RESET}")
    print(f"  - Success: {GREEN}{success_count}{RESET}")
    print(f"  - Failures: {RED if fail_count > 0 else GREEN}{fail_count}{RESET}")
    
    if fail_count > 0:
        print(f"  - Error Breakdown: {errors}")
        return False
    return True

def main():
    print(f"{BOLD}Starting Pulse-Mind Stress Analysis{RESET}")
    
    # 1. Stress Signal Service
    stress_endpoint("signal", SERVICES["signal"], generate_signal_payload)
    
    # 2. Stress AI Service
    stress_endpoint("ai", SERVICES["ai"], generate_features_payload)
    
    # 3. Stress HSI Service
    stress_endpoint("hsi", SERVICES["hsi"], generate_features_payload)
    
    print(f"\n{BOLD}Stress Analysis Complete{RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
