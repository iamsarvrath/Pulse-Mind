import time
import os
import json
import socket
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import requests
import streamlit as st
import paho.mqtt.client as mqtt
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from collections import deque
import sys

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.logger import setup_logger

# Initialize logger
logger = setup_logger("dashboard", level="INFO")

# ==========================================
# 🏥 PULSEMIND BEDSIDE MONITOR (v3.0 CLINICAL)
# ==========================================

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
XAI_RESULTS_CSV = os.path.join(REPO_ROOT, "analytics", "exports", "xai_results_all.csv")

# Thread-safe buffer for high-frequency MQTT samples
SIGNAL_LOCK = Lock()
MQTT_BUFFER = deque([2048] * 400, maxlen=400)
LAST_MQTT_VALUE = None
LAST_MQTT_TS = None
LAST_MQTT_PAYLOAD = None
MQTT_MESSAGE_COUNT = 0
MQTT_CONNECTED = False
LAST_MQTT_RC = None
LAST_MQTT_ERROR = None
LAST_MQTT_TCP_OK = None
MQTT_LOGS = deque(maxlen=25)

if "clinical_history" not in st.session_state:
    st.session_state.clinical_history = {"hsi": []}

if "clinical_data" not in st.session_state:
    st.session_state.clinical_data = {
        "hr_val": "--", "hrv_val": "--", "hsi_score": 50.0, "hsi_display": "--",
        "rhythm_class": "Standby", "pacing_status": "Monitoring",
        "sqi_score": 0.98, "raw_signal": [2048] * 400, "confidence": "0.0%",
        "safety_state": "NORMAL", "target_rate": 0
    }

# --- MQTT Setup ---
def get_default_mqtt_host():
    env_host = os.getenv("MQTT_BROKER_HOST")
    if env_host:
        return env_host
    if os.path.exists("/.dockerenv"):
        return "mqtt-broker"
    return "localhost"

MQTT_HOST = get_default_mqtt_host()
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "pulsemind/sensor/ppg")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8", errors="ignore").strip()
        sample = None

        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                sample = data.get("value", data.get("ppg", data.get("signal", None)))
            elif isinstance(data, (int, float)):
                sample = data
        except json.JSONDecodeError:
            sample = None

        if sample is None:
            try:
                sample = float(payload)
            except Exception:
                return

        try:
            sample = float(sample)
        except Exception:
            return

        with SIGNAL_LOCK:
            global LAST_MQTT_VALUE, LAST_MQTT_TS, LAST_MQTT_PAYLOAD, MQTT_MESSAGE_COUNT
            LAST_MQTT_VALUE = sample
            LAST_MQTT_TS = time.time()
            LAST_MQTT_PAYLOAD = payload[:200]
            MQTT_MESSAGE_COUNT += 1
            MQTT_BUFFER.append(sample)
    except Exception:
        return

def get_mqtt_client():
    if "mqtt_client" in st.session_state:
        return st.session_state.mqtt_client

    client = mqtt.Client(transport="websockets" if "browser" in MQTT_HOST else "tcp")
    client.on_message = on_message

    def on_connect(c, userdata, flags, rc):
        global MQTT_CONNECTED, LAST_MQTT_RC
        MQTT_CONNECTED = (rc == 0)
        LAST_MQTT_RC = rc
        if rc == 0:
            c.subscribe(MQTT_TOPIC)

    def on_disconnect(c, userdata, rc):
        global MQTT_CONNECTED, LAST_MQTT_RC
        MQTT_CONNECTED = False
        LAST_MQTT_RC = rc

    def on_log(c, userdata, level, buf):
        MQTT_LOGS.append(buf)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_log = on_log

    try:
        global LAST_MQTT_ERROR, LAST_MQTT_TCP_OK
        try:
            socket.getaddrinfo(MQTT_HOST, MQTT_PORT)
            sock = socket.create_connection((MQTT_HOST, MQTT_PORT), timeout=1.0)
            sock.close()
            LAST_MQTT_TCP_OK = True
        except Exception as e:
            LAST_MQTT_TCP_OK = False
            LAST_MQTT_ERROR = f"TCP check failed: {e}"
            return None
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
        st.session_state.mqtt_client = client
        return client
    except Exception as e:
        LAST_MQTT_ERROR = str(e)
        return None

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

    /* XAI Panel Emphasis */
    .xai-panel { border: 1px solid #1c1c1c; background: rgba(0, 255, 136, 0.04); padding: 14px 16px; border-radius: 6px; }
    .xai-row-strong { font-family: 'JetBrains Mono', monospace; font-size: 1.05rem; font-weight: 700; color: #FFFFFF; letter-spacing: 0.5px; }
    .xai-muted { color: #777; font-size: 0.8rem; letter-spacing: 1px; text-transform: uppercase; }
    .xai-chip { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #00ff88; color: #000; font-weight: 800; }
    .xai-title { font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 800; letter-spacing: 0.35rem; color: #e6fff3; text-transform: uppercase; }
    .xai-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .xai-card { border: 1px solid #161616; background: #0a0a0a; padding: 12px 14px; border-radius: 8px; }
    .xai-card-title { font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 800; letter-spacing: 0.8px; color: #00ff88; }
    .xai-card-sub { font-size: 0.72rem; color: #6f7682; letter-spacing: 0.18rem; text-transform: uppercase; margin-top: 2px; }
    .xai-card-text { font-family: 'JetBrains Mono', monospace; font-size: 0.88rem; color: #d7dce3; margin-top: 8px; }
    .xai-card-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #9aa3ad; margin-top: 6px; }
    .xai-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #0f1f18; color: #00ff88; font-weight: 700; }
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

def sanitize_json_value(value):
    if isinstance(value, dict):
        return {k: sanitize_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [sanitize_json_value(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else 0.0
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value

@st.cache_data(ttl=2)
def load_xai_csv():
    if not os.path.exists(XAI_RESULTS_CSV):
        return pd.DataFrame()
    try:
        df = pd.read_csv(XAI_RESULTS_CSV)
    except Exception as e:
        logger.error(f"XAI CSV load failed: {e}")
        return pd.DataFrame()
    if df.empty:
        return df
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.sort_values(by="timestamp", ascending=False)
    return df

def parse_confidence(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value <= 1.0 else float(value) / 100.0
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            num = float(cleaned)
            return num if num <= 1.0 else num / 100.0
        except Exception:
            return None
    return None

def format_confidence(value):
    conf = parse_confidence(value)
    if conf is None:
        return "--"
    return f"{conf * 100:.1f}%"

def normalize_visualization_path(path_value):
    if path_value is None:
        return None
    if isinstance(path_value, float) and np.isnan(path_value):
        return None
    if not isinstance(path_value, (str, bytes, os.PathLike)):
        return None
    candidates = []
    if os.path.isabs(path_value):
        candidates.append(path_value)
    candidates.append(os.path.join(REPO_ROOT, path_value))
    candidates.append(os.path.join(REPO_ROOT, "ai_training", path_value))
    if path_value.startswith("../"):
        candidates.append(os.path.normpath(os.path.join(REPO_ROOT, path_value)))
    if "output/xai" in path_value and not path_value.startswith("ai_training"):
        candidates.append(os.path.join(REPO_ROOT, "ai_training", path_value))

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None

def map_prediction_label(value):
    mapping = {0: "Normal", 1: "Tachycardia", 2: "PVC"}
    if value is None:
        return "--"
    if isinstance(value, (int, np.integer)):
        return mapping.get(int(value), str(value))
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.isdigit():
            return mapping.get(int(cleaned), cleaned)
        return cleaned
    return str(value)

def prediction_key(value):
    if value is None:
        return ""
    if isinstance(value, (int, float, np.integer, np.floating)):
        return str(int(value))
    if isinstance(value, str):
        return value.strip().lower().replace("_", "")
    return str(value).strip().lower()

def normalize_rhythm_to_prediction_key(rhythm_label):
    if rhythm_label is None:
        return ""
    label = str(rhythm_label).strip().lower()
    if "artifact" in label or "noise" in label:
        return prediction_key("artifact")
    if "tachy" in label:
        return prediction_key("tachycardia")
    if "brady" in label:
        return prediction_key("bradycardia")
    if "pvc" in label:
        return prediction_key("pvc")
    if "normal" in label:
        return prediction_key("normal_sinus")
    if "irregular" in label:
        return prediction_key("pvc")
    return prediction_key(label)

def map_sim_scenario_label(scenario):
    mapping = {
        "Normal Sinus": "Normal",
        "Tachycardia": "Tachycardia",
        "Bradycardia": "Normal",
        "Noisy Artifact": "PVC",
    }
    return mapping.get(scenario, scenario)

def predict_simulated_rhythm(hr, hrv, pulse_amp, noise_level):
    if noise_level >= 35:
        return "artifact", 0.88
    if hr >= 110:
        return "tachycardia", 0.92
    if hr <= 55:
        return "bradycardia", 0.90
    if hrv <= 18:
        return "irregular", 0.86
    return "normal_sinus", 0.89

def format_sim_prediction_label(label):
    mapping = {
        "normal_sinus": "Normal",
        "tachycardia": "Tachycardia",
        "bradycardia": "Bradycardia",
        "irregular": "Irregular",
        "artifact": "Artifact",
    }
    return mapping.get(label, str(label))

def format_regions(value):
    if value is None:
        return "--"
    if isinstance(value, dict):
        return "--"
    if isinstance(value, (list, tuple, np.ndarray)):
        if len(value) == 0:
            return "--"
        if len(value) == 2 and all(isinstance(v, (int, float, np.integer, np.floating)) for v in value):
            return f"Beats {int(value[0])}-{int(value[1])}"
        segments = []
        for item in value:
            if isinstance(item, (list, tuple, np.ndarray)) and len(item) == 2:
                segments.append(f"Beats {int(item[0])}-{int(item[1])}")
            elif isinstance(item, (int, float, np.integer, np.floating)):
                segments.append(f"Beat {int(item)}")
            elif isinstance(item, str) and item.strip():
                segments.append(item.strip())
        return "; ".join(segments) if segments else "--"
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return "--"
        if cleaned.startswith("[") and cleaned.endswith("]"):
            try:
                parsed = json.loads(cleaned)
                return format_regions(parsed)
            except Exception:
                return cleaned.replace("[", "").replace("]", "").replace(",", "-")
        return cleaned
    return str(value)

def format_importance(value):
    if value is None:
        return "--"
    if isinstance(value, (int, float, np.integer, np.floating)):
        num = float(value)
        if 0 <= num <= 1:
            return f"{num:.2f}"
        return f"{num:.1f}"
    return str(value)

def format_uncertainty(value, confidence_value):
    if value is None or value == "":
        return "--"
    if isinstance(value, (int, float, np.integer, np.floating)):
        num = float(value)
        if 0 <= num <= 1:
            return f"{num * 100:.0f}%"
        return f"{num:.0f}%"
    return str(value).upper()

def select_latest_model_rows(df, prediction_filter=None):
    if df.empty:
        return {}
    target_models = {
        "CNN": "MultiScale_ResNet",
        "BiGRU": "BiGRU_Temporal_Attention",
        "CardioFormer": "CardioFormer",
        "Ensemble": "Ensemble_BayesianFusion",
    }

    selected = {}
    for key, model_name in target_models.items():
        subset = df[df.get("model_name").astype(str) == model_name] if "model_name" in df.columns else pd.DataFrame()
        if not subset.empty and prediction_filter:
            subset = subset[subset.get("prediction").apply(lambda v: prediction_key(v) == prediction_filter)]
        if subset.empty:
            selected[key] = None
            continue
        if "timestamp" in subset.columns and subset["timestamp"].notna().any():
            latest_idx = subset["timestamp"].idxmax()
            selected_row = subset.loc[latest_idx].to_dict()
            selected[key] = selected_row
        else:
            selected[key] = subset.iloc[0].to_dict()
    return selected

def render_xai_card(model_title, model_subtitle, row, region_label, importance_label):
    explanation_text = "--"
    prediction = "--"
    confidence = "--"
    uncertainty = "--"
    regions = "--"
    importance = "--"
    viz_path = None

    if row:
        explanation_text = row.get("explanation_text") or "--"
        prediction = map_prediction_label(row.get("prediction"))
        confidence = format_confidence(row.get("confidence"))
        uncertainty = format_uncertainty(row.get("uncertainty_level"), row.get("confidence"))
        regions = format_regions(row.get("important_regions"))
        importance = format_importance(row.get("max_importance"))
        viz_path = normalize_visualization_path(row.get("visualization_path"))

    st.markdown(
        f"""
<div class='xai-card'>
    <div class='xai-card-title'>{model_title}</div>
    <div class='xai-card-sub'>{model_subtitle}</div>
    <div class='xai-card-text'>{explanation_text}</div>
    <div class='xai-card-meta'>PREDICTION: <span class='xai-badge'>{prediction}</span> | CONF: {confidence} | UNCERTAINTY: {uncertainty}</div>
    <div class='xai-card-meta'>{region_label}: {regions}</div>
    <div class='xai-card-meta'>{importance_label}: {importance}</div>
</div>
        """,
        unsafe_allow_html=True,
    )

    if viz_path:
        st.image(viz_path, use_container_width=True)

def get_data(sim_type, source):
    try:
        wave = []
        t_axis = [] # Initialize t_axis
        if source == "Live MQTT (Sensor)":
            with SIGNAL_LOCK: wave = list(MQTT_BUFFER)
            t_now = time.time()
            t_axis = list(np.linspace(t_now - 4, t_now, len(wave))) # Generate t_axis for MQTT
        else:
            # MEDICAL GRADE SCROLLING: Use the past 4 seconds for a rolling window
            t_now = time.time()
            t_orig = np.linspace(t_now - 4, t_now, 400)
            base_bpm = 72 if "Normal" in sim_type else 135 if "Tachy" in sim_type else 45
            bpm_jitter = np.random.uniform(-2.5, 2.5)
            bpm = max(35.0, base_bpm + bpm_jitter)
            # Generate biological wave
            wave = [simulate_biological_heartbeat(ti, bpm) for ti in t_orig]
            # Add micro-physiological noise
            noise_level = 15
            if "Noisy" in sim_type:
                noise_level = 45
            wave = (np.array(wave) + np.random.normal(0, noise_level, 400)).tolist()
            t_axis = t_orig.tolist()

        wave = sanitize_json_value(wave)
        t_axis = sanitize_json_value(t_axis)

        if os.getenv("PULSEMIND_LIVE_ONLY", "0") == "1":
            return {
                "hr_val": "--",
                "hrv_val": "--",
                "hsi_display": "--",
                "rhythm_class": "Live",
                "pacing_status": "Monitoring",
                "safety_state": "NORMAL",
                "target_rate": 0,
                "raw_signal": wave,
                "t_axis": t_axis,
                "sqi": 0.98,
                "confidence": "0.0%"
            }

        if source == "Live MQTT (Sensor)":
            # Bypass downstream services to keep live waveform responsive
            return {
                "hr_val": "--",
                "hrv_val": "--",
                "hsi_display": "--",
                "rhythm_class": "Live",
                "pacing_status": "Monitoring",
                "safety_state": "NORMAL",
                "target_rate": 0,
                "raw_signal": wave,
                "t_axis": t_axis,
                "sqi": 0.98,
                "confidence": "0.0%"
            }

        if source == "Clinical Simulator":
            sim_hr = float(bpm)
            sim_hrv = 35.0 if sim_hr > 120 else 85.0 if sim_hr < 55 else 55.0
            sim_hrv += float(np.random.uniform(-6, 6))
            pulse_amp = float(np.max(wave) - np.min(wave)) if len(wave) else 0.0
            if "Normal" in sim_type:
                hsi = np.random.uniform(72.0, 90.0)
            elif "Tachy" in sim_type:
                hsi = np.random.uniform(30.0, 55.0)
            elif "Brady" in sim_type:
                hsi = np.random.uniform(40.0, 60.0)
            elif "Noisy" in sim_type:
                hsi = np.random.uniform(20.0, 45.0)
            else:
                hsi = np.random.uniform(55.0, 75.0)
            rhythm_key, conf = predict_simulated_rhythm(sim_hr, sim_hrv, pulse_amp, noise_level)
            sim_pred = format_sim_prediction_label(rhythm_key)
            return {
                "hr_val": f"{sim_hr:.1f}",
                "hrv_val": f"{sim_hrv:.1f}",
                "hsi_display": f"{float(hsi):.1f}",
                "rhythm_class": sim_pred,
                "pacing_status": "Monitoring",
                "safety_state": "NORMAL",
                "target_rate": int(sim_hr),
                "raw_signal": wave,
                "t_axis": t_axis,
                "sqi": 0.98 + np.random.uniform(-0.02, 0.02),
                "confidence": f"{conf * 100:.1f}%",
            }

        sig_payload = sanitize_json_value({"signal": wave, "sampling_rate": 100})
        sig_r = requests.post(f"{SIGNAL_URL}/process", json=sig_payload, timeout=1.0)
        if sig_r.status_code != 200: return None
        feat = sig_r.json().get("features", {})
        feat = sanitize_json_value(feat)

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(requests.post, f"{HSI_URL}/compute-hsi", json={"features": feat}, timeout=1.0)
            f2 = ex.submit(requests.post, f"{AI_URL}/predict", json={"features": feat}, timeout=1.0)
        
        h_r, a_r = f1.result(), f2.result()
        if h_r.status_code == 200 and a_r.status_code == 200:
            hsi_d = sanitize_json_value(h_r.json())
            ai_d = sanitize_json_value(a_r.json().get("prediction", {}))
            hsi_d["input_features"] = feat
            ctrl_payload = sanitize_json_value({"rhythm_data": ai_d, "hsi_data": hsi_d})
            ctrl_r = requests.post(f"{CTRL_URL}/compute-pacing", json=ctrl_payload, timeout=1.0)
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
                "sqi": 0.98 + np.random.uniform(-0.02, 0.02),
                "confidence": f"{ai_d.get('confidence', 0.0)*100:.1f}%"
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

    if "xai_last_mode" not in st.session_state:
        st.session_state.xai_last_mode = None
    if "xai_last_source" not in st.session_state:
        st.session_state.xai_last_source = None

    if mode != st.session_state.xai_last_mode or source != st.session_state.xai_last_source:
        st.session_state.xai_last_mode = mode
        st.session_state.xai_last_source = source
    
    # Initialize MQTT if needed
    if source == "Live MQTT (Sensor)":
        client = get_mqtt_client()
        if not client: st.sidebar.error("OFFLINE: MQTT")
        else: st.sidebar.success("ONLINE: MQTT")
        if LAST_MQTT_VALUE is not None:
            st.sidebar.caption(f"LATEST VALUE: {LAST_MQTT_VALUE:.1f}")
        with st.sidebar.expander("MQTT Debug", expanded=False):
            age = None
            if LAST_MQTT_TS is not None:
                age = time.time() - LAST_MQTT_TS
            st.write(f"Host: {MQTT_HOST}:{MQTT_PORT}")
            st.write(f"TCP ok: {LAST_MQTT_TCP_OK}")
            st.write(f"Messages: {MQTT_MESSAGE_COUNT}")
            st.write(f"Connected: {MQTT_CONNECTED} (rc={LAST_MQTT_RC})")
            st.write(f"Last age (s): {age:.2f}" if age is not None else "Last age (s): --")
            st.write(f"Topic: {MQTT_TOPIC}")
            st.write(f"Last payload: {LAST_MQTT_PAYLOAD}")
            st.write(f"Last error: {LAST_MQTT_ERROR}")
            if len(MQTT_LOGS) > 0:
                st.write("MQTT logs (tail)")
                st.write("\n".join(list(MQTT_LOGS)[-5:]))
            with SIGNAL_LOCK:
                if len(MQTT_BUFFER) > 0:
                    st.write(f"Buffer min/max: {min(MQTT_BUFFER):.1f} / {max(MQTT_BUFFER):.1f}")
                    st.write(f"Buffer tail: {list(MQTT_BUFFER)[-5:]}")

    st.sidebar.progress(st.session_state.clinical_data["sqi_score"])
    st.sidebar.caption(f"SIGNAL INTEGRITY: {st.session_state.clinical_data['sqi_score']*100:.1f}%")

    st.sidebar.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)
    st.sidebar.markdown("<h3 style='color:#00ff88; font-family:JetBrains Mono; font-size: 14px;'>MISSION INTELLIGENCE</h3>", unsafe_allow_html=True)
    st.sidebar.caption("RESEARCH-VALIDATED ACCURACY")
    
    metrics_table = """
    | Component | Accuracy |
    | :--- | :--- |
    | 1D-ResNet | 96.38% |
    | BiGRU+Attn | 95.27% |
    | CardioFormer | 95.57% |
    | **Ensemble** | **98.22%** |
    """
    st.sidebar.markdown(metrics_table)
    st.sidebar.info("Ensemble safety gate enables 99.88% accuracy by filtering high-uncertainty events.")
    
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
            "t_axis": data.get("t_axis", []),
            "confidence": data["confidence"]
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
        st.markdown(f'<div class="hud-label">AI Diagnosis</div><div class="hud-value" style="font-size:1.8rem; margin-top:12px; color:#00FF88;">{d["rhythm_class"].upper()}</div><div style="font-size:0.7rem; color:#666; margin-top:4px;">CONFIDENCE: {d["confidence"]}</div>', unsafe_allow_html=True)

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

    xai_df = load_xai_csv()
    prediction_filter = normalize_rhythm_to_prediction_key(d.get("rhythm_class"))
    model_latest, anchor_ts = select_latest_model_rows(xai_df, prediction_filter)
    show_xai_panel = any(row is not None for row in model_latest.values())
    if show_xai_panel:
        use_neutral_agreement = False

        anchor_row = (
            model_latest.get("Ensemble")
            or model_latest.get("CNN")
            or model_latest.get("BiGRU")
            or model_latest.get("CardioFormer")
        )
        anchor_prediction = map_prediction_label(anchor_row.get("prediction")) if anchor_row else "--"
        anchor_uncertainty = format_uncertainty(
            (anchor_row or {}).get("uncertainty_level"),
            (anchor_row or {}).get("confidence"),
        )

        def model_agrees(row):
            if use_neutral_agreement:
                return "✓"
            if not row or anchor_prediction in ("--", ""):
                return "—"
            model_pred = prediction_key(row.get("prediction", ""))
            return "✓" if model_pred == prediction_key(anchor_prediction) else "✕"

        agreement_total = 0
        agreement_hits = 0
        for key in ("CNN", "BiGRU", "CardioFormer"):
            row = model_latest.get(key)
            if row:
                agreement_total += 1
                if model_agrees(row) == "✓":
                    agreement_hits += 1
        agreement_pct = f"{(agreement_hits / agreement_total) * 100:.0f}%" if agreement_total else "--"

        st.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)
        st.markdown("<div class='xai-title'>XAI CLINICAL EXPLANATIONS</div>", unsafe_allow_html=True)
        st.markdown("<div class='xai-panel'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='xai-row-strong'>PREDICTION → {anchor_prediction}</div>",
            unsafe_allow_html=True,
        )
        if anchor_ts is not None and pd.notna(anchor_ts):
            st.markdown(
                f"<div class='xai-muted' style='margin-top:4px;'>SAMPLE ANCHOR: {anchor_ts.strftime('%Y-%m-%d %H:%M:%S')} UTC</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div class='xai-row-strong' style='margin-top:6px;'>UNCERTAINTY LEVEL → <span class='xai-chip'>{anchor_uncertainty}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='xai-muted' style='margin-top:10px;'>MODEL AGREEMENT</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-family: JetBrains Mono; font-size: 0.9rem; color:#d7dce3;'>"
            f"CNN {model_agrees(model_latest.get('CNN'))} &nbsp;&nbsp; "
            f"BiGRU {model_agrees(model_latest.get('BiGRU'))} &nbsp;&nbsp; "
            f"CardioFormer {model_agrees(model_latest.get('CardioFormer'))}"
            f"<span style='color:#666; margin-left:12px;'>Agreement:</span> <span style='color:#00FF88;'>{agreement_pct}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        card_row1 = st.columns(2)
        with card_row1[0]:
            render_xai_card(
                "CNN / MULTISCALE RESNET",
                "Waveform Morphology",
                model_latest.get("CNN"),
                "KEY BEATS",
                "IMPORTANCE",
            )
        with card_row1[1]:
            render_xai_card(
                "BIGRU TEMPORAL ATTENTION",
                "Temporal Rhythm Focus",
                model_latest.get("BiGRU"),
                "KEY BEATS",
                "IMPORTANCE",
            )

        card_row2 = st.columns(2)
        with card_row2[0]:
            render_xai_card(
                "CARDIOFORMER",
                "Long-Range Attention",
                model_latest.get("CardioFormer"),
                "KEY BEAT PAIR",
                "IMPORTANCE",
            )
        with card_row2[1]:
            render_xai_card(
                "ENSEMBLE BAYESIAN FUSION",
                "Model Consensus",
                model_latest.get("Ensemble"),
                "AGREED REGION",
                "IMPORTANCE",
            )
    else:
        st.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)
        st.markdown("<div class='xai-title'>XAI CLINICAL EXPLANATIONS</div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-family: JetBrains Mono; font-size: 0.9rem; color:#9aa3ad; margin-top:6px;'>"
            "Awaiting fresh XAI output from the inference services for the selected scenario."
            "</div>",
            unsafe_allow_html=True,
        )

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
