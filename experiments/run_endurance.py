"""Endurance Test Launcher.

This script runs the validation suite repeatedly for a specified duration
to check for memory leaks or resource exhaustion over time.

Usage:
    python experiments/run_endurance.py --hours 24
"""

import argparse
import time
import subprocess
import sys
from datetime import datetime

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def run_endurance_test(hours):
    start_time = time.time()
    end_time = start_time + (hours * 3600)
    iteration = 0
    failures = 0
    
    print(f"{BLUE}Starting Endurance Test for {hours} hours...{RESET}")
    print(f"Start Time: {datetime.now()}")
    
    try:
        while time.time() < end_time:
            iteration += 1
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] Iteration #{iteration}", end="... ", flush=True)
            
            # Run validation script
            result = subprocess.run(
                ["python", "experiments/run_validation.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            if result.returncode == 0:
                print(f"{GREEN}PASS{RESET}")
            else:
                failures += 1
                print(f"{RED}FAIL (Code {result.returncode}){RESET}")
                
            # Optional: Log memory usage here using 'docker stats'
            
            # Sleep briefly to prevent tight loop CPU spike if script is fast
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nEndurance test stopped manually.")

    print(f"\n{BLUE}Endurance Test Complete{RESET}")
    print(f"Total Iterations: {iteration}")
    print(f"Total Failures: {failures}")
    
    if failures == 0:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pulse-Mind Endurance Tester")
    parser.add_argument("--hours", type=float, default=24.0, help="Duration in hours")
    args = parser.parse_args()
    
    run_endurance_test(args.hours)
