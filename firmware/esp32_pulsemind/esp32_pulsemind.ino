// Arduino IDE sketch entry for ESP32 PulseMind UART->MQTT bridge.
// This mirrors firmware/esp32_pulsemind/src/main.cpp for Arduino uploads.

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "include/Config.h"

// Serial2 pins for ESP32 (change if you used different pins)
#ifndef ESP32_UART2_RX
#define ESP32_UART2_RX 16
#endif
#ifndef ESP32_UART2_TX
#define ESP32_UART2_TX 17
#endif

WiFiClient espClient;
PubSubClient mqttClient(espClient);

static unsigned long lastPublish = 0;
static const unsigned long PUBLISH_MIN_MS = 10; // max 100 Hz
static unsigned long lastWifiAttempt = 0;
static const unsigned long WIFI_RETRY_MS = 5000;

void connectWiFi() {
  wl_status_t status = WiFi.status();
  if (status == WL_CONNECTED || status == WL_IDLE_STATUS) return;
  unsigned long now = millis();
  if (now - lastWifiAttempt < WIFI_RETRY_MS) return;
  lastWifiAttempt = now;
  Serial.printf("Connecting to WiFi '%s'...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi connection failed");
  }
}

void mqttReconnect() {
  if (mqttClient.connected()) return;
  Serial.printf("Connecting to MQTT broker %s:%d...\n", MQTT_BROKER, MQTT_PORT);
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  unsigned long start = millis();
  while (!mqttClient.connected() && millis() - start < 10000) {
    if (mqttClient.connect(MQTT_CLIENT_ID)) {
      Serial.println("MQTT connected");
      mqttClient.publish(TOPIC_DEVICE_STATUS, "{\"status\":\"connected\"}");
      return;
    }
    Serial.print('x');
    delay(500);
  }
  Serial.println();
}

int extractFirstNumber(const String &s) {
  int len = s.length();
  String num = "";
  bool found = false;
  for (int i = 0; i < len; ++i) {
    char c = s.charAt(i);
    if ((c >= '0' && c <= '9') || c == '-' ) {
      num += c; found = true;
    } else if (found) break;
  }
  if (num.length() == 0) return -1;
  return num.toInt();
}

int parseValueFromLine(String line) {
  line.trim();
  if (line.length() == 0) return -1;

  // If JSON-like, try to find "value" or "ppg" key
  int idx = line.indexOf("\"value\"");
  if (idx < 0) idx = line.indexOf("value");
  if (idx >= 0) {
    // find colon after key
    int colon = line.indexOf(':', idx);
    if (colon >= 0) {
      String num = "";
      for (int i = colon+1; i < line.length(); ++i) {
        char c = line.charAt(i);
        if ((c >= '0' && c <= '9') || c == '-' ) num += c;
        else if (num.length() > 0) break;
      }
      if (num.length()>0) return num.toInt();
    }
  }

  // try ppg key
  idx = line.indexOf("ppg");
  if (idx >= 0) {
    int colon = line.indexOf(':', idx);
    if (colon < 0) colon = line.indexOf('=', idx);
    if (colon >= 0) {
      String num = "";
      for (int i = colon+1; i < line.length(); ++i) {
        char c = line.charAt(i);
        if ((c >= '0' && c <= '9') || c == '-') num += c;
        else if (num.length() > 0) break;
      }
      if (num.length()>0) return num.toInt();
    }
  }

  // try patterns like IR=123 or BPM=72
  int eq = line.indexOf('=');
  if (eq >= 0) {
    // take substring after first '=' and extract first number
    String sub = line.substring(eq+1);
    return extractFirstNumber(sub);
  }

  // fallback: first integer in line
  return extractFirstNumber(line);
}

void processLine(String line) {
  int value = parseValueFromLine(line);
  if (value < 0) return;

  unsigned long now = millis();
  if (now - lastPublish < PUBLISH_MIN_MS) return;
  lastPublish = now;

  char out[64];
  snprintf(out, sizeof(out), "{\"value\":%d,\"ts\":%lu}", value, now);
  if (mqttClient.connected()) {
    bool ok = mqttClient.publish(TOPIC_SENSOR_DATA, out);
    if (!ok) Serial.println("MQTT publish failed");
  } else {
    Serial.println("MQTT not connected, skipping publish");
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP32 PulseMind UART->MQTT Bridge Starting");

  // Start UART2 to receive data from PIC (9600)
  Serial2.begin(9600, SERIAL_8N1, ESP32_UART2_RX, ESP32_UART2_TX);
  delay(50);

  WiFi.mode(WIFI_STA);

  connectWiFi();
  mqttReconnect();

  Serial.printf("Listening on Serial2 (RX=%d, TX=%d)\n", ESP32_UART2_RX, ESP32_UART2_TX);
}

String rxLine = "";

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqttClient.connected()) mqttReconnect();
  mqttClient.loop();

  while (Serial2.available()) {
    char c = (char)Serial2.read();
    if (c == '\r' || c == '\n') {
      if (rxLine.length() > 0) {
        Serial.printf("RX: %s\n", rxLine.c_str());
        processLine(rxLine);
        rxLine = "";
      }
    } else {
      rxLine += c;
      // avoid runaway line length
      if (rxLine.length() > 200) rxLine = rxLine.substring(rxLine.length()-200);
    }
  }

  delay(1);
}
