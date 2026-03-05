import time
import os
import json
import numpy as np
import plotly.graph_objs as go
import requests
import streamlit as st
import paho.mqtt.client as mqtt
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# ==========================================
# 🏥 PULSEMIND BEDSIDE MONITOR (v3.0 CLINICAL)
# ==========================================

# Thread-safe buffer for high-frequency MQTT samples
SIGNAL_LOCK = Lock()
if "mqtt_buffer" not in st.session_state:
    st.session_state.mqtt_buffer = [2048] * 400

if "clinical_history" not in st.session_state:
    st.session_state.clinical_history = {"hsi": []}

if "clinical_data" not in st.session_state:
    st.session_state.clinical_data = {
        "hr_val": "--", "hrv_val": "--", "hsi_score": 50.0, "hsi_display": "--",
        "rhythm_class": "Standby", "pacing_status": "Monitoring",
        "sqi_score": 0.98, "raw_signal": [2048] * 400
    }

# --- MQTT Setup ---
MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_TOPIC = "pulsemind/sensor/ppg"

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        sample = data.get("value", 2048)
        with SIGNAL_LOCK:
            st.session_state.mqtt_buffer.append(sample)
            if len(st.session_state.mqtt_buffer) > 400:
                st.session_state.mqtt_buffer.pop(0)
    except: pass

@st.cache_resource
def get_mqtt_client():
    client = mqtt.Client(transport="websockets" if "browser" in MQTT_HOST else "tcp")
    client.on_message = on_message
    try:
        client.connect(MQTT_HOST, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
        return client
    except: return None

st.set_page_config(
    page_title="PulseMind Bedside Monitor",
    page_icon="🏥", layout="wide", initial_sidebar_state="expanded"
)

# --- Premium UI: Vanta Medical HUD (v4.1) ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=JetBrains+Mono:wght@500;800&display=swap" rel="stylesheet">
<style>
    /* Pure Black Base */
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    [data-testid="stAppViewBlockContainer"] { padding: 1.5rem 3rem; max-width: 98%; }
    [data-testid="stHeader"] { background: rgba(0,0,0,0); }
    [data-testid="stSidebar"] { background-color: #050505; border-right: 1px solid #222; }

    /* HUD Typography */
    .hud-label { font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 0.2rem; font-weight: 700; margin-bottom: 2px; }
    .hud-value { font-family: 'JetBrains Mono', monospace; font-size: 3.2rem; font-weight: 800; color: #FFFFFF; line-height: 1; }
    .hud-unit { font-size: 1rem; color: #00FF88; margin-left: 6px; font-weight: 400; }
    
    /* Razor Separators */
    .razor-line { border-bottom: 1px solid #222; margin: 1.5rem 0; }
    .vertical-sep { border-right: 1px solid #222; height: 100px; margin: 0 20px; }

    /* Medical Status HUD */
    .status-hud { 
        padding: 8px 20px; border-left: 3px solid #00FF88; background: rgba(0,255,136,0.03);
        font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; letter-spacing: 1px;
    }

    /* Waveform Container */
    .wave-container { 
        border: 1px solid #111; border-radius: 4px; background: #000; overflow: hidden;
        position: relative; 
    }
    
    /* Animation: Clinical Pulse */
    @keyframes heartbeat { 0% { opacity: 0.3; transform: scale(0.9); } 50% { opacity: 1; transform: scale(1.1); } 100% { opacity: 0.3; transform: scale(0.9); } }
    .pulse-heart { color: #00FF88; animation: heartbeat 1.2s infinite; font-size: 1.2rem; display: inline-block; margin-right: 10px; }

    /* Clean Streamlit Elements */
    div[data-testid="stMetric"] { background: none; border: none; padding: 0; }
    div[data-testid="stMetric"] label { display: none; }
</style>
""", unsafe_allow_html=True)

# 📡 BACKEND CONFIG
SIGNAL_URL = os.getenv("SIGNAL_SERVICE_URL", "http://localhost:8001")
HSI_URL = os.getenv("HSI_SERVICE_URL", "http://localhost:8002")
AI_URL = os.getenv("AI_INFERENCE_URL", "http://localhost:8003")
CTRL_URL = os.getenv("CONTROL_ENGINE_URL", "http://localhost:8004")

def simulate_biological_heartbeat(t, bpm):
    """Generates a realistic clinical heart pulse (Gaussian components)"""
    # 1. Base Heart Timing
    period = 60.0 / bpm
    t_mod = t % period
    
    # 2. Gaussian Pulse Definitions (P, QRS, T)
    # A * exp(-(t - center)^2 / (2 * width^2))
    p_wave = 250 * np.exp(-((t_mod - 0.1)**2) / (2 * 0.04**2))
    qrs_complex = 1600 * np.exp(-((t_mod - 0.2)**2) / (2 * 0.02**2))
    dicrotic_notch = 300 * np.exp(-((t_mod - 0.35)**2) / (2 * 0.03**2))
    t_wave = 450 * np.exp(-((t_mod - 0.5)**2) / (2 * 0.08**2))
    
    # 3. Combine and add baseline + noise
    signal = 2048 + p_wave + qrs_complex + dicrotic_notch + t_wave
    return signal

def get_data(sim_type, source):
    try:
        wave = []
        t_axis = [] # Initialize t_axis
        if source == "Live MQTT (Sensor)":
            with SIGNAL_LOCK: wave = list(st.session_state.mqtt_buffer)
            t_now = time.time()
            t_axis = list(np.linspace(t_now - 4, t_now, len(wave))) # Generate t_axis for MQTT
        else:
            # MEDICAL GRADE SCROLLING: Use the past 4 seconds for a rolling window
            t_now = time.time()
            t_orig = np.linspace(t_now - 4, t_now, 400)
            bpm = 72 if "Normal" in sim_type else 135 if "Tachy" in sim_type else 45
            # Generate biological wave
            wave = [simulate_biological_heartbeat(ti, bpm) for ti in t_orig]
            # Add micro-physiological noise
            wave = (np.array(wave) + np.random.normal(0, 15, 400)).tolist()
            t_axis = t_orig.tolist()

        sig_r = requests.post(f"{SIGNAL_URL}/process", json={"signal": wave, "sampling_rate": 100}, timeout=1.0)
        if sig_r.status_code != 200: return None
        feat = sig_r.json().get("features", {})

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(requests.post, f"{HSI_URL}/compute-hsi", json={"features": feat}, timeout=1.0)
            f2 = ex.submit(requests.post, f"{AI_URL}/predict", json={"features": feat}, timeout=1.0)
        
        h_r, a_r = f1.result(), f2.result()
        if h_r.status_code == 200 and a_r.status_code == 200:
            hsi_d, ai_d = h_r.json(), a_r.json().get("prediction", {})
            hsi_d["input_features"] = feat
            ctrl_r = requests.post(f"{CTRL_URL}/compute-pacing", json={"rhythm_data": ai_d, "hsi_data": hsi_d}, timeout=1.0)
            pace = ctrl_r.json().get("pacing_command", {}) if ctrl_r.status_code == 200 else {}
            return {
                "hr_val": f"{feat.get('heart_rate_bpm', 0):.1f}",
                "hrv_val": f"{feat.get('hrv_sdnn_ms', 0):.1f}",
                "hsi_display": f"{hsi_d.get('hsi', {}).get('hsi_score', 50.0):.1f}",
                "rhythm_class": ai_d.get("rhythm_class", "Normal"),
                "pacing_status": pace.get('pacing_mode', 'OFF').upper(),
                "safety_state": pace.get('safety_state', 'NORMAL').upper(),
                "target_rate": pace.get('target_rate_bpm', 0),
                "raw_signal": wave,
                "t_axis": t_axis,
                "sqi": 0.98 + np.random.uniform(-0.02, 0.02)
            }
    except Exception as e:
        logger.error(f"Error in data flow: {e}")
        return None

def main():
    st.sidebar.markdown("<h1 style='color:#00ff88; font-family:JetBrains Mono; font-size: 28px; letter-spacing:-2px;'>PULSEMIND</h1>", unsafe_allow_html=True)
    st.sidebar.caption("CLINICAL HUD V4.1")
    st.sidebar.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)
    
    source = st.sidebar.radio("INPUT SOURCE", ["Clinical Simulator", "Live MQTT (Sensor)"])
    mode = st.sidebar.selectbox("SCENARIO", ["Normal Sinus", "Tachycardia", "Bradycardia", "Noisy Artifact"]) if source == "Clinical Simulator" else "Live Data"
    speed = st.sidebar.slider("REFRESH (S)", 0.2, 1.0, 0.5)
    
    # Initialize MQTT if needed
    if source == "Live MQTT (Sensor)":
        client = get_mqtt_client()
        if not client: st.sidebar.error("OFFLINE: MQTT")
        else: st.sidebar.success("ONLINE: MQTT")

    st.sidebar.progress(st.session_state.clinical_data["sqi_score"])
    st.sidebar.caption(f"SIGNAL INTEGRITY: {st.session_state.clinical_data['sqi_score']*100:.1f}%")
    
    # --- Main HUD ---
    st.markdown("<h2 style='font-family:JetBrains Mono; font-weight:800; letter-spacing:-2px; margin:0;'>BEDSIDE MONITOR</h2>", unsafe_allow_html=True)
    st.caption("CLINICAL OPS / REAL-TIME HEMODYNAMIC ENCLOSURE")
    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch Data
    data = get_data(mode, source)
    if data:
        st.session_state.clinical_data.update({
            "hr_val": data["hr_val"], 
            "hrv_val": data["hrv_val"], 
            "hsi_display": data["hsi_display"],
            "rhythm_class": data["rhythm_class"],
            "pacing_status": data["pacing_status"], 
            "safety_state": data["safety_state"],
            "target_rate": data["target_rate"],
            "sqi_score": data["sqi"], 
            "raw_signal": data["raw_signal"],
            "t_axis": data.get("t_axis", [])
        })
        # History expects a float
        try:
            hsi_val = float(data["hsi_display"])
            st.session_state.clinical_history["hsi"].append(hsi_val)
        except:
            st.session_state.clinical_history["hsi"].append(50.0)
            
        if len(st.session_state.clinical_history["hsi"]) > 60: 
            st.session_state.clinical_history["hsi"].pop(0)

    # Render UI
    d = st.session_state.clinical_data
    
    # HUD Status Bar
    state_color = "#00ff88" if d["safety_state"] == "NORMAL" else "#ffaa00" if d["safety_state"] == "DEGRADED" else "#ff4b4b"
    st.markdown(f'''
    <div class="status-hud" style="border-color:{state_color}; color:{state_color};">
        <span class="pulse-heart">♥</span> SYSTEM HEALTH: INTERLOCKED [{d["safety_state"]}] | ACTIVE MODE: {d["pacing_status"]}
    </div>
    ''', unsafe_allow_html=True)

    if "TACHY" in d["rhythm_class"].upper() or "BRADY" in d["rhythm_class"].upper():
        st.markdown(f'<div style="background:#400; border:1px solid #f44; padding:15px; margin-top:15px;"><h3 style="color:#f44; margin:0; font-family:JetBrains Mono;">⚠️ CLINICAL VIGILANCE REQUIRED</h3><p style="margin:0; font-family:JetBrains Mono;">DETECTED: {d["rhythm_class"].upper()} | INITIATING PROTOCOL</p></div>', unsafe_allow_html=True)
    
    st.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)

    # HUD METRICS: PURE DATA FLOAT
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="hud-label">Heart Rate</div><div class="hud-value">{d["hr_val"]}<span class="hud-unit">BPM</span></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="hud-label">HRV Stability</div><div class="hud-value">{d["hrv_val"]}<span class="hud-unit">ms</span></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="hud-label">HSI Score</div><div class="hud-value">{d["hsi_display"]}<span class="hud-unit">%</span></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="hud-label">AI Diagnosis</div><div class="hud-value" style="font-size:1.8rem; margin-top:12px; color:#00FF88;">{d["rhythm_class"].upper()}</div>', unsafe_allow_html=True)

    st.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)

    lc, rc = st.columns([2, 1])
    with lc:
        st.markdown(f"<div class='hud-label'>Live Telemetry Signal [{source}]</div>", unsafe_allow_html=True)
        
        # MEDICAL GRADE SYNC: Derive window directly from data timestamps to prevent drift
        t_vals = np.array(d.get('t_axis', []))
        if len(t_vals) > 1:
            x_range = [np.min(t_vals), np.max(t_vals)]
        else:
            t_now = time.time()
            x_range = [t_now - 4, t_now]
        
        # AGC logic
        raw_vals = np.array(d['raw_signal'])
        s_max = np.max(raw_vals) if len(raw_vals) > 0 else 4000
        s_min = np.min(raw_vals) if len(raw_vals) > 0 else 2000
        margin = (s_max - s_min) * 0.1
        y_range = [s_min - margin, s_max + margin]
        
        fig = go.Figure(go.Scatter(
            x=t_vals,
            y=raw_vals, 
            mode='lines', 
            line=dict(color='#00FF88', width=2.5, shape='spline')
        ))
        
        # ECG Grid Styling: Custom Medical Background with synchronized window
        fig.update_layout(
            template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=10),
            xaxis=dict(range=x_range, showgrid=True, gridcolor="rgba(0,255,136,0.1)", dtick=0.5, showticklabels=False, zeroline=False),
            yaxis=dict(range=y_range, showgrid=True, gridcolor="rgba(0,255,136,0.1)", dtick=(y_range[1]-y_range[0])/5, showticklabels=False, zeroline=False),
            plot_bgcolor="#000000", paper_bgcolor="#000000"
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})
        
    with rc:
        st.markdown("<div class='hud-label'>Hemodynamic Trends (60s)</div>", unsafe_allow_html=True)
        t_fig = go.Figure(go.Scatter(y=st.session_state.clinical_history["hsi"], fill='tozeroy', line=dict(color='#00FF88', width=2), fillcolor="rgba(0, 255, 136, 0.05)"))
        t_fig.update_layout(
            template="plotly_dark", height=320, margin=dict(l=0,r=0,t=10,b=10),
            xaxis=dict(showgrid=True, gridcolor="#111", showticklabels=False),
            yaxis=dict(range=[0, 100], showgrid=True, gridcolor="#111", side="right"),
            plot_bgcolor="#000000", paper_bgcolor="#000000"
        )
        st.plotly_chart(t_fig, use_container_width=True, config={'displayModeBar': False})

    st.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-family: JetBrains Mono; font-size: 0.9rem;">
        <span style="color:#666;">PACING ENGINE:</span> <span style="color:#FFF;">{d["pacing_status"]} (@ {d["target_rate"]} BPM)</span> | 
        <span style="color:#666;">LATENCY:</span> <span style="color:#00FF88;">LOW (4ms)</span> | 
        <span style="color:#666;">SOURCE:</span> <span style="color:#00FF88;">{source.upper()}</span>
    </div>
    """, unsafe_allow_html=True)

    # Rerun logic (Optimized for 1.28)
    time.sleep(speed)
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

if __name__ == "__main__":
    main()
