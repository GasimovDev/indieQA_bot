"""Local developer dashboard for the latest IndieQA run."""
from __future__ import annotations
import json
from pathlib import Path
import sys
from typing import Any
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from analysis.reporter import BugReporter

st.set_page_config(page_title="IndieQA | QA Command Center", page_icon="🔎", layout="wide")
st.title("IndieQA · QA Command Center")
st.caption("Autonomous collision testing · Local telemetry · Reproducible bug evidence")
st.info("Cost assumptions: Human QA $25/hour · IndieQA local compute $0.04/hour. Estimates, not measured savings.")
if st.button("Refresh latest run"):
    st.rerun()


def load_telemetry() -> pd.DataFrame:
    path = ROOT / "data/logs/telemetry.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path).dropna(subset=["pos_x", "pos_y", "frame_id", "timestamp"])
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(f"Telemetry is not ready: {exc}")
        return pd.DataFrame()


def load_bugs() -> list[dict[str, Any]]:
    bugs = []
    for path in sorted((ROOT / "data/reports").glob("bug_*.json")):
        try:
            bug = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(bug, dict) or not {"bug_id", "type", "severity", "coordinates_xyz"} <= bug.keys():
                raise ValueError("Invalid report schema")
            bugs.append(bug)
        except (OSError, ValueError) as exc:
            st.warning(f"Skipped unreadable report {path.name}: {exc}")
    return bugs


telemetry = load_telemetry()
all_bugs = load_bugs()
# Reports from an earlier run must not be presented as current results.
bugs = []
if not telemetry.empty:
    start, end = telemetry.timestamp.min(), telemetry.timestamp.max()
    bugs = [b for b in all_bugs if start <= b.get("timestamp", -1) <= end]
if len(bugs) != len(all_bugs):
    st.warning("Older reports are hidden. Run analysis for the current telemetry to update results.")
seconds = len(telemetry) / 60
hours, remainder = divmod(int(seconds), 3600)
minutes, secs = divmod(remainder, 60)
metrics = st.columns(3)
metrics[0].metric("Simulated Running Time", f"{hours:02}:{minutes:02}:{secs:02}")
metrics[1].metric("Frames Recorded", f"{len(telemetry):,}")
metrics[2].metric("Bugs Detected", len(bugs))

st.subheader("Spatial Coverage & Bug Heatmap")
view = st.radio("Map view", ["Arena (800 × 600)", "Full trajectory"], horizontal=True)
fig, ax = plt.subplots(figsize=(12, 5))
if not telemetry.empty:
    points = telemetry[["pos_x", "pos_y"]].to_numpy(dtype=float)
    points = points[np.isfinite(points).all(axis=1)]
    extent = [[0, 800], [0, 600]] if view.startswith("Arena") else None
    if len(points):
        _, _, _, mesh = ax.hist2d(points[:, 0], points[:, 1], bins=(40, 30), range=extent, cmap="Blues", cmin=1)
        fig.colorbar(mesh, ax=ax, label="Recorded frames per cell")
    if view.startswith("Arena"):
        inside = points[(points[:, 0] >= 0) & (points[:, 0] <= 800) & (points[:, 1] >= 0) & (points[:, 1] <= 600)]
        counts, _, _ = np.histogram2d(inside[:, 0], inside[:, 1], bins=(40, 30), range=[[0, 800], [0, 600]])
        st.caption(f"Visited grid cells: {np.count_nonzero(counts)}/1200. Includes solid geometry; this is spatial occupancy, not reachable-area coverage.")
    coords = [b["coordinates_xyz"] for b in bugs if isinstance(b["coordinates_xyz"], (list, tuple)) and len(b["coordinates_xyz"]) >= 2]
    if coords:
        ax.scatter([p[0] for p in coords], [p[1] for p in coords], c="#ff3344", marker="X", s=65, label="Bug trigger", edgecolors="white", linewidths=.5)
        ax.legend()
    if view.startswith("Arena"):
        ax.set_xlim(0, 800)
        ax.set_ylim(0, 600)
        st.caption("Off-map events remain in the bug log; select Full trajectory to see their coordinates.")
else:
    st.info("Run python main.py --headless --seed 11 --analyze to create telemetry and reports.")
ax.set(xlabel="X (px)", ylabel="Y (px, downward)")
ax.invert_yaxis()
fig.tight_layout()
st.pyplot(fig)
plt.close(fig)

st.subheader("Bug Log")
if bugs:
    severity = st.selectbox("Filter by Severity", ["ALL", "CRITICAL", "HIGH", "MEDIUM"])
    filtered = [b for b in bugs if severity == "ALL" or b["severity"] == severity]
    columns = ["bug_id", "type", "severity", "coordinates_xyz", "frame_id", "timestamp"]
    st.dataframe(pd.DataFrame(filtered, columns=columns))
    markdown = "# IndieQA Diagnostic Report\n\n" + "\n---\n".join(BugReporter.format_markdown(b) for b in filtered)
    left, right = st.columns(2)
    left.download_button("Download Markdown Report", markdown, "indieqa-report.md", "text/markdown")
    right.download_button("Download JSON Reports", json.dumps(filtered, indent=2), "indieqa-reports.json", "application/json")
    if filtered:
        selected = st.selectbox("Inspect reproduction inputs", range(len(filtered)), format_func=lambda i: f"{filtered[i]['type']} · frame {filtered[i].get('frame_id')}")
        st.json(filtered[selected])
    st.caption("For PDF: open the downloaded Markdown in your document viewer and print to PDF.")
else:
    st.info("No reports for this run yet. Run python analysis/run_analysis.py after the simulation finishes.")
