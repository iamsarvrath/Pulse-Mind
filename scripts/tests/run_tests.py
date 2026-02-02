import subprocess
import sys
import os

def main():
    """Runs Pytest unit tests."""
    print("running pytest...")
    
    if not os.path.exists("tests"):
        print("⚠️ tests directory not found. skipping.")
        return

    pytest_result = subprocess.run(["python", "-m", "pytest", "tests/"], shell=True)
    
    if pytest_result.returncode != 0:
        print("\n❌ tests failed!")
        sys.exit(1)
    
    print("\n✅ tests passed!")

if __name__ == "__main__":
    main()
