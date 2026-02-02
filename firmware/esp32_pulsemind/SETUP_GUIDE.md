# PulseMind Firmware Setup & Usage Guide

## 1. How It Works (The "Brain" Flow)

The PulseMind system relies on a continuous feedback loop between the hardware (ESP32) and the software (PC Backend).

```mermaid
graph TD
    User((User))
    Sensor[PPG Sensor]
    ESP[ESP32 Firmware]
    MQTT[MQTT Broker (Mosquitto)]
    Brain[PC Backend Services]
    LED[Pacing LED]

    User -->|Pulse| Sensor
    Sensor -->|Analog Signal| ESP
    ESP -->|JSON: {"ppg": 512}| MQTT
    MQTT -->|Topic: sensor/ppg| Brain
    Brain -->|Analysis & Decision| Brain
    Brain -->|JSON: {"rate": 75}| MQTT
    MQTT -->|Topic: pacing/cmd| ESP
    ESP -->|Blink Command| LED
    LED -->|Visual Pacing| User
```

1.  **Sensing**: The ESP32 reads the user's pulse via the PPG sensor (Pin 34).
2.  **Publishing**: It sends this raw data to the `pulsemind/sensor/ppg` topic over WiFi/MQTT.
3.  **Processing**: The backend (Python services) analyzes the stress level and calculates the best breathing/heart rate pattern.
4.  **Commanding**: The backend sends a command back to `pulsemind/pacing/command`.
5.  **Actuating**: The ESP32 receives this command and blinks the LED (Pin 2) to guide the user's breathing.

---

## 2. What To Do (Step-by-Step)

### Step 1: Configure Your Network
The firmware needs to know **your** WiFi capabilities and **your PC's** address.

1.  Open `firmware/esp32_pulsemind/include/Config.h`.
2.  **WiFi**: Change `WIFI_SSID` and `WIFI_PASSWORD` to match your home/lab WiFi.
    ```cpp
    #define WIFI_SSID       "Your_WiFi_Name"
    #define WIFI_PASSWORD   "Your_WiFi_Password"
    ```
3.  **MQTT Broker**: Change `MQTT_BROKER` to your PC's local IP address.
    *   *Windows*: Open CMD, type `ipconfig`, look for "IPv4 Address" (e.g., `192.168.1.5`).
    ```cpp
    #define MQTT_BROKER     "192.168.1.5" // <--- Your PC's IP here
    ```

### Step 2: Setup Prerequisites
1.  **Install an MQTT Broker**: You need a "post office" for messages.
    *   Download and install [Mosquitto](https://mosquitto.org/download/).
    *   Start it (usually runs automatically as a service) or run `mosquitto -v` in a terminal to see logs.
2.  **Connect Hardware**:
    *   **PPG Sensor**: Connect Signal wire to **GPIO 34**.
    *   **LED**: Uses the built-in Blue LED (GPIO 2).

### Step 3: Flash and Monitor
1.  Click the **PlatformIO icon** (Alien face) in VS Code.
2.  Pick **Project Tasks** -> **esp32dev** -> **General** -> **Upload and Monitor**.
3.  The code will compile, upload, and then open the **Serial Monitor**.

### Step 4: Interpret the "Everything" Logs
We enabled verbose logging, so the hardware will tell you exactly what it's doing:

*   `[WiFi] Connecting to...` -> It's trying to get on your network.
*   `[MQTT] Attempting connection...` -> It's trying to find your PC.
*   `[MQTT] > PUB ...` -> **Success!** It is streaming live sensor data.
*   `[Pacing] RX Command` -> **Success!** It received an instruction from the backend.

### Step 5: Run the Backend (Optional for Hardware Test)
To close the loop, you need the Python services running.
1.  Open a new terminal.
2.  Navigate to `services/`.
3.  Run the services (e.g., `python hsi-service/main.py` etc., or use Docker).
