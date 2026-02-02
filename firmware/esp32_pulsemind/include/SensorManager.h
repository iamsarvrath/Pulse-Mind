#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include <Arduino.h>
#include "Config.h"

/**
 * Manages PPG sensor sampling and basic signal conditioning.
 */
class SensorManager {
private:
    uint8_t pin;
    unsigned long lastSampleTime;
    unsigned long sampleInterval;
    
    // Basic signal conditioning
    const int bufferSize = 5;
    int* buffer;
    int bufferIndex;
    int bufferSum;

public:
    SensorManager(uint8_t ppgPin) : pin(ppgPin), lastSampleTime(0), bufferIndex(0), bufferSum(0) {
        sampleInterval = 1000 / ADC_SAMPLE_RATE_HZ;
        buffer = new int[bufferSize];
        for (int i = 0; i < bufferSize; i++) buffer[i] = 0;
    }

    ~SensorManager() {
        delete[] buffer;
    }

    void begin() {
        pinMode(pin, INPUT);
        analogReadResolution(ADC_RESOLUTION_BITS);
        Serial.print("[Sensor] Initialized PPG on Pin: ");
        Serial.println(pin);
    }

    /**
     * Samples the sensor if enough time has passed.
     * Returns true if a new sample is available.
     */
    bool update(float &value) {
        unsigned long now = millis();
        if (now - lastSampleTime >= sampleInterval) {
            lastSampleTime = now;
            
            // Read raw value
            int raw = analogRead(pin);
            
            // Moving average filter
            bufferSum -= buffer[bufferIndex];
            buffer[bufferIndex] = raw;
            bufferSum += buffer[bufferIndex];
            bufferIndex = (bufferIndex + 1) % bufferSize;
            
            // Return averaged value
            value = (float)bufferSum / bufferSize;
            return true;
        }
        return false;
    }
};

#endif // SENSOR_MANAGER_H
