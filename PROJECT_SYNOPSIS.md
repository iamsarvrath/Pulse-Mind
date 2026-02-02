# Project Synopsis: Pulse-Mind

## Introduction
Pulse-Mind is an integrated hardware-software ecosystem designed for real-time cardiac monitoring and adaptive pacing. Leveraging readily available ESP32 microcontrollers and standard pulse sensors, it bridges the gap between consumer wearables and medical-grade telemetry. The system captures physiological signals and processes them through a modular microservices architecture to detect arrhythmias and provide immediate feedback via a clinical dashboard.

## Problem Statements
Current cardiac monitoring solutions are often siloed, expensive, or lack real-time analytical depth. Traditional Holter monitors provide retrospective data but fail to offer immediate intervention or predictive insights. Conversely, consumer wearables, while accessible, often suffer from noisy data and simplistic algorithms that miss critical transient events. There is a need for a scalable, cost-effective platform that combines robust data acquisition with AI inference to enable proactive cardiac care.

## Literature Review
Existing literature highlights the efficacy of photoplethysmography (PPG) for detecting heart rate variability (HRV) and arrhythmias. However, most low-cost implementations process data locally with limited computational power, restricting the complexity of analysis. Pulse-Mind addresses these challenges by implementing a hybrid approach: edge-based signal conditioning on the ESP32 for data acquisition, and a containerized microservices suite for heavy-lifting tasks like signal processing and AI inference.

## Objectives
1.  **Hardware Acquisition**: To develop reliable ESP32 firmware that acquires high-fidelity pulse signals and handles basic I/O (Sensors/LEDs).
2.  **Microservices Architecture**: To implement a modular, containerized system (Docker) with specialized services for Signal Processing, Health Status Index (HSI) calculation, and Artificial Intelligence.
3.  **AI Integration**: To integrate Deep Learning models for accurate rhythm classification (Normal, Bradycardia, Tachycardia) and anomaly detection.
4.  **Interactive Dashboard**: To provide a unified Streamlit dashboard for system orchestration, real-time visualization of patient vitals, and simulation of clinical scenarios.
5.  **Adaptive Control**: To implement a safety-critical control engine that evaluates AI outputs and determines appropriate pacing interventions.

## Methodology
The Pulse-Mind system employs a microservices-based processing pipeline orchestrated via REST APIs.
1.  **Data Acquisition**: The ESP32 firmware manages sensor reading and acts as the edge node, capable of publishing data via MQTT.
2.  **Processing Pipeline**: A suite of stateless Flask-based microservices process data in real-time steps:
    -   **Signal Service**: Filters raw PPG data and extracts time-domain features (BPM, HRV).
    -   **HSI Service**: Computes a hemodynamic stability score based on physiological trends.
    -   **AI Inference**: Uses pre-trained models to classify cardiac rhythms.
3.  **Orchestration & Visualization**: The Clinical Dashboard serves as the central control plane. It can trigger analysis pipelines, visualize waveforms, and display pacing recommendations from the Control Engine. Currently, the system supports a "Simulation Mode" where the dashboard provides synthetic data to verify the full software stack.

## System Architecture
1.  **Input Layer** – ESP32 Firmware for PPG sensor data acquisition and MQTT communication.
2.  **Service Layer** – Dockerized RESTful microservices:
    -   `signal-service`: Signal filtering and feature extraction.
    -   `hsi-service`: Health Status Index calculation.
    -   `ai-inference`: Neural network-based rhythm classification.
    -   `control-engine`: Logic-based pacing decision engine.
3.  **Integration Layer** – `api-gateway` (FastAPI) manages routing and load balancing between services; Docker Compose handles container orchestration.
4.  **Presentation Layer** – `dashboard` (Streamlit) provides the user interface for monitoring, simulation, and system verification.
