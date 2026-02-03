import os
import subprocess
import time
import requests
import json
from datetime import datetime
import numpy as np

# Configuration
SERVICES = {
    "signal": "http://localhost:8001",
    "hsi": "http://localhost:8002",
    "ai": "http://localhost:8003",
    "control": "http://localhost:8004",
}

def generate_normal_signal(duration_sec=5, fs=100):
    t = np.linspace(0, duration_sec, int(duration_sec * fs))
    freq = 1.25  # 75 BPM
    signal = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(4 * np.pi * freq * t)
    signal = (signal * 100) + 2048
    return signal.tolist()

def run_orchestrated_flow():
    """Simulates the full data flow: Signal -> AI -> HSI -> Control.
    Handles AI failure via client-side fallback (orchestrator pattern).
    """
    try:
        # 1. Signal
        signal = generate_normal_signal()
        resp_sig = requests.post(f"{SERVICES['signal']}/process", json={"signal": signal, "sampling_rate": 100}, timeout=2)
        if resp_sig.status_code != 200: return {"status": "error", "stage": "signal", "details": resp_sig.text}
        features = resp_sig.json().get("features", {})

        # 2. AI (May Fail)
        try:
            resp_ai = requests.post(f"{SERVICES['ai']}/predict", json={"features": features}, timeout=2)
            ai_data = resp_ai.json()
            ai_success = ai_data.get("success", False)
            prediction = ai_data.get("prediction", {}) if ai_success else {}
        except Exception:
            ai_success = False
            prediction = {}

        # Orchestrator Fallback for AI
        if not ai_success:
            rhythm_data = {"rhythm_class": "unknown", "confidence": 0.0}
        else:
            rhythm_data = prediction

        # 3. HSI
        try:
            resp_hsi = requests.post(f"{SERVICES['hsi']}/compute-hsi", json={"features": features}, timeout=2)
            hsi_data = resp_hsi.json()
        except Exception:
             hsi_data = {"hsi": {"hsi_score": 50.0}, "trend": {"trend_direction": "stable"}, "input_features": features}

        if "input_features" not in hsi_data: hsi_data["input_features"] = features

        # 4. Control
        resp_ctrl = requests.post(f"{SERVICES['control']}/compute-pacing", json={"rhythm_data": rhythm_data, "hsi_data": hsi_data}, timeout=2)
        ctrl_data = resp_ctrl.json()
        
        return {
            "status": "success",
            "ai_alive": ai_success,
            "control_decision": ctrl_data.get("pacing_command", {})
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ANSI Output Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def main():
    print(f"--- {BOLD}Starting Chaos Test (Issue 1.5){RESET} ---")
    
    # Phase 1: Baseline
    print(f"\nPhase 1: {BOLD}Establishing Baseline...{RESET}")
    res = run_orchestrated_flow()
    if res["status"] != "success" or not res["ai_alive"]:
        print(f"{RED}FAIL: Baseline Failed! Is the system running?{RESET}")
        print(res)
        exit(1)
    print(f"{GREEN}PASS: Baseline Established (System Healthy){RESET}")

    # Phase 2: Kill AI Service
    print(f"\nPhase 2: {BOLD}Induced Failure (Stopping AI Service)...{RESET}")
    run_cmd("docker compose stop ai-inference")
    time.sleep(3) # Wait for shutdown
    
    print("Verifying Graceful Degradation...")
    res = run_orchestrated_flow()
    
    if res["status"] == "success":
        decision = res["control_decision"]
        safety_state = decision.get("safety_state")
        mode = decision.get("pacing_mode")
        
        print(f"System Response: SafetyState={safety_state}, Mode={mode}, AI_Alive={res['ai_alive']}")
        
        if not res["ai_alive"] and (safety_state == "safe_mode" or safety_state == "degraded" or mode == "monitor_only"):
            print(f"{GREEN}PASS: System degraded gracefully to Safe Mode/Monitor Only.{RESET}")
        else:
            print(f"{RED}FAIL: Unexpected state: {safety_state}{RESET}")
            exit(1)
    else:
        print(f"{RED}FAIL: Orchestrator crashed: {res}{RESET}")
        exit(1)

    # Phase 3: Recovery
    print(f"\nPhase 3: {BOLD}Recovery (Restarting AI Service)...{RESET}")
    run_cmd("docker compose start ai-inference")
    time.sleep(10) # Wait for startup
    
    print("Verifying System Recovery...")
    res = run_orchestrated_flow()
    
    if res["status"] == "success" and res["ai_alive"]:
        print(f"{GREEN}PASS: System fully recovered.{RESET}")
    else:
        print(f"{RED}FAIL: System did not recover. AI Alive: {res.get('ai_alive')}{RESET}")
        exit(1)

    print(f"\n{GREEN}{BOLD}CHAOS TEST COMPLETED SUCCESSFULLY{RESET}")

if __name__ == "__main__":
    main()
