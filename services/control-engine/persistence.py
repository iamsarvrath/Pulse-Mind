"""Decision Persistence Layer for Control Engine.

This module handles logging all pacing decisions to a local SQLite database
for auditing and verification purposes.
"""

import sqlite3
import os
import json
from datetime import datetime
from shared.logger import setup_logger

logger = setup_logger("decision-logger", level="INFO")

class DecisionLogger:
    """Handles persistence of pacing decisions."""
    
    def __init__(self, db_path="pacing_decisions.db"):
        self.db_path = os.path.join(os.path.dirname(__file__), db_path)
        self._init_db()
        
    def _init_db(self):
        """Initialize the database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    rhythm_class TEXT,
                    hsi_score REAL,
                    pacing_mode TEXT,
                    target_rate REAL,
                    rationale TEXT,
                    full_payload TEXT
                )
            ''')
            conn.commit()
            conn.close()
            logger.info(f"Decision database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def log_decision(self, decision_data):
        """Log a decision to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            pacing_cmd = decision_data.get("pacing_command", {})
            input_summary = decision_data.get("input_summary", {})
            
            cursor.execute('''
                INSERT INTO decisions (
                    timestamp, rhythm_class, hsi_score, pacing_mode, 
                    target_rate, rationale, full_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                decision_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                input_summary.get("rhythm_class", "unknown"),
                input_summary.get("hsi_score", 0.0),
                pacing_cmd.get("pacing_mode", "off"),
                pacing_cmd.get("target_rate_bpm", 0.0),
                pacing_cmd.get("rationale", ""),
                json.dumps(decision_data)
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")
