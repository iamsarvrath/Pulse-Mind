import subprocess  # nosec B404
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def main():
    """Runs Black, Flake8, and Mypy checks."""
    success = True

    print("Running Black...")
    res_black = subprocess.run(
        ["python", "-m", "black", "--check", "--quiet", "."], shell=True
    )  # nosec B602 B607
    if res_black.returncode != 0:
        success = False

    print("\nRunning Flake8...")
    res_flake8 = subprocess.run(
        ["python", "-m", "flake8", "."], shell=True
    )  # nosec B602 B607
    if res_flake8.returncode != 0:
        success = False

    print("\nRunning Mypy...")
    res_mypy = subprocess.run(
        ["python", "-m", "mypy", "."], shell=True
    )  # nosec B602 B607
    if res_mypy.returncode != 0:
        success = False

    print("\nRunning Prettier (Check)...")
    res_prettier = subprocess.run(
        [
            "npx",
            "prettier",
            "--check",
            "**/*.{md,json,yaml,yml,js,css}",
            "--loglevel",
            "warn",
        ],
        shell=True,
    )  # nosec B602 B607
    if res_prettier.returncode != 0:
        success = False

    if not success:
        print(f"\n{RED}Lint checks failed!{RESET}")
        sys.exit(1)

    print(f"\n{GREEN}SUCCESS: All lint checks passed!{RESET}")


if __name__ == "__main__":
    main()
