import unittest
import sqlite3
import os
import json
import sys
from datetime import datetime

# Add services/control-engine to path for direct testing
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "control-engine")))
from persistence import DecisionLogger

class TestDatabaseIntegration(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_pacing_decisions.db"
        self.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "control-engine", self.db_name))
        
        # Ensure clean state
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        self.logger = DecisionLogger(db_path=self.db_name)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_log_and_retrieve_decision(self):
        """Test logging a decision and verifying it in the DB."""
        test_decision = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "pacing_command": {
                "pacing_enabled": True,
                "target_rate_bpm": 80.0,
                "pacing_mode": "minimal",
                "rationale": "High HSI with slight bradycardia"
            },
            "input_summary": {
                "rhythm_class": "normal_sinus_rhythm",
                "hsi_score": 0.95
            }
        }
        
        # Log it
        self.logger.log_decision(test_decision)
        
        # Verify using the logger's decrypted retrieval
        decisions = self.logger.get_decisions(limit=1)
        self.assertEqual(len(decisions), 1)
        
        decision = decisions[0]
        self.assertEqual(decision["rhythm_class"], "normal_sinus_rhythm")
        self.assertEqual(decision["hsi_score"], 0.95)
        self.assertEqual(decision["pacing_mode"], "minimal")
        self.assertEqual(decision["target_rate"], 80.0)
        self.assertEqual(decision["rationale"], "High HSI with slight bradycardia")
        
        # Verify JSON payload
        self.assertEqual(decision["full_payload"]["pacing_command"]["pacing_mode"], "minimal")

        # Also verify that raw DB access shows encrypted content (for security proof)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT rhythm_class FROM decisions")
        raw_rhythm = cursor.fetchone()[0]
        conn.close()
        self.assertNotEqual(raw_rhythm, "normal_sinus_rhythm")
        self.assertTrue(len(raw_rhythm) > 50) # Fernet tokens are long

if __name__ == "__main__":
    unittest.main()
