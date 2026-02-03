"""MQTT Verification Utility for Pulse-Mind.

This script verifies that the MQTT broker is operational and that
messages can be published and received correctly.
"""

import time
import json
import paho.mqtt.client as mqtt
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MQTT Settings
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_PACING_CMD = "pulsemind/pacing/cmd"
TOPIC_SENSOR_DATA = "pulsemind/sensor/ppg"

class MqttTester:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.last_received_msg = None
        self.received = False
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
    def _on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logger.info("Connected to MQTT Broker successfully")
            client.subscribe(TOPIC_PACING_CMD)
            client.subscribe(TOPIC_SENSOR_DATA)
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode()
        logger.info(f"Received message on topic {msg.topic}: {payload}")
        self.last_received_msg = payload
        self.received = True

    def test_broker_roundtrip(self, timeout=5):
        """Verify we can publish and receive a message."""
        logger.info("Starting MQTT Roundtrip Test...")
        
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            
            # Publish a test message
            test_payload = {"test": "data", "ts": time.time()}
            logger.info(f"Publishing test message to {TOPIC_SENSOR_DATA}")
            self.client.publish(TOPIC_SENSOR_DATA, json.dumps(test_payload))
            
            # Wait for message to be received
            start_time = time.time()
            while not self.received and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            self.client.loop_stop()
            self.client.disconnect()
            
            if self.received:
                logger.info("✅ MQTT Roundtrip Test Passed!")
                return True
            else:
                logger.error("❌ MQTT Roundtrip Test Timed Out - No message received")
                return False
                
        except Exception as e:
            logger.error(f"❌ MQTT Test Error: {e}")
            return False

if __name__ == "__main__":
    tester = MqttTester()
    if tester.test_broker_roundtrip():
        exit(0)
    else:
        exit(1)
