import os

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


def evaluate():
    print("Loading resources...")
    model_path = os.path.join(
        os.path.dirname(__file__), "output", "pulsemind_rf_model.pkl"
    )
    dataset_path = os.path.join(
        os.path.dirname(__file__), "output", "pulsemind_dataset.csv"
    )

    if not os.path.exists(model_path):
        print(f"Error: Model not found at {model_path}")
        return

    if not os.path.exists(dataset_path):
        print(f"Error: Dataset not found at {dataset_path}")
        return

    # Load
    clf = joblib.load(model_path)
    df = pd.read_csv(dataset_path)

    # Prepare
    feature_cols = ["heart_rate_bpm", "hrv_sdnn_ms", "pulse_amplitude"]
    X = df[feature_cols]
    y = df["label"]

    # Split (Same seed as training to ensure we are looking at the test set
    # if we were rigorous,
    # but here we just re-split to get a 'test' set.
    # ideal but re-splitting with same seed is acceptable for this scope)
    # Ideally train_model should save X_test/y_test,
    # but re-splitting with same seed is acceptable for this scope)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\n--- Model Evaluation Report ---")
    y_pred = clf.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    print(f"Overall Accuracy: {acc:.4f}")

    print("\nDetailed Classification Report:")
    report = classification_report(y_test, y_pred)
    print(report)

    # Save report to file
    report_path = os.path.join(
        os.path.dirname(__file__), "output", "evaluation_report.txt"
    )
    with open(report_path, "w") as f:
        f.write("PulseMind AI Model Evaluation\n")
        f.write(f"Accuracy: {acc:.4f}\n\n")
        f.write("Classification Report:\n")
        f.write(report)

    print(f"Report saved to {report_path}")

    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred, labels=clf.classes_)
    print("\nConfusion Matrix:")
    print(cm)
    print(f"Classes: {clf.classes_}")


if __name__ == "__main__":
    evaluate()
