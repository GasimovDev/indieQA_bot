import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json

st.set_page_config(page_title="IndieQA Dashboard", layout="wide")

# Section A (Live Header & Metrics)
st.title("IndieQA - Autonomous QA Bug & Collision Hunter")

st.markdown("""
<div style='background-color: #1e1e1e; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>
    <h3 style='margin: 0; color: #4CAF50;'>Economics Comparison</h3>
    <p style='margin: 0;'><strong>Human QA:</strong> $25/hr | <strong>IndieQA:</strong> $0.04/hr</p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

# Mocked running metrics
col1.metric("Running Time", "02:15:30") 

# Load data
LOG_DIR = "data/logs"
REPORT_DIR = "data/reports"

@st.cache_data(ttl=5) # Refresh slightly when possible
def load_telemetry():
    log_path = os.path.join(LOG_DIR, "telemetry.csv")
    if os.path.exists(log_path):
        return pd.read_csv(log_path)
    return pd.DataFrame({'pos_x': [], 'pos_y': []})

@st.cache_data(ttl=5)
def load_bugs():
    bugs = []
    if os.path.exists(REPORT_DIR):
        for file in os.listdir(REPORT_DIR):
            if file.endswith(".json"):
                with open(os.path.join(REPORT_DIR, file), "r", encoding='utf-8') as f:
                    bugs.append(json.load(f))
    return pd.DataFrame(bugs)

telemetry_df = load_telemetry()
bugs_df = load_bugs()

total_frames = len(telemetry_df) if not telemetry_df.empty else 0
col2.metric("Total Frames Analyzed", f"{total_frames:,}")

num_bugs = len(bugs_df) if not bugs_df.empty else 0
col3.metric("Bugs Detected", str(num_bugs))

# Section B (Spatial Coverage Heatmap)
st.header("Spatial Coverage & Bug Heatmap")

fig, ax = plt.subplots(figsize=(10, 6))

if not telemetry_df.empty and 'pos_x' in telemetry_df.columns and 'pos_y' in telemetry_df.columns:
    try:
        sns.kdeplot(
            x=telemetry_df['pos_x'], 
            y=telemetry_df['pos_y'], 
            cmap="Blues", 
            fill=True, 
            bw_adjust=0.5,
            ax=ax
        )
    except Exception as e:
        st.warning(f"Could not generate heatmap: {e}")

if not bugs_df.empty and 'coordinates_xyz' in bugs_df.columns:
    # Scatter bugs
    bug_x = [coord[0] for coord in bugs_df['coordinates_xyz'] if isinstance(coord, (list, tuple))]
    bug_y = [coord[1] for coord in bugs_df['coordinates_xyz'] if isinstance(coord, (list, tuple))]
    
    if bug_x and bug_y:
        ax.scatter(bug_x, bug_y, color='red', s=50, marker='X', label="Detected Bugs")
        ax.legend()

ax.set_title("Exploration Heatmap vs Bug Locations")
ax.set_xlabel("X Coordinate")
ax.set_ylabel("Y Coordinate")
ax.invert_yaxis() # Typical for 2D game coordinates

st.pyplot(fig)

# Section C (Bug Log Table)
st.header("Bug Log Table")

if not bugs_df.empty:
    severity_filter = st.selectbox("Filter by Severity", ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"])
    
    display_df = bugs_df
    if severity_filter != "ALL":
        display_df = bugs_df[bugs_df['severity'] == severity_filter]
        
    cols_to_display = ['bug_id', 'type', 'severity', 'coordinates_xyz', 'timestamp']
    existing_cols = [c for c in cols_to_display if c in display_df.columns]
    
    st.dataframe(display_df[existing_cols], use_container_width=True)
    
    st.subheader("Export Reports")
    export_col1, export_col2 = st.columns(2)
    with export_col1:
        if st.button("Export PDF Report"):
            st.success("PDF Report generation initiated. (Requires PDF export plugin)")
    with export_col2:
        if st.button("Export Markdown Summary"):
            summary = display_df[existing_cols].to_markdown()
            os.makedirs(REPORT_DIR, exist_ok=True)
            with open(os.path.join(REPORT_DIR, "summary.md"), "w", encoding='utf-8') as f:
                f.write(summary)
            st.success("Markdown summary saved to data/reports/summary.md")
else:
    st.info("No bugs detected yet. Run the simulation engine to generate telemetry.")
