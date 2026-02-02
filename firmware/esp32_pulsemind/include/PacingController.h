#ifndef PACING_CONTROLLER_H
#define PACING_CONTROLLER_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include "Config.h"

/**
 * Manages LED output based on pacing commands.
 */
class PacingController {
private:
    uint8_t ledPin;
    bool pacingEnabled;
    float targetRateBpm;
    float amplitudeMs; // Simulated amplitude via PWM duty cycle or duration
    
    unsigned long lastPaceTime;
    unsigned long paceInterval;
    bool ledState;
    unsigned long ledOnTime;
    const unsigned long paceDuration = 20; // 20ms pulse duration

public:
    PacingController(uint8_t pin) : ledPin(pin), pacingEnabled(false), targetRateBpm(60.0), amplitudeMs(0), lastPaceTime(0), ledState(false) {}

    void begin() {
        pinMode(ledPin, OUTPUT);
        digitalWrite(ledPin, LOW);
    }

    /**
     * Process a received pacing command JSON.
     */
    void processCommand(const char* jsonPayload) {
        Serial.print("[Pacing] RX Command: ");
        Serial.println(jsonPayload);

        DynamicJsonDocument doc(512);
        DeserializationError error = deserializeJson(doc, jsonPayload);

        if (error) {
            Serial.print("[Pacing] JSON Parsing Failed: ");
            Serial.println(error.c_str());
            return; // Ignore invalid JSON
        }

        // Extract command fields
        // structure matches control-engine output
        if (doc.containsKey("pacing_command")) {
            JsonObject cmd = doc["pacing_command"];
            pacingEnabled = cmd["pacing_enabled"] | false;
            targetRateBpm = cmd["target_rate_bpm"] | 60.0;
            
            // Safety clamp
            if (targetRateBpm < 30) targetRateBpm = 30;
            if (targetRateBpm > 200) targetRateBpm = 200;
            
            paceInterval = 60000 / targetRateBpm;
            
            Serial.println("[Pacing] Updated Params:");
            Serial.print("  - Enabled: "); Serial.println(pacingEnabled ? "YES" : "NO");
            Serial.print("  - Rate: "); Serial.print(targetRateBpm); Serial.println(" BPM");
            Serial.print("  - Interval: "); Serial.print(paceInterval); Serial.println(" ms");
        } else {
             Serial.println("[Pacing] JSON missing 'pacing_command' key");
        }
    }

    /**
     * Update loop to handle LED timing.
     * Should be called frequently.
     */
    void update() {
        if (!pacingEnabled) {
            if (ledState) {
                digitalWrite(ledPin, LOW);
                ledState = false;
            }
            return;
        }

        unsigned long now = millis();

        // Turn ON LED
        if (!ledState && (now - lastPaceTime >= paceInterval)) {
            digitalWrite(ledPin, HIGH);
            ledState = true;
            lastPaceTime = now;
            ledOnTime = now;
        }
        
        // Turn OFF LED
        if (ledState && (now - ledOnTime >= paceDuration)) {
            digitalWrite(ledPin, LOW);
            ledState = false;
        }
    }
};

#endif // PACING_CONTROLLER_H
