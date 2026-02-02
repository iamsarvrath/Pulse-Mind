import subprocess  # nosec B404
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def main():
    """Runs Bandit security scan."""
    print("Running Bandit...")
    # -r for recursive, -f screen for readable output
    # skipping B104 (hardcoded_bind_all_interfaces) for Docker compatibility
    # skipping B301, B403 (pickle) for ML model loading
    cmd = ["python", "-m", "bandit", "-r", ".", "-f", "screen", "-s", "B104,B301,B403"]
    result = subprocess.run(cmd, shell=True)  # nosec B602 B607

    if result.returncode != 0:
        print(f"\n{RED}Security checks failed!{RESET}")
        sys.exit(1)

    print(f"\n{GREEN}SUCCESS: Security checks passed!{RESET}")


if __name__ == "__main__":
    main()
