"""Throughput Test Script.

This script measures the maximum Requests Per Second (RPS) and Latency
of the Pulse-Mind system by sending concurrent signal processing requests.
"""

import time
import requests
import concurrent.futures
import statistics
import sys
import numpy as np

# ANSI Colors for Professional Output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

SIGNAL_SERVICE_URL = "http://localhost:8001/process"
CONCURRENCY_LEVELS = [1, 5, 10, 20, 50]
DURATION_PER_LEVEL = 5  # Seconds to run each test

def generate_signal(duration_sec=4, fs=100):
    t = np.linspace(0, duration_sec, int(duration_sec * fs))
    # Simple sine wave
    signal = 100 * np.sin(2 * np.pi * 1.2 * t) + 2048
    return signal.tolist()

def send_request(session, payload):
    start = time.time()
    try:
        resp = session.post(SIGNAL_SERVICE_URL, json=payload, timeout=2)
        latency = (time.time() - start) * 1000  # ms
        if resp.status_code != 200:
             print(f"DEBUG: Status {resp.status_code}, Text: {resp.text[:50]}")
        return resp.status_code == 200, latency
    except Exception as e:
        print(f"DEBUG: Exception: {e}")
        return False, 0.0

def run_load_test(concurrency):
    print(f"\n{BLUE}Testing with {concurrency} concurrent users...{RESET}")
    
    payload = {"signal": generate_signal(), "sampling_rate": 100}
    session = requests.Session()
    
    latencies = []
    success_count = 0
    fail_count = 0
    
    start_time = time.time()
    end_time = start_time + DURATION_PER_LEVEL
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        while time.time() < end_time:
            # Submit a batch of requests equal to concurrency
            futures = [executor.submit(send_request, session, payload) for _ in range(concurrency)]
            
            for future in concurrent.futures.as_completed(futures):
                success, latency = future.result()
                if success:
                    success_count += 1
                    latencies.append(latency)
                else:
                    fail_count += 1

    total_time = time.time() - start_time
    rps = success_count / total_time
    avg_latency = statistics.mean(latencies) if latencies else 0
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else avg_latency
    
    print(f"  {BOLD}Results (Concurrency {concurrency}):{RESET}")
    print(f"  - RPS: {GREEN}{rps:.2f} req/s{RESET}")
    print(f"  - Avg Latency: {YELLOW}{avg_latency:.2f} ms{RESET}")
    print(f"  - P95 Latency: {YELLOW}{p95_latency:.2f} ms{RESET}")
    print(f"  - Failures: {RED if fail_count > 0 else GREEN}{fail_count}{RESET}")
    
    return rps, avg_latency, fail_count

def main():
    print(f"{BOLD}Starting Throughput Analysis (Signal Service){RESET}")
    print(f"Target URL: {SIGNAL_SERVICE_URL}")
    
    results = []
    
    for level in CONCURRENCY_LEVELS:
        results.append(run_load_test(level))
        time.sleep(1)  # Cooldown
        
    print(f"\n{BOLD}{GREEN}Throughput Analysis Complete{RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
