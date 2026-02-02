import subprocess
import sys
import os

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
YELLOW = "\033[93m"

def main():
    """Runs Pytest unit tests."""
    print("Running pytest...")
    
    if not os.path.exists("tests"):
        print(f"{YELLOW}Tests directory not found. Skipping.{RESET}")
        return

    pytest_result = subprocess.run(["python", "-m", "pytest", "tests/", "services/"], shell=True)
    
    if pytest_result.returncode != 0:
        print(f"\n{RED}Tests failed!{RESET}")
        sys.exit(1)
    
    print(f"\n{GREEN}SUCCESS: Tests passed!{RESET}")

if __name__ == "__main__":
    main()
