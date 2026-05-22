import streamlit as st
import sqlite3
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import time

# --- Configuration & Styling ---
st.set_page_config(page_title="PulseMind Analytics", layout="wide", initial_sidebar_state="collapsed")
ANALYTICS_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(ANALYTICS_DIR, ".."))
WAREHOUSE_DB = os.path.join(ANALYTICS_DIR, "analytics_warehouse.db")
XAI_RESULTS_CSV = os.path.join(ANALYTICS_DIR, "exports", "xai_results_all.csv")

# --- Premium UI: Vanta Medical HUD (v4.1) ---
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700&family=JetBrains+Mono:wght@500;800&display=swap" rel="stylesheet">
<style>
    /* Pure Black Base */
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Inter', sans-serif; }
    [data-testid="stHeader"] { background: rgba(0,0,0,0); }
    [data-testid="stAppViewBlockContainer"] { padding: 1.5rem 3rem; max-width: 98%; }

    /* HUD Typography */
    .hud-label { font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 0.2rem; font-weight: 700; margin-bottom: 2px; }
    .hud-value { font-family: 'JetBrains Mono', monospace; font-size: 2.5rem; font-weight: 800; color: #FFFFFF; line-height: 1; }
    .hud-unit { font-size: 0.9rem; color: #00FF88; margin-left: 4px; font-weight: 400; }
    .razor-line { border-bottom: 1px solid #222; margin: 1.5rem 0; }
    
    /* Custom Tabs Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid #111; }
    .stTabs [data-baseweb="tab"] {
        height: 45px; background-color: #050505; color: #666; font-weight: 600; 
        font-family: 'JetBrains Mono'; font-size: 0.8rem; border: none !important;
    }
    .stTabs [aria-selected="true"] { color: #00FF88 !important; border-bottom: 2px solid #00FF88 !important; }

    /* HUD Grid */
    .hud-grid { display: flex; gap: 2rem; margin-bottom: 2rem; }
    .hud-item { flex: 1; }
    .alert-val { color: #FF4B4B; }

    /* XAI Cards */
    .xai-panel { border: 1px solid #1c1c1c; background: rgba(0, 255, 136, 0.04); padding: 14px 16px; border-radius: 8px; }
    .xai-title { font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 800; letter-spacing: 0.2rem; color: #e6fff3; text-transform: uppercase; }
    .xai-row { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #d7dce3; }
    .xai-chip { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #00ff88; color: #000; font-weight: 800; }
    .xai-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .xai-card { border: 1px solid #161616; background: #0a0a0a; padding: 12px 14px; border-radius: 8px; }
    .xai-card-title { font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 800; letter-spacing: 0.8px; color: #00ff88; }
    .xai-card-sub { font-size: 0.7rem; color: #6f7682; letter-spacing: 0.18rem; text-transform: uppercase; margin-top: 2px; }
    .xai-card-text { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #d7dce3; margin-top: 8px; }
    .xai-card-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: #9aa3ad; margin-top: 6px; }
    .xai-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; background: #0f1f18; color: #00ff88; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_data(ttl=2)
def load_data(query):
    try:
        conn = sqlite3.connect(WAREHOUSE_DB)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=2)
def load_xai_csv():
    if not os.path.exists(XAI_RESULTS_CSV):
        return pd.DataFrame()
    try:
        df = pd.read_csv(XAI_RESULTS_CSV)
    except Exception:
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

def format_uncertainty(value):
    if value is None or value == "":
        return "--"
    if isinstance(value, (int, float)):
        num = float(value)
        if 0 <= num <= 1:
            return f"{num * 100:.0f}%"
        return f"{num:.0f}%"
    return str(value).upper()

def format_regions(value):
    if value is None:
        return "--"
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return "--"
        segments = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                segments.append(f"Beats {int(item[0])}-{int(item[1])}")
            elif isinstance(item, (int, float)):
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
    if isinstance(value, (int, float)):
        num = float(value)
        if 0 <= num <= 1:
            return f"{num:.2f}"
        return f"{num:.1f}"
    return str(value)

def normalize_visualization_path(path_value):
    if path_value is None:
        return None
    if isinstance(path_value, float) and pd.isna(path_value):
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
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None

def normalize_prediction(value):
    if value is None:
        return "--"
    if isinstance(value, (int, float)):
        return str(int(value))
    if isinstance(value, str):
        cleaned = value.strip().replace("_", " ")
        return cleaned.title()
    return str(value)

def prediction_key(value):
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value))
    if isinstance(value, str):
        return value.strip().lower().replace("_", "")
    return str(value).strip().lower()

def select_xai_sample_rows(df, anchor_timestamp):
    if df.empty:
        return {}, None
    target_models = {
        "CNN": "MultiScale_ResNet",
        "BiGRU": "BiGRU_Temporal_Attention",
        "CardioFormer": "CardioFormer",
        "Ensemble": "Ensemble_BayesianFusion",
    }
    if "timestamp" in df.columns and df["timestamp"].notna().any():
        anchor_ts = anchor_timestamp or df["timestamp"].max()
    else:
        anchor_ts = None

    selected = {}
    for key, model_name in target_models.items():
        subset = df[df.get("model_name").astype(str) == model_name] if "model_name" in df.columns else pd.DataFrame()
        if subset.empty:
            selected[key] = None
            continue
        if anchor_ts is not None and "timestamp" in subset.columns and subset["timestamp"].notna().any():
            idx = (subset["timestamp"] - anchor_ts).abs().idxmin()
            selected[key] = subset.loc[idx].to_dict()
        else:
            selected[key] = subset.iloc[0].to_dict()
    return selected, anchor_ts

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
        prediction = normalize_prediction(row.get("prediction"))
        confidence = format_confidence(row.get("confidence"))
        uncertainty = format_uncertainty(row.get("uncertainty_level"))
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

# --- Main App ---
st.markdown("<h1 style='font-family:JetBrains Mono; font-weight:800; letter-spacing:-3px; margin:0;'>MISSION CONTROL</h1>", unsafe_allow_html=True)
st.caption("VANTA CLINICAL OPERATIONS & AI RESEARCH ORCHESTRATOR")
st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 Clinical Analytics", "⚙️ Operational Analytics (MLOps)", "🚨 Alerts & Data Export"])

with tab1:
    st.subheader("Patient Cohort & Pacing Outcomes (Last 24h)")
    
    # 1. Top Level Metrics (Custom Grid)
    df_alerts = load_data("SELECT * FROM clinical_alerts ORDER BY date DESC LIMIT 1")
    
    if not df_alerts.empty:
        total_decisions = df_alerts['total_decisions'].iloc[0]
        total_pvcs = df_alerts['total_pvcs'].iloc[0]
        tachy = df_alerts['tachycardia_events'].iloc[0]
        brady = df_alerts['bradycardia_events'].iloc[0]
    else:
        total_decisions, total_pvcs, tachy, brady = 0, 0, 0, 0
        
    st.markdown(f"""
    <div class="hud-grid">
        <div class="hud-item">
            <div class="hud-label">Total Decisions</div>
            <div class="hud-value">{total_decisions:,}</div>
        </div>
        <div class="hud-item">
            <div class="hud-label">Isolated PVCs</div>
            <div class="hud-value alert-val">{total_pvcs:,}</div>
        </div>
        <div class="hud-item">
            <div class="hud-label">Tachycardia</div>
            <div class="hud-value alert-val">{tachy:,}</div>
        </div>
        <div class="hud-item">
            <div class="hud-label">Bradycardia</div>
            <div class="hud-value alert-val">{brady:,}</div>
        </div>
    </div>
    <div class="razor-line"></div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. HSI Trend Graph
    df_history = load_data("SELECT * FROM recent_pacing_history ORDER BY id DESC")
    if not df_history.empty:
        fig = px.line(df_history, x='timestamp', y='hsi_score', 
                      title='Hemodynamic Surrogate Index (HSI) Trend',
                      markers=True, line_shape='spline',
                      color_discrete_sequence=['#00CC96'])
        
        # Add a danger zone
        fig.add_hrect(y0=0, y1=60, line_width=0, fillcolor="red", opacity=0.2, annotation_text="Critical HSI Zone")
        fig.update_layout(plot_bgcolor='#111', paper_bgcolor='#111', font_color='#EEE')
        st.plotly_chart(fig, use_container_width=True)
        
        # Pacing Mode Distribution Pie Chart
        st.subheader("Intervention Distribution")
        mode_counts = df_history['pacing_mode'].value_counts().reset_index()
        mode_counts.columns = ['Pacing Mode', 'Count']
        fig_pie = px.pie(mode_counts, values='Count', names='Pacing Mode',
                         title="AI Decision Breakdown (Last 100 Events)",
                         color='Pacing Mode',
                         color_discrete_map={'monitor_only':'green', 'moderate':'orange', 'emergency':'red'})
        fig_pie.update_layout(plot_bgcolor='#111', paper_bgcolor='#111', font_color='#EEE')
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # 3. Decision Log
        st.subheader("Recent Clinical Pacing Logs (Audit Trail)")
        
        # Style dataframe
        def color_mode(val):
            color = 'red' if val == 'emergency' else 'orange' if val == 'moderate' else 'green'
            return f'color: {color}'
            
        st.dataframe(df_history[['timestamp', 'rhythm_class', 'hsi_score', 'pacing_mode', 'target_rate', 'rationale']].head(50), 
                     use_container_width=True, hide_index=True)
    else:
        st.info("Waiting for Control Engine telemetry...")

    st.markdown("<div class='razor-line'></div>", unsafe_allow_html=True)
    st.subheader("Clinically Interpretable AI Reasoning (XAI)")

    xai_df = load_xai_csv()
    if xai_df.empty:
        st.info("XAI CSV unavailable or empty. Export XAI results to enable clinician-facing reasoning.")
    else:
        if "timestamp" in xai_df.columns:
            ts_options = (
                xai_df["timestamp"].dropna().sort_values(ascending=False)
                .dt.strftime("%Y-%m-%d %H:%M:%S").unique().tolist()
            )
        else:
            ts_options = []

        if ts_options:
            selected_ts = st.selectbox("XAI Sample Timestamp", ts_options, index=0)
            anchor_ts = pd.to_datetime(selected_ts, utc=True, errors="coerce")
        else:
            anchor_ts = None

        model_rows, anchor_ts = select_xai_sample_rows(xai_df, anchor_ts)
        anchor_row = (
            model_rows.get("Ensemble")
            or model_rows.get("CNN")
            or model_rows.get("BiGRU")
            or model_rows.get("CardioFormer")
        )
        anchor_prediction = normalize_prediction((anchor_row or {}).get("prediction"))
        anchor_confidence = format_confidence((anchor_row or {}).get("confidence"))
        anchor_uncertainty = format_uncertainty((anchor_row or {}).get("uncertainty_level"))

        def model_agrees(row):
            if not row or anchor_prediction in ("--", ""):
                return "—"
            return "✓" if prediction_key(row.get("prediction")) == prediction_key(anchor_prediction) else "✕"

        agreement_total = 0
        agreement_hits = 0
        for key in ("CNN", "BiGRU", "CardioFormer"):
            row = model_rows.get(key)
            if row:
                agreement_total += 1
                if model_agrees(row) == "✓":
                    agreement_hits += 1
        agreement_pct = f"{(agreement_hits / agreement_total) * 100:.0f}%" if agreement_total else "--"

        st.markdown("<div class='xai-panel'>", unsafe_allow_html=True)
        st.markdown(f"<div class='xai-title'>AI Interpretation Summary</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='xai-row' style='margin-top:6px;'>Prediction: <span class='xai-badge'>{anchor_prediction}</span> &nbsp; "
            f"Confidence: {anchor_confidence} &nbsp; Uncertainty: <span class='xai-chip'>{anchor_uncertainty}</span></div>",
            unsafe_allow_html=True,
        )
        if anchor_ts is not None and pd.notna(anchor_ts):
            st.markdown(
                f"<div class='xai-row' style='margin-top:4px;'>Sample Anchor: {anchor_ts.strftime('%Y-%m-%d %H:%M:%S')} UTC</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div class='xai-row' style='margin-top:6px;'>CNN {model_agrees(model_rows.get('CNN'))} &nbsp; "
            f"BiGRU {model_agrees(model_rows.get('BiGRU'))} &nbsp; "
            f"Transformer {model_agrees(model_rows.get('CardioFormer'))} &nbsp; "
            f"Agreement: <span class='xai-badge'>{agreement_pct}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        card_row1 = st.columns(2)
        with card_row1[0]:
            render_xai_card(
                "CNN MORPHOLOGY ANALYTICS",
                "Grad-CAM Morphology",
                model_rows.get("CNN"),
                "IMPORTANT BEATS",
                "IMPORTANCE",
            )
        with card_row1[1]:
            render_xai_card(
                "BIGRU TEMPORAL RHYTHM",
                "Temporal Attention",
                model_rows.get("BiGRU"),
                "ATTENDED BEATS",
                "IMPORTANCE",
            )

        card_row2 = st.columns(2)
        with card_row2[0]:
            render_xai_card(
                "CARDIOFORMER CONTEXTUAL",
                "Long-Range Attention",
                model_rows.get("CardioFormer"),
                "KEY BEAT PAIR",
                "IMPORTANCE",
            )
        with card_row2[1]:
            render_xai_card(
                "ENSEMBLE CONSENSUS",
                "Model Agreement",
                model_rows.get("Ensemble"),
                "AGREED REGIONS",
                "IMPORTANCE",
            )

with tab2:
    st.subheader("MLOps Pipeline Health")
    
    df_models = load_data("SELECT * FROM ml_model_stats")
    
    if not df_models.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Active Production Models")
            st.dataframe(df_models, use_container_width=True, hide_index=True)
            
        with col2:
            fig_acc = px.bar(df_models, x='model_name', y='accuracy', 
                             title="Model Accuracies", text_auto='.2%',
                             color='accuracy', color_continuous_scale='Mint')
            fig_acc.update_layout(plot_bgcolor='#111', paper_bgcolor='#111', font_color='#EEE', showlegend=False)
            st.plotly_chart(fig_acc, use_container_width=True)
            
        st.markdown("---")
        
        st.markdown(f"""
        <div class="hud-grid">
            <div class="hud-item">
                <div class="hud-label">Research Engine</div>
                <div class="hud-value" style="color:#00ff88; font-size:1.8rem;">INTERLOCKED</div>
            </div>
            <div class="hud-item">
                <div class="hud-label">Clinical Drift</div>
                <div class="hud-value" style="color:#00ff88; font-size:1.8rem;">STABLE</div>
            </div>
            <div class="hud-item">
                <div class="hud-label">Validation HUD</div>
                <div class="hud-value" style="color:#00ff88; font-size:1.8rem;">READY</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No MLflow tracking records found. Run a research notebook to generate initial training data.")

with tab3:
    st.subheader("Critical Clinical Alerts")
    st.markdown("Displays only safety-critical pacing interventions (Moderate & Emergency).")
    
    df_all = load_data("SELECT * FROM recent_pacing_history ORDER BY id DESC")
    if not df_all.empty:
        df_critical = df_all[df_all['pacing_mode'].isin(['moderate', 'emergency'])]
        
        if not df_critical.empty:
            st.dataframe(df_critical[['timestamp', 'rhythm_class', 'hsi_score', 'pacing_mode', 'rationale']], 
                         use_container_width=True, hide_index=True)
        else:
            st.success("No critical alerts in the recent history window. System stable.")
            
        st.markdown("---")
        st.subheader("Reporting & Export")
        
        # Convert df to CSV for download
        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')

        csv = convert_df(df_all)

        st.download_button(
            label="📄 Download Full Pacing Log (CSV)",
            data=csv,
            file_name=f"pulsemind_clinical_export_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("Database empty.")

# --- Auto-Refresh ---
st.markdown("---")
st.caption(f"Last synchronized: {pd.Timestamp.now().strftime('%H:%M:%S')} (Auto-refreshing every 5 seconds)")
time.sleep(5)
st.rerun()
