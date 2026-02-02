import os
import re
import subprocess  # nosec B404  # nosec B404
import sys

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def check_and_install(package_name):
    """Checks if a package is installed via pip, and installs it if missing."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "show", package_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # nosec B603
    except subprocess.CalledProcessError:
        print(f"{YELLOW}⚠️  {package_name} not found. Installing...{RESET}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name], check=True
        )  # nosec B603


def fix_custom_issues():
    """Applies custom fixes for issues that standard formatters miss or create."""
    print("🔧 Running custom fixes for stubborn errors...")

    # 1. Recovery for evaluate_model.py (Syntax Error)
    eval_model_path = os.path.join(os.getcwd(), "ai_training/evaluate_model.py")
    if os.path.exists(eval_model_path):
        try:
            with open(eval_model_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Match "PulseMind AI Model Evaluation followed by newline and then ")
            # This is the exact pattern that broke syntax.
            if 'f.write("PulseMind AI Model Evaluation\n' in content:
                print("  - Recovering evaluate_model.py from syntax error (LF)")
                new_content = content.replace(
                    'f.write("PulseMind AI Model Evaluation\n',
                    'f.write("PulseMind AI Model Evaluation\\n',
                )
                with open(eval_model_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                content = new_content

            if 'f.write("PulseMind AI Model Evaluation\r\n' in content:
                print("  - Recovering evaluate_model.py from syntax error (CRLF)")
                new_content = content.replace(
                    'f.write("PulseMind AI Model Evaluation\r\n',
                    'f.write("PulseMind AI Model Evaluation\\n',
                )
                with open(eval_model_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        except Exception as e:
            print(f"  - Failed to recover evaluate_model.py: {e}")

    # 2. Fix missing datetime import in various files
    fix_files = [
        "experiments/health_check.py",
        "experiments/test_faults.py",
        "experiments/run_validation.py",
        "services/hsi-service/hsi_computer.py",
    ]
    for f_path in fix_files:
        full_path = os.path.join(os.getcwd(), f_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check for various datetime uses
                needs_import = False
                if re.search(r"\bdatetime\.utcnow\(", content) or re.search(
                    r"\bdatetime\.fromisoformat\(", content
                ):
                    if (
                        "import datetime" not in content
                        and "from datetime" not in content
                    ):
                        needs_import = True

                if needs_import:
                    print(f"  - Adding missing datetime import to {f_path}")
                    # Insert after docstring or at top
                    if content.startswith('"""'):
                        end_doc = content.find('"""', 3)
                        if end_doc != -1:
                            new_content = (
                                content[: end_doc + 3]
                                + "\nfrom datetime import datetime\n"
                                + content[end_doc + 3 :]
                            )
                        else:
                            new_content = "from datetime import datetime\n" + content
                    else:
                        new_content = "from datetime import datetime\n" + content

                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
            except Exception as e:
                print(f"  - Failed to fix {f_path}: {e}")

    # 3. Other regex-based E501 fixes
    regex_fixes = [
        {
            "file": "services/shared/shutdown.py",
            "pattern": (
                r'logger\.info\(f"Received signal \{signum\}\. '
                r'Initiating graceful shutdown\.\.\."\)'
            ),
            "replacement": 'logger.info(f"Received signal {signum}. Shutting down...")',
        }
    ]

    for fix in regex_fixes:
        file_path = os.path.join(os.getcwd(), fix["file"])
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = re.sub(fix["pattern"], fix["replacement"], content)
            if new_content != content:
                print(f"  - Applied fix to {fix['file']}")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
        except Exception as e:
            print(f"  - Failed to fix {fix['file']}: {e}")


def main():
    """Runs a suite of auto-formatters to clean up code."""
    print("🚀 Starting comprehensive code formatting...\n")

    # 1. Custom Fixes (Pre-processing)
    fix_custom_issues()

    # 2. Autoflake
    check_and_install("autoflake")
    print("🧹 Running Autoflake...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "autoflake",
            "--in-place",
            "--remove-all-unused-imports",
            "--remove-unused-variables",
            "--recursive",
            ".",
        ],
        check=False,
    )  # nosec B603

    # 3. Isort
    check_and_install("isort")
    print("qh Running Isort...")
    subprocess.run(
        [sys.executable, "-m", "isort", ".", "--profile", "black"], check=False
    )  # nosec B603

    # 4. Docformatter
    check_and_install("docformatter")
    print("qh Running Docformatter...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "docformatter",
            "--in-place",
            "--recursive",
            "--wrap-summaries",
            "88",
            "--wrap-descriptions",
            "88",
            ".",
        ],
        check=False,
    )  # nosec B603

    # 5. Black
    check_and_install("black")
    print("🎨 Running Black...")
    subprocess.run([sys.executable, "-m", "black", "."], check=False)  # nosec B603

    # 6. Prettier
    print("✨ Running Prettier for non-Python files...")
    subprocess.run(
        [
            "npx",
            "prettier",
            "--write",
            "**/*.{md,json,yaml,yml,js,css}",
            "--loglevel",
            "warn",
        ],
        check=False,
        shell=True,
    )  # nosec B602 B603 B607

    print(f"\n{GREEN}✨ All formatters finished! ✨{RESET}")


if __name__ == "__main__":
    main()
