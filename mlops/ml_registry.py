
import mlflow
import mlflow.pytorch
import os

# --- MLflow Configuration ---
MLFLOW_TRACKING_URI = "sqlite:///mlflow.db"
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("PulseMind_Cardiac_Intelligence")

def log_cardiac_experiment(model_name, metrics, params, model=None, artifact_path=None):
    """
    Logs a heart model's performance to MLflow.
    """
    with mlflow.start_run(run_name=f"{model_name}_Research"):
        # Log Hyperparameters
        mlflow.log_params(params)
        
        # Log Clinical Metrics
        mlflow.log_metrics(metrics)
        
        # Log the actual model weights (PyTorch)
        if model is not None:
            mlflow.pytorch.log_model(model, "model")
            
        # Log extra artifacts (e.g., plots, confusion matrices)
        if artifact_path and os.path.exists(artifact_path):
            mlflow.log_artifact(artifact_path)
            
        run_info = mlflow.active_run().info
        print(f"\033[92m[SUCCESS]\033[0m Experiment Logged: {model_name} | Run ID: {run_info.run_id}")
        return run_info.run_id

if __name__ == "__main__":
    print("PulseMind MLflow Registry Service Initialized.")
    print(f"Tracking Database: {MLFLOW_TRACKING_URI}")
