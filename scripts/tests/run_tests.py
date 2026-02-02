import subprocess  # nosec B404
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def main():
    """Runs Pytest with coverage."""
    print("Running Pytest...")
    # --cov=. runs coverage on current directory
    cmd = ["python", "-m", "pytest", "--cov=.", "--cov-report=term-missing"]

    result = subprocess.run(cmd, shell=True)  # nosec B602 B607

    if result.returncode != 0:
        print(f"\n{RED}Tests failed!{RESET}")
        sys.exit(1)

    print(f"\n{GREEN}SUCCESS: Tests passed!{RESET}")


if __name__ == "__main__":
    main()
