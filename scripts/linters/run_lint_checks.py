import subprocess
import sys

def main():
    """Runs Black (check mode) and Flake8."""
    print("running black check...")
    black_result = subprocess.run(["python", "-m", "black", "--check", "services/"], shell=True)
    
    print("\nrunning flake8 check...")
    flake8_cmd = [
        "python", "-m", "flake8", "services/", "--count", 
        "--select=E9,F63,F7,F82", "--show-source", "--statistics"
    ]
    flake8_result = subprocess.run(flake8_cmd, shell=True)

    if black_result.returncode != 0 or flake8_result.returncode != 0:
        print("\n❌ lint checks failed!")
        sys.exit(1)
    
    print("\n✅ all lint checks passed!")

if __name__ == "__main__":
    main()
