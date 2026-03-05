
import pandas as pd
import numpy as np
from evidently import Report
from evidently.presets import DataDriftPreset
import os

def check_cardiac_drift(reference_data, current_data, output_path="reports/drift_report.html"):
    """
    Compares real-time PPG features (current) against the medical baseline (reference).
    Checks for statistical shifts in signal patterns.
    """
    if not os.path.exists("reports"):
        os.makedirs("reports")
        
    # Standardize to DataFrames
    df_ref = pd.DataFrame(reference_data)
    df_curr = pd.DataFrame(current_data)
    
    # Run Drift Analysis
    report = Report(metrics=[
        DataDriftPreset(),
    ])
    
    snapshot = report.run(reference_data=df_ref, current_data=df_curr)
    snapshot.save_html(output_path)
    
    # Simplified check: Has drift been detected?
    # In a real system, we'd parse the JSON result for specific p-values.
    print(f"\033[92m[SUCCESS]\033[0m Cardiac Drift Analysis Complete. Report saved to: {output_path}")
    return output_path

if __name__ == "__main__":
    print("PulseMind Drift Detection Service Online.")
    # Example simulation with named features
    features = ["HR", "HRV", "Morph_Score", "HSI", "Signal_Quality"]
    ref = pd.DataFrame(np.random.normal(0, 1, (100, 5)), columns=features)
    curr = pd.DataFrame(np.random.normal(0.5, 1, (100, 5)), columns=features)
    check_cardiac_drift(ref, curr)
