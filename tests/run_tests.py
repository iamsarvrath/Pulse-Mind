"""Unified Test Runner for Pulse-Mind Services.

This script allows running all unit tests.
Modified to run from the 'tests/' folder.
"""

import os
import sys
import subprocess
import time

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Define services and their test files (relative to PROJECT ROOT)
SERVICES = {
    "Signal Service": "services/signal-service/test_signal_processor.py",
    "HSI Service": "services/hsi-service/test_hsi_computer.py",
    "AI Inference": "services/ai-inference/test_rhythm_classifier.py",
    "Control Engine": "services/control-engine/test_pacing_controller.py",
    "Integration Suite": "tests/integration_test.py"
}

def run_service_tests(service_name, test_path):
    """Run tests for a specific service."""
    print(f"\n{'='*60}")
    print(f" Running Tests for {service_name}")
    print(f"{'='*60}")
    
    # Get absolute paths - adjusted for being in 'tests/' folder
    current_dir = os.path.abspath(os.path.dirname(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, ".."))
    test_file = os.path.abspath(os.path.join(root_dir, test_path))
    service_dir = os.path.dirname(test_file)
    
    # Run the test file directly as a script
    env = os.environ.copy()
    env["PYTHONPATH"] = service_dir + os.pathsep + os.path.join(root_dir, "services") + os.pathsep + os.path.join(root_dir, "services", "shared") + os.pathsep + env.get("PYTHONPATH", "")
    
    try:
        # We run with 'python -m unittest' but from the service directory to ensure local imports work
        result = subprocess.run(
            [sys.executable, "-m", "unittest", os.path.basename(test_file)],
            cwd=service_dir,
            env=env,
            capture_output=False, # Show output in real-time
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests for {service_name}: {e}")
        return False

def main():
    print(f"Pulse-Mind Unified Test Runner")
    print(f"Execution Context: tests/run_tests.py")
    print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    for service, path in SERVICES.items():
        success = run_service_tests(service, path)
        results[service] = success
        
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f" {BOLD}TEST SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    all_passed = True
    for service, passed in results.items():
        if passed:
            status = f"{GREEN}PASSED{RESET}"
        else:
            status = f"{RED}FAILED{RESET}"
            all_passed = False
        print(f"{service:.<40} {status}")
            
    print(f"{BOLD}{'='*60}{RESET}")
    if all_passed:
        print(f"{GREEN}{BOLD}ALL TESTS PASSED SUCCESSFULLY{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}SOME TESTS FAILED - CHECK OUTPUT ABOVE{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
