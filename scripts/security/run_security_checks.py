import subprocess
import sys

def main():
    """Runs Bandit security scan."""
    print("running bandit security scan...")
    # using -r for recursive and -f screen for readable output
    # skipping B104 (hardcoded_bind_all_interfaces) as we need 0.0.0.0 for Docker
    # skipping B301, B403 (pickle) as we use it for ML model loading trusted data
    cmd = [
        "python", "-m", "bandit", "-r", "services/", "-f", "screen",
        "-s", "B104,B301,B403"
    ]
    bandit_result = subprocess.run(cmd, shell=True)
    
    if bandit_result.returncode != 0:
        print("\n❌ security checks failed!")
        sys.exit(1)
    
    print("\n✅ security checks passed!")

if __name__ == "__main__":
    main()
