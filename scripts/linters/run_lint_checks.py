import subprocess
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def main():
    """Runs Black (check mode) and Flake8."""
    print("Running black check...")
    black_result = subprocess.run(["python", "-m", "black", "--check", "--quiet", "services/"], shell=True)
    
    print("\nRunning flake8 check...")
    flake8_cmd = [
        "python", "-m", "flake8", "services/", "--count", 
        "--select=E9,F63,F7,F82", "--show-source", "--statistics"
    ]
    flake8_result = subprocess.run(flake8_cmd, shell=True)

    if black_result.returncode != 0 or flake8_result.returncode != 0:
        print(f"\n{RED}Lint checks failed!{RESET}")
        sys.exit(1)
    
    print(f"\n{GREEN}SUCCESS: All lint checks passed!{RESET}")

if __name__ == "__main__":
    main()
