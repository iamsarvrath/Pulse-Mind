import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import time
from datetime import datetime

# ==========================================
# Configuration
# ==========================================
st.set_page_config(
    page_title="PulseMind Dashboard",
    page_icon="💓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Service URLs (Internal Docker Network)
API_GATEWAY_URL = "http://api-gateway:8000"
SIGNAL_SERVICE_URL = "http://signal-service:8001"
HSI_SERVICE_URL = "http://hsi-service:8002"
AI_INFERENCE_URL = "http://ai-inference:8003"
CONTROL_ENGINE_URL = "http://control-engine:8004"


# ==========================================
# Helpers
# ==========================================
def fetch_health_status():
    try:
        response = requests.get(f"{API_GATEWAY_URL}/services", timeout=2)
        if response.status_code == 200:
            return response.json().get("services", {})
    except Exception:
        return {}
    return {}


# ==========================================
# Sidebar
# ==========================================
st.sidebar.title("PulseMind Control")
st.sidebar.markdown("---")

# Signal Controls
st.sidebar.markdown("### Patient Simulation")
signal_type = st.sidebar.selectbox(
    "Rhythm Type",
    [
        "Normal Sinus (75 BPM)",
        "Tachycardia (120 BPM)",
        "Bradycardia (50 BPM)",
        "Noisy / Artifact",
    ],
)

refresh_rate = st.sidebar.slider("Refresh Rate (s)", 0.5, 5.0, 1.0)
auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)

st.sidebar.markdown("---")


def generate_mock_signal(rhythm_type):
    """
    Generate valid PPG signals based on selected type.
    Includes time-shift for animation effect.
    """
    # Create time vector
    fs = 100
    duration = 4  # seconds
    t_now = time.time()
    # Phase shift based on current time to make it look like scrolling data
    phase = (t_now % duration) * 2 * np.pi

    t = np.linspace(0, duration, int(duration * fs))

    # Baseline parameters
    amp = 2000
    dc = 2048
    noise_level = 50

    if "Normal" in rhythm_type:
        freq = 1.25  # 75 BPM
    elif "Tachycardia" in rhythm_type:
        freq = 2.0  # 120 BPM
    elif "Bradycardia" in rhythm_type:
        freq = 0.8  # 48 BPM
    elif "Noisy" in rhythm_type:
        return np.random.normal(dc, 500, len(t)).tolist()
    else:
        freq = 1.0

    # Generate Waveform (Sine + Harmonics for PPG shape)
    # sin(wt + phase)
    signal = np.sin(2 * np.pi * freq * t + phase)
    # Add dicrotic notch approx (harmonic)
    signal += 0.3 * np.sin(4 * np.pi * freq * t + phase)

    # Scale and Offset
    signal = (signal * amp / 2) + dc

    # Add Noise
    noise = np.random.normal(0, noise_level, len(t))
    signal += noise

    return signal.tolist()


st.sidebar.markdown("### System Status")
services_status = fetch_health_status()

for service, info in services_status.items():
    color = "green" if info["status"] == "healthy" else "red"
    st.sidebar.markdown(f":{color}[●] **{service}**")

st.sidebar.markdown("---")
st.sidebar.info("v1.0.0 | Medical-Grade Dashboard")

# ==========================================
# Main Layout
# ==========================================
st.title("💓 PulseMind Clinical Dashboard")

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)

# Placeholder variables
hr_val = "--"
hrv_val = "--"
hsi_score = "--"
rhythm_class = "--"
pacing_status = "Standby"

# Data Fetching Logic (simulated flow for demo)
# In a real app, we'd fetch the latest processed packet.
# Since services are stateless/request-response, the dashboard needs to triggering
# flow or just displaying "last known".
# Here we will TRIGGER a sample process flow to visualize the system working.

try:
    # 1. Generate Signal (Client-side simulation of sensor)
    # real scenario: fetch from DB or cache. Here we simulate "Live Input"
    # 1. Generate Signal (Client-side simulation of sensor)
    # real scenario: fetch from DB or cache. Here we simulate "Live Input"
    raw_signal = generate_mock_signal(signal_type)

    # 2. Call Signal Service
    sig_resp = requests.post(
        f"{SIGNAL_SERVICE_URL}/process",
        json={"signal": raw_signal, "sampling_rate": 100},
        timeout=1,
    )
    if sig_resp.status_code == 200:
        sig_data = sig_resp.json()
        features = sig_data.get("features", {})
        hr_val = f"{features.get('heart_rate_bpm', 0):.1f}"
        hrv_val = f"{features.get('hrv_sdnn_ms', 0):.1f}"

        # 3. Call HSI Service
        hsi_resp = requests.post(
            f"{HSI_SERVICE_URL}/compute-hsi", json={"features": features}, timeout=1
        )
        if hsi_resp.status_code == 200:
            hsi_data = hsi_resp.json()
            # Response structure is {"hsi": {"hsi_score": XX, ...}, ...}
            hsi_result = hsi_data.get("hsi", {})
            hsi_score = f"{hsi_result.get('hsi_score', 0):.1f}"

        # 4. Call AI Inference
        ai_resp = requests.post(
            f"{AI_INFERENCE_URL}/predict", json={"features": features}, timeout=1
        )
        rhythm_data = {}
        if ai_resp.status_code == 200:
            rhythm_data = ai_resp.json().get("prediction", {})
            rhythm_class = rhythm_data.get("rhythm_class", "Unknown")

        # 5. Call Control Engine
        # Need to construct hsi_data payload structure expected by control engine
        if hsi_resp.status_code == 200 and ai_resp.status_code == 200:
            full_hsi_data = hsi_resp.json()  # contains hsi_score and trend
            # Add input_features if missing, Control Engine expects it nested sometimes
            # The control engine expects 'input_features' inside hsi_data?
            # Checked control-engine code: input_features = hsi_data.get("input_features", {})
            # So we add it manually here.
            full_hsi_data["input_features"] = features

            ctrl_resp = requests.post(
                f"{CONTROL_ENGINE_URL}/compute-pacing",
                json={"rhythm_data": rhythm_data, "hsi_data": full_hsi_data},
                timeout=1,
            )
            if ctrl_resp.status_code == 200:
                pacing_cmd = ctrl_resp.json().get("pacing_command", {})
                pacing_status = f"{pacing_cmd.get('pacing_mode', 'off').upper()} @ {pacing_cmd.get('target_rate_bpm', 0)} BPM"

except Exception as e:
    st.error(f"Data Fetch Error: {e}")

# Display Metrics
col1.metric("Heart Rate (BPM)", hr_val, "Normal")
col2.metric("HRV (ms)", hrv_val, "-2.4")
col3.metric("HSI Score", hsi_score, "Stable")
col4.metric("Rhythm Status", rhythm_class, pacing_status)

# ==========================================
# Visualizations
# ==========================================
st.markdown("### Real-time Signal Analysis")
chart_col, info_col = st.columns([2, 1])

with chart_col:
    # Plot PPG
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=raw_signal, mode="lines", name="PPG", line=dict(color="#00ff00", width=2)
        )
    )
    fig.update_layout(
        title="Live PPG Waveform",
        xaxis_title="Time (samples)",
        yaxis_title="Amplitude",
        template="plotly_dark",
        height=350,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

with info_col:
    st.markdown("#### Clinical Decision Support")
    if pacing_status != "Standby":
        st.success(f"**Pacing Active**: {pacing_status}")
        st.markdown(f"**Rationale**: Based on {rhythm_class} and HSI {hsi_score}")
    else:
        st.info("System Standby - Monitoring")

    st.progress(
        float(hsi_score) / 100.0 if hsi_score != "--" else 0.5,
        text="Hemodynamic Stability Index",
    )

# ==========================================
# Auto-Refresh
# ==========================================
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
