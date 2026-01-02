import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import dataset_builder

def train_model():
    print("Step 1: Loading Dataset...")
    dataset_path = os.path.join(os.path.dirname(__file__), 'output', 'pulsemind_dataset.csv')
    
    if not os.path.exists(dataset_path):
        print("Dataset not found, building it now...")
        df = dataset_builder.build_dataset()
    else:
        df = pd.read_csv(dataset_path)
    
    print(f"Dataset loaded. {len(df)} samples.")
    print("Class distribution:")
    print(df['label'].value_counts())
    
    # Prepare X and y
    feature_cols = ['heart_rate_bpm', 'hrv_sdnn_ms', 'pulse_amplitude']
    X = df[feature_cols]
    y = df['label']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Train
    print("\nStep 2: Training Random Forest Classifier...")
    # Parameters chosen for:
    # - n_estimators=100: good balance of performance/speed
    # - max_depth=10: prevent overfitting to noise/artifacts
    # - class_weight='balanced': handle imbalanced medical data
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    clf.fit(X_train, y_train)
    
    # Evaluate
    print("\nStep 3: Evaluation...")
    print(f"Training Accuracy: {clf.score(X_train, y_train):.4f}")
    print(f"Test Accuracy: {clf.score(X_test, y_test):.4f}")
    
    y_pred = clf.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Cross Validation
    print("\nPerforming Cross Validation...")
    
    # Check minimum class counts
    min_samples = y.value_counts().min()
    if min_samples < 2:
        print("Warning: Some classes have less than 2 samples. Skipping Cross Validation.")
        cv_scores = np.array([clf.score(X_test, y_test)]) # Fallback to test score
    else:
        # Adjust folds based on data size
        n_folds = min(5, min_samples)
        if n_folds < 2:
             n_folds = 2
             
        print(f"Using {n_folds}-fold CV")
        try:
            cv_scores = cross_val_score(clf, X, y, cv=n_folds)
            print(f"CV Accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        except ValueError as e:
            print(f"CV Failed: {e}")
            cv_scores = np.array([0.0])
    
    # Save Model
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    model_path = os.path.join(output_dir, 'pulsemind_rf_model.pkl')
    joblib.dump(clf, model_path)
    print(f"\nModel saved to: {model_path}")
    
    # Save Metadata (Optional but good for tracking)
    metadata = {
        'features': feature_cols,
        'classes': list(clf.classes_),
        'performance': {
            'test_accuracy': clf.score(X_test, y_test),
            'cv_accuracy_mean': cv_scores.mean()
        }
    }
    joblib.dump(metadata, os.path.join(output_dir, 'model_metadata.pkl'))

if __name__ == "__main__":
    train_model()
