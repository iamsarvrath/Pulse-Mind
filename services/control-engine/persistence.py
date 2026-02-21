"""Decision Persistence Layer for Control Engine.

This module handles logging all pacing decisions to a local SQLite database
for auditing and verification purposes.
"""

import sqlite3
import os
import json
from datetime import datetime
from shared.logger import setup_logger
from shared.security_utils import encrypt_data, decrypt_data

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
        """Log a decision to the database with PHI encryption."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            pacing_cmd = decision_data.get("pacing_command", {})
            input_summary = decision_data.get("input_summary", {})
            
            # PHI Encryption
            # We encrypt these fields to comply with HIPAA/GDPR
            encrypted_rhythm = encrypt_data(input_summary.get("rhythm_class", "unknown"))
            encrypted_hsi = encrypt_data(str(input_summary.get("hsi_score", 0.0)))
            encrypted_rationale = encrypt_data(pacing_cmd.get("rationale", ""))
            encrypted_payload = encrypt_data(json.dumps(decision_data))

            cursor.execute('''
                INSERT INTO decisions (
                    timestamp, rhythm_class, hsi_score, pacing_mode, 
                    target_rate, rationale, full_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                decision_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                encrypted_rhythm,
                encrypted_hsi,
                pacing_cmd.get("pacing_mode", "off"),
                pacing_cmd.get("target_rate_bpm", 0.0),
                encrypted_rationale,
                encrypted_payload
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log decision: {e}")

    def get_decisions(self, limit=10):
        """Retrieve and decrypt decisions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, rhythm_class, hsi_score, pacing_mode, 
                       target_rate, rationale, full_payload 
                FROM decisions ORDER BY id DESC LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            conn.close()

            decisions = []
            for row in rows:
                decisions.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "rhythm_class": decrypt_data(row[2]),
                    "hsi_score": float(decrypt_data(row[3])),
                    "pacing_mode": row[4],
                    "target_rate": row[5],
                    "rationale": decrypt_data(row[6]),
                    "full_payload": json.loads(decrypt_data(row[7]))
                })
            return decisions
        except Exception as e:
            logger.error(f"Failed to retrieve decisions: {e}")
            return []
