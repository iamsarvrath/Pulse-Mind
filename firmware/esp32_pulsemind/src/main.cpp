#include <Arduino.h>
#include <esp_task_wdt.h>
#include "Config.h"
#include "SensorManager.h"
#include "MqttManager.h"
#include "PacingController.h"

// ==========================================
// Globals
// ==========================================
SensorManager* sensor;
PacingController* pacer;
MqttManager* mqtt;

// ==========================================
// MQTT Callback
// ==========================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    // Convert payload to string
    String msg;
    for (unsigned int i = 0; i < length; i++) {
        msg += (char)payload[i];
    }
    
    // Check topic and route to appropriate controller
    if (String(topic) == TOPIC_PACING_CMD) {
        pacer->processCommand(msg.c_str());
    }
}

// ==========================================
// Setup
// ==========================================
void setup() {
    Serial.begin(115200);
    Serial.println("PulseMind ESP32 Firmware Starting...");

    // Initialize WDT
    esp_task_wdt_init(WATCHDOG_TIMEOUT_S, true);
    esp_task_wdt_add(NULL); // Add current thread

    // Instantiate Managers
    sensor = new SensorManager(PIN_PPG_SENSOR);
    pacer = new PacingController(PIN_PACING_LED);
    mqtt = new MqttManager(pacer);

    // Initialize Hardware
    sensor->begin();
    pacer->begin();
    
    // Initialize Network
    mqtt->setCallback(mqttCallback);
    mqtt->begin();

    Serial.println("System Ready.");
}

// ==========================================
// Main Loop
// ==========================================
void loop() {
    // 1. Service Watchdog
    esp_task_wdt_reset();

    // 2. Update Network
    mqtt->update();

    // 3. Update Pacing Logic (High Priority)
    pacer->update();

    // 4. Sample Sensor
    float ppgValue = 0;
    if (sensor->update(ppgValue)) {
        // Publish Sensor Data
        // Optimization: Don't publish too fast if network is slow
        // For real-time PPG, we typically batch or use UDP, but for this demo MQTT is fine
        // provided latency is acceptable.
        
        static char jsonBuffer[64];
        snprintf(jsonBuffer, sizeof(jsonBuffer), "{\"ppg\":%.2f,\"ts\":%lu}", ppgValue, millis());
        mqtt->publish(TOPIC_SENSOR_DATA, jsonBuffer);
    }
    
    // 5. Short yield to let IDLE task run
    delay(1); 
}
