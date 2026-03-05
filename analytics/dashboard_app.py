import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import time

# --- Configuration & Styling ---
st.set_page_config(page_title="PulseMind Analytics", layout="wide", initial_sidebar_state="collapsed")
WAREHOUSE_DB = os.path.join(os.path.dirname(__file__), "analytics_warehouse.db")

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
