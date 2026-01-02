#ifndef CONFIG_H
#define CONFIG_H

// ==========================================
// Hardware Configuration
// ==========================================
#define PIN_PPG_SENSOR      34   // ADC1_CH6
#define PIN_PACING_LED      2    // Built-in LED or external LED
#define PIN_STATUS_LED      4    // Optional status LED

// ADC Configuration
#define ADC_SAMPLE_RATE_HZ  100  // Sampling rate for PPG
#define ADC_RESOLUTION_BITS 12

// ==========================================
// Network Configuration
// ==========================================
// Note: In production, use WiFiManager or hardcoded credentials securely
#define WIFI_SSID           "PULSEMIND_LAB"
#define WIFI_PASSWORD       "medical_grade_iot"

// MQTT Configuration
#define MQTT_BROKER         "192.168.1.100" // Replace with actual broker IP
#define MQTT_PORT           1883
#define MQTT_CLIENT_ID      "ESP32_PulseMind_01"

// MQTT Topics
#define TOPIC_SENSOR_DATA   "pulsemind/sensor/ppg"
#define TOPIC_PACING_CMD    "pulsemind/pacing/command"
#define TOPIC_DEVICE_STATUS "pulsemind/device/status"

// ==========================================
// Safety Configuration
// ==========================================
#define WATCHDOG_TIMEOUT_S  5    // Watchdog timeout in seconds
#define MAX_RECONNECT_RETRY 5
#define RECONNECT_DELAY_MS  5000

#endif // CONFIG_H
