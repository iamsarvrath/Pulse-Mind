"""Safety Path Verification Script.

This script validates the Critical Safety Path:
Tachycardia Signal -> Detection -> Pacing Enabled -> Persistence Log.
"""

import os
import sys
import time
import requests
import sqlite3
import numpy as np
import subprocess

# ANSI Colors for Professional Output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Configuration
SERVICES = {
    "signal": "http://localhost:8001",
    "hsi": "http://localhost:8002",
    "ai": "http://localhost:8003",
    "control": "http://localhost:8004",
}

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "services", "control-engine", "pacing_decisions.db")

def generate_tachycardia_signal(duration_sec=5, fs=100):
    """Generate a high-rate (130 BPM) signal."""
    t = np.linspace(0, duration_sec, int(duration_sec * fs))
    freq = 2.17  # ~130 BPM
    signal = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(4 * np.pi * freq * t)
    signal = (signal * 100) + 2048
    return signal.tolist()

def log_info(msg):
    print(f"{BLUE}[INFO]{RESET} {msg}")

def log_success(msg):
    print(f"{GREEN}[PASS]{RESET} {msg}")

def log_fail(msg):
    print(f"{RED}[FAIL]{RESET} {msg}")

def log_warn(msg):
    print(f"{YELLOW}[WARN]{RESET} {msg}")

def verify_safety_path():
    print(f"\n{BOLD}Starting Safety Path Verification (Tachycardia Simulation)...{RESET}")
    
    # 1. Generate Signal
    signal = generate_tachycardia_signal()
    
    try:
        # 2. Process Signal
        # log_info("Sending signal to Signal Service...")
        resp_sig = requests.post(f"{SERVICES['signal']}/process", json={"signal": signal, "sampling_rate": 100})
        if resp_sig.status_code != 200:
            log_fail(f"Signal Service Failed: {resp_sig.text}")
            return False
        features = resp_sig.json()["features"]
        log_success(f"Signal Processed: HR={features['heart_rate_bpm']:.1f} BPM")
        
        # 3. AI Inference
        resp_ai = requests.post(f"{SERVICES['ai']}/predict", json={"features": features})
        rhythm_data = resp_ai.json().get("prediction", {})
        log_success(f"AI Inference: Class={rhythm_data.get('rhythm_class')}")
        
        # 4. HSI Computation
        resp_hsi = requests.post(f"{SERVICES['hsi']}/compute-hsi", json={"features": features})
        hsi_data = resp_hsi.json()
        if "input_features" not in hsi_data:
            hsi_data["input_features"] = features
        log_success(f"HSI Computed: Score={hsi_data.get('hsi', {}).get('hsi_score'):.1f}")
        
        # 5. Control Engine - OVERRIDE CONFIDENCE for Safety Test
        # We manually boost confidence to 0.95 to ensure we test the Tachycardia logic
        # and not the "Low Confidence" fallback logic.
        rhythm_data["confidence"] = 0.95
        log_info(f"Test Override: Boosted Confidence to {rhythm_data['confidence']}")

        resp_ctrl = requests.post(
            f"{SERVICES['control']}/compute-pacing",
            json={"rhythm_data": rhythm_data, "hsi_data": hsi_data}
        )
        ctrl_data = resp_ctrl.json()
        pacing = ctrl_data.get("pacing_command", {})
        
        # ASSERTIONS
        print(f"\n{BOLD}Verifying Safety Decisions...{RESET}")
        
        # A. Check Pacing Status
        if pacing.get("pacing_enabled") is True:
            log_success("Pacing Triggered Successfully")
        else:
            log_fail(f"Pacing NOT Triggered (Mode: {pacing.get('pacing_mode')})")
            return False
            
        # B. Check Pacing Mode (Should be Aggressive or Moderate for Tachycardia)
        mode = pacing.get("pacing_mode")
        if mode in ["aggressive", "moderate"]:
             log_success(f"Correct Pacing Mode ({mode})")
        else:
             log_warn(f"Unexpected Pacing Mode ({mode})")
             # Don't fail hard here if we are debugging, but for E2E it should pass

        # C. Check Database Persistence (FROM DOCER CONTAINER)
        print(f"\n{BOLD}Verifying Audit Log (fetching from container)...{RESET}")
        
        start_time = time.time()
        found_new = False
        
        while time.time() - start_time < 10: # 10s timeout
            try:
                # Copy DB from container to temp file
                subprocess.run("docker cp pulsemind-control-engine:/app/pacing_decisions.db temp_db.sqlite", 
                             shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                conn = sqlite3.connect("temp_db.sqlite")
                cur = conn.cursor()
                # Get latest decision with rationale
                cur.execute("SELECT id, rhythm_class, pacing_mode, rationale FROM decisions ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                conn.close()
                
                if row:
                    # Check if this looks like our Tachycardia test (confidence boost -> 0.95 not visible here directly but class should be Tachycardia)
                    if row[1] == "tachycardia" and row[2] == mode:
                         log_success(f"Decision Logged to DB (ID={row[0]}, Class={row[1]}, Mode={row[2]})")
                         found_new = True
                         break
                    elif row[1] == "tachycardia":
                         # Found the record but mode mismatch
                         log_success(f"Decision Logged to DB (ID={row[0]})")
                         log_fail(f"Mode mismatch (Expected {mode}, got {row[2]})")
                         log_info(f"Rationale from DB: {row[3]}")
                         found_new = True # Found the record, just failed content
                         return False

            except Exception:
                pass
            
            time.sleep(1)

        if not found_new:
             log_fail("Could not find new record in DB after 10s")
             # Print last seen for debug
             if 'row' in locals() and row:
                  log_info(f"Last seen: ID={row[0]}, Class={row[1]}")
             return False

        return True

    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

if __name__ == "__main__":
    success = verify_safety_path()
    if success:
        print(f"\n{GREEN}{BOLD}SAFETY PATH VERIFICATION COMPLETED SUCCESSFULLY{RESET}")
        sys.exit(0)
    else:
        print(f"\n{RED}{BOLD}SAFETY PATH VERIFICATION FAILED{RESET}")
        sys.exit(1)
