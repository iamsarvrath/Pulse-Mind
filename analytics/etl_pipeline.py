import sqlite3
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import importlib.util

# Add 'services' directory to path so persistence.py can import 'shared'
services_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'services'))
sys.path.insert(0, services_path)

# Dynamically import DecisionLogger because folder has hyphen
engine_path = os.path.join(services_path, 'control-engine', 'persistence.py')
spec = importlib.util.spec_from_file_location("persistence", engine_path)
persistence = importlib.util.module_from_spec(spec)
sys.modules['persistence'] = persistence
spec.loader.exec_module(persistence)
DecisionLogger = persistence.DecisionLogger

import mlflow

# Configuration
WAREHOUSE_DB = os.path.join(os.path.dirname(__file__), "analytics_warehouse.db")
MLFLOW_URI = "sqlite:///../mlflow.db"

def init_warehouse():
    """Create the aggregate tables for fast Streamlit querying."""
    conn = sqlite3.connect(WAREHOUSE_DB)
    cursor = conn.cursor()
    
    # Aggregated clinical events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clinical_alerts (
            date TEXT PRIMARY KEY,
            total_pvcs INTEGER,
            tachycardia_events INTEGER,
            bradycardia_events INTEGER,
            total_decisions INTEGER
        )
    ''')
    
    # Operational Model Stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ml_model_stats (
            model_name TEXT PRIMARY KEY,
            accuracy REAL,
            f1_score REAL,
            last_updated TEXT
        )
    ''')
    
    # Store recent raw decisions (decrypted) for the table view
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recent_pacing_history (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            rhythm_class TEXT,
            hsi_score REAL,
            pacing_mode TEXT,
            target_rate REAL,
            rationale TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def load_clinical_data():
    """Extract clinical decisions, decrypt, aggregate, and load."""
    logger = DecisionLogger(db_path="../../services/control-engine/pacing_decisions.db")
    decisions = logger.get_decisions(limit=5000)
    
    if not decisions:
        print("No clinical decisions found to aggregate.")
        # Insert some intelligent mock data if DB is completely empty (for dev/demo purposes)
        decisions = []
        now = datetime.utcnow()
        import random
        rhythms = ['normal_sinus', 'normal_sinus', 'tachycardia', 'PVC', 'bradycardia', 'tachycardia', 'tachycardia']
        modes = ['monitor_only', 'moderate', 'emergency']
        for i in range(150):
            r = random.choice(rhythms)
            p_mode = 'monitor_only' if r == 'normal_sinus' else random.choice(modes[1:])
            decisions.append({
                "id": i,
                "timestamp": (now - timedelta(minutes=i*2)).isoformat(), # more frequent events
                "rhythm_class": r,
                "hsi_score": random.uniform(20.0, 95.0),
                "pacing_mode": p_mode,
                "target_rate": random.uniform(60, 90) if r == 'normal_sinus' else random.uniform(40, 140),
                "rationale": f"Simulated history for dashboard - {r.upper()} Detected"
            })
    
    df = pd.DataFrame(decisions)
    if df.empty:
        return
        
    df['date'] = pd.to_datetime(df['timestamp']).dt.date.astype(str)
    
    # 1. Update aggregations
    aggs = df.groupby('date').agg(
        total_decisions=('id', 'count'),
        total_pvcs=('rhythm_class', lambda x: (x == 'PVC').sum() + (x == 'arrhythmia').sum()),
        tachycardia_events=('rhythm_class', lambda x: (x == 'tachycardia').sum()),
        bradycardia_events=('rhythm_class', lambda x: (x == 'bradycardia').sum())
    ).reset_index()
    
    conn = sqlite3.connect(WAREHOUSE_DB)
    aggs.to_sql('clinical_alerts', conn, if_exists='replace', index=False)
    
    # 2. Update recent raw history
    recent = df.head(100)[['id', 'timestamp', 'rhythm_class', 'hsi_score', 'pacing_mode', 'target_rate', 'rationale']]
    recent.to_sql('recent_pacing_history', conn, if_exists='replace', index=False)
    
    conn.close()
    print("Clinical data ETL complete.")

def load_mlops_data():
    """Extract model metrics from MLflow and load."""
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        client = mlflow.MlflowClient()
        experiments = client.search_experiments()
        
        if not experiments:
            return
            
        exp_id = experiments[0].experiment_id
        runs = mlflow.search_runs(experiment_ids=[exp_id])
        
        if runs.empty:
            return
            
        # Extract latest metrics for models
        model_stats = []
        for _, run in runs.head(10).iterrows():
            tags = run.get('tags.mlflow.source.name', '')
            metrics = {
                'model_name': run.get('tags.mlflow.runName', 'PulseMind Model'),
                'accuracy': run.get('metrics.accuracy', 0.0),
                'f1_score': run.get('metrics.macro_f1', 0.0),
                'last_updated': str(run.get('end_time', pd.Timestamp.now()))
            }
            if metrics['accuracy'] > 0:
                model_stats.append(metrics)
                
        if model_stats:
            df = pd.DataFrame(model_stats).drop_duplicates(subset=['model_name'], keep='first')
            conn = sqlite3.connect(WAREHOUSE_DB)
            df.to_sql('ml_model_stats', conn, if_exists='replace', index=False)
            conn.close()
            print("MLOps data ETL complete.")
    except Exception as e:
        print(f"MLOps extract warning: {e}")

import time

if __name__ == "__main__":
    print("Starting PulseMind Analytics ETL Pipeline in Continuous Mode...")
    init_warehouse()
    while True:
        try:
            load_clinical_data()
            load_mlops_data()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ETL sync complete.")
        except Exception as e:
            print(f"ETL sync error: {e}")
        time.sleep(5)
