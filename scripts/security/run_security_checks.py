import subprocess
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def main():
    """Runs Bandit security scan."""
    print("Running bandit security scan...")
    # using -r for recursive and -f screen for readable output
    # skipping B104 (hardcoded_bind_all_interfaces) as we need 0.0.0.0 for Docker
    # skipping B301, B403 (pickle) as we use it for ML model loading trusted data
    cmd = [
        "python", "-m", "bandit", "-r", "services/", "-f", "screen",
        "-s", "B104,B301,B403"
    ]
    bandit_result = subprocess.run(cmd, shell=True)
    
    if bandit_result.returncode != 0:
        print(f"\n{RED}Security checks failed!{RESET}")
        sys.exit(1)
    
    print(f"\n{GREEN}SUCCESS: Security checks passed!{RESET}")

if __name__ == "__main__":
    main()
