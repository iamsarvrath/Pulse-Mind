#ifndef MQTT_MANAGER_H
#define MQTT_MANAGER_H

#include <WiFi.h>
#include <PubSubClient.h>
#include "Config.h"
#include "PacingController.h"

/**
 * Manages WiFi and MQTT connections.
 */
class MqttManager {
private:
    WiFiClient espClient;
    PubSubClient client;
    PacingController* pacingController;
    unsigned long lastReconnectAttempt;

    // Callback must be static or global to work with PubSubClient
    // We'll use a functional approach or a simple global wrapper in main if needed,
    // but here we can pass context if we structured it differently.
    // simpler approach: keep the callback logic in main or use a static instance pointer.
    
public:
    MqttManager(PacingController* controller) : client(espClient), pacingController(controller), lastReconnectAttempt(0) {
        client.setServer(MQTT_BROKER, MQTT_PORT);
    }

    void setCallback(MQTT_CALLBACK_SIGNATURE) {
        client.setCallback(callback);
        Serial.println("[MQTT] Callback function registered");
    }

    void begin() {
        setupWifi();
    }

    void setupWifi() {
        delay(10);
        Serial.println();
        Serial.print("[WiFi] Connecting to ");
        Serial.println(WIFI_SSID);
        
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        
        // Non-blocking wait could be implemented, but typically startup setup blocks
        // For strict non-blocking, we'd check status in loop.
        // We'll keep it simple for startup.
        int retries = 0;
        while (WiFi.status() != WL_CONNECTED && retries < 20) {
            delay(500);
            Serial.print(".");
            retries++;
        }

        if (WiFi.status() == WL_CONNECTED) {
            Serial.println("");
            Serial.println("[WiFi] WiFi connected");
            Serial.print("[WiFi] IP address: ");
            Serial.println(WiFi.localIP());
        } else {
            Serial.println("");
            Serial.println("[WiFi] WiFi Connection Failed!");
        }
    }

    void update() {
        if (!client.connected()) {
            unsigned long now = millis();
            if (now - lastReconnectAttempt > RECONNECT_DELAY_MS) {
                lastReconnectAttempt = now;
                reconnect();
            }
        } else {
            client.loop();
        }
    }

    void reconnect() {
        Serial.print("[MQTT] Attempting MQTT connection...");
        // Attempt to connect
        if (client.connect(MQTT_CLIENT_ID)) {
            Serial.println("connected");
            
            // Subscribe to generic topics if needed
            client.subscribe(TOPIC_PACING_CMD);
            Serial.print("[MQTT] Subscribed to: ");
            Serial.println(TOPIC_PACING_CMD);
            
            const char* statusMsg = "{\"status\":\"connected\",\"fw_version\":\"1.0.0\"}";
            client.publish(TOPIC_DEVICE_STATUS, statusMsg);
            Serial.print("[MQTT] Published Status: ");
            Serial.println(statusMsg);
            
        } else {
            Serial.print("failed, rc=");
            Serial.print(client.state());
            Serial.println(" try again in 5 seconds");
        }
    }

    bool publish(const char* topic, const char* payload) {
        if (client.connected()) {
            bool success = client.publish(topic, payload);
            if (success) {
                Serial.print("[MQTT] > PUB [");
                Serial.print(topic);
                Serial.print("]: ");
                Serial.println(payload);
            } else {
                Serial.print("[MQTT] ! PUB FAILED [");
                Serial.print(topic);
                Serial.println("]");
            }
            return success;
        }
        Serial.println("[MQTT] ! Cannot Publish (Disconnected)");
        return false;
    }
};

#endif // MQTT_MANAGER_H
