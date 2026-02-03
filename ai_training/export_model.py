import os
import shutil
import sys


def export_model():
    # Source
    src_dir = os.path.join(os.path.dirname(__file__), "output")
    model_name = "pulsemind_rf_model.pkl"
    src_path = os.path.join(src_dir, model_name)

    # Destination
    # Navigate up from ai_training/export_model.py to root, then to services
    dest_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "services", "ai-inference", "models"
        )
    )
    dest_path = os.path.join(dest_dir, model_name)

    print(f"Source: {src_path}")
    print(f"Destination: {dest_path}")

    if not os.path.exists(src_path):
        print("Error: Source model not found. Run train_model.py first.")
        sys.exit(1)

    if not os.path.exists(dest_dir):
        print(f"Creating destination directory: {dest_dir}")
        os.makedirs(dest_dir, exist_ok=True)

    try:
        shutil.copy2(src_path, dest_path)
        print("Model exported successfully!")

        # Verify
        if os.path.exists(dest_path):
            size = os.path.getsize(dest_path)
            print(f"Verified export. File size: {size} bytes")
        else:
            print("Error: Verification failed. File not found at destination.")
            sys.exit(1)

    except Exception as e:
        print(f"Error exporting model: {e}")
        sys.exit(1)


if __name__ == "__main__":
    export_model()
