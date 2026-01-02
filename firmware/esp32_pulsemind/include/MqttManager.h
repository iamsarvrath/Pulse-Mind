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
    }

    void begin() {
        setupWifi();
    }

    void setupWifi() {
        delay(10);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        
        // Non-blocking wait could be implemented, but typically startup setup blocks
        // For strict non-blocking, we'd check status in loop.
        // We'll keep it simple for startup.
        int retries = 0;
        while (WiFi.status() != WL_CONNECTED && retries < 20) {
            delay(500);
            retries++;
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
        if (client.connect(MQTT_CLIENT_ID)) {
            client.subscribe(TOPIC_PACING_CMD);
            client.publish(TOPIC_DEVICE_STATUS, "{\"status\":\"connected\",\"fw_version\":\"1.0.0\"}");
        }
    }

    bool publish(const char* topic, const char* payload) {
        if (client.connected()) {
            return client.publish(topic, payload);
        }
        return false;
    }
};

#endif // MQTT_MANAGER_H
