import os
import json

def generate_global_feature_importance():
    # Attempt to import joblib and matplotlib inside the function 
    # to be completely container-safe and avoid import errors on module load.
    try:
        import joblib
    except ImportError:
        print("Error: joblib is not installed. Cannot load the model.")
        return

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Error: matplotlib is not installed. Cannot generate plots.")
        plt = None

    # Define paths relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(current_dir)
    
    model_path = os.path.join(base_dir, "output", "pulsemind_rf_model.pkl")
    output_dir = os.path.join(base_dir, "output", "xai")
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Load trained model
    if not os.path.exists(model_path):
        print(f"Error: Model file not found at {model_path}")
        return
        
    try:
        model = joblib.load(model_path)
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    # Check if the model has feature_importances_
    if not hasattr(model, "feature_importances_"):
        print("Error: The loaded model does not have 'feature_importances_' attribute.")
        return

    importances = model.feature_importances_
    
    # Expected features
    features = ["heart_rate_bpm", "hrv_sdnn_ms", "pulse_amplitude"]
    
    # Map and sort importance values (rounding slightly for cleaner JSON if desired, but float() is required)
    feature_importance_map = []
    for i, feature in enumerate(features):
        if i < len(importances):
            # Using round to 4 decimal places for clean JSON
            feature_importance_map.append({
                "feature": feature,
                "importance": round(float(importances[i]), 4)
            })
    
    # Sort descending
    feature_importance_map.sort(key=lambda x: x["importance"], reverse=True)
    
    # 1. Console Logging
    print("Global Feature Importance Ranking")
    for i, item in enumerate(feature_importance_map, 1):
        # Format exactly as requested
        print(f"{i}. {item['feature']}")
        
    # 2. JSON Output
    json_path = os.path.join(output_dir, "feature_importance.json")
    with open(json_path, 'w') as f:
        json.dump(feature_importance_map, f, indent=2)
    # print(f"Saved JSON to: {json_path}") # Removed extra noisy print for exact match, but let's keep success messages minimal
        
    # 3. Bar Plot
    if plt is not None:
        # Extract data for plotting
        sorted_features = [item["feature"] for item in feature_importance_map]
        sorted_importances = [item["importance"] for item in feature_importance_map]
        
        plt.figure(figsize=(10, 6))
        plt.bar(sorted_features, sorted_importances, color='skyblue')
        plt.xlabel('Features', fontsize=12)
        plt.ylabel('Importance', fontsize=12)
        plt.title('Global Feature Importance', fontsize=14)
        # Ensure features fit well on x-axis
        plt.xticks(rotation=15)
        plt.tight_layout()
        
        png_path = os.path.join(output_dir, "feature_importance.png")
        plt.savefig(png_path)
        plt.close()

if __name__ == "__main__":
    generate_global_feature_importance()
