# Breadboard Assembly Guide (PulseMind Kit)

This guide is tailored for your specific components: **ESP32 (38-pin)**, **Pulse Sensor**, **Red LED**, and **Resistor**.

## 1. The Setup (Mental Model)
We are building two simple circuits on the breadboard:
1.  **Input**: The Pulse Sensor sends data TO the ESP32 (Pin 34).
2.  **Output**: The ESP32 sends power FROM Pin 2 to light up your Red LED.

---

## 2. Step-by-Step Assembly

### Step A: Mount the ESP32
1.  Place your **ESP32 38-pin board** in the center of the breadboard.
2.  Push it down gently so the pins go into the holes.
3.  **Crucial**: Make sure the middle "ravine" of the breadboard separates the left pins from the right pins.

### Step B: Wire the Pulse Sensor (Input)
Identify the 3 wires on your Pulse Sensor (Amped or Generic):
*   **Red / +** : Power
*   **Black / -** : Ground
*   **Purple / Green / S** : Signal

**Connections:**
1.  **Red Wire** -> Connect to **`3V3`** pin on ESP32.
2.  **Black Wire** -> Connect to **`GND`** pin on ESP32.
3.  **Signal Wire** -> Connect to **`D34`** (labeled `34` or `GPIO34`) on ESP32.
    *   *Note: On a 38-pin board, Pin 34 is usually on the LEFT side, 5th pin down from the USB.*

### Step C: Wire the External Red LED (Output)
We will use **Pin 2** (D2) for this. This pin also controls the blue board light, so both will blink together!

**Components**: Red LED, 220Ω Resistor (Red-Red-Brown).

1.  **Identify LED Legs**:
    *   **Long Leg (+) / Anode**: This side gets the signal.
    *   **Short Leg (-) / Cathode**: This side goes to Ground.

2.  **Wiring**:
    *   **ESP32 Pin 2 (D2)** -> **Jumper Wire** -> **Breadboard Row X**.
    *   **Breadboard Row X** -> **Long Leg (+)** of LED.
    *   **Short Leg (-)** of LED -> **Resistor** -> **Breadboard Power Rail (Blue/-)**.
    *   **Breadboard Power Rail (Blue/-)** -> **Jumper Wire** -> **ESP32 `GND`**.

    *Simplified Direct Version (if leads are long enough)*:
    1.  Plug the **Long Leg (+)** of the LED into the breadboard row connected to **Pin 2**.
    2.  Plug the **Short Leg (-)** into an empty row.
    3.  Bridge that empty row to **GND** using the **Resistor**.

---

## 3. Visual Wiring Checklist

| Component | Pin / Wire | Connects To |
| :--- | :--- | :--- |
| **Pulse Sensor** | **(+) Red** | ESP32 **3V3** |
| **Pulse Sensor** | **(-) Black** | ESP32 **GND** |
| **Pulse Sensor** | **(S) Signal** | ESP32 **Pin 34** |
| | | |
| **Pacing LED** | **(+) Long Leg** | ESP32 **Pin 2** |
| **Pacing LED** | **(-) Short Leg** | **Resistor** (One End) |
| **Resistor** | **Other End** | ESP32 **GND** |

## 4. Troubleshooting
*   **LED is dim?** Check if you used a very high resistance resistor (e.g., 10kΩ) instead of 220Ω. 220Ω is Red-Red-Brown.
*   **LED doesn't light up?** Try flipping the LED around. The Long leg MUST go to Pin 2 (Positive).
*   **Sensor values are random?** Ensure you are using **Pin 34**. Some other pins have WiFi interference. Pin 34 is "ADC1" which is safe.
