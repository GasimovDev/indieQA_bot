"""IndieQA backup website (branch backup-plan1).

    streamlit run dashboard/backup_site.py

Reads data/logs/telemetry.csv (written live by main.py), runs Person 2's
detector on it, and shows: cost banner, KPIs, level map with bug locations,
a "fix first" priority board, per-bug screenshots with reproduction steps,
and an exportable bug log. Refreshes automatically while the bot is playing.
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import streamlit as st

from core.engine import FPS, build_level
from dashboard.insights import (
    BORDER,
    CARD,
    GREEN,
    GREEN_SOFT,
    INK,
    MUTED,
    RED,
    RED_SOFT,
    SEVERITY_WEIGHT,
    TIER_COLOURS,
    TIERS,
    TYPE_BLURB,
    Analysis,
    Issue,
    analyse,
    bug_markdown,
    format_game_time,
    load_telemetry,
    render_map,
    render_snapshot,
)

CSV_PATH = ROOT / "data" / "logs" / "telemetry.csv"
HUMAN_RATE = 25.0
INDIEQA_RATE = 0.04
DEMO_SEED = 11

st.set_page_config(page_title="IndieQA · QA Report", page_icon="🧪", layout="wide")

st.markdown(
    f"""
<style>
header[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1420px; }}
.iq-card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 16px 18px; }}
.iq-brand {{ font-size: 2.1rem; font-weight: 800; color: {INK}; letter-spacing: -0.02em; line-height: 1; }}
.iq-brand span {{ color: {RED}; }}
.iq-sub {{ color: {MUTED}; font-size: 0.95rem; margin-top: 4px; }}
.iq-status {{ display: inline-block; padding: 5px 12px; border-radius: 999px; font-weight: 700; font-size: 0.8rem; }}
.iq-live {{ background: {GREEN_SOFT}; color: {GREEN}; }}
.iq-idle {{ background: #EFE6D2; color: {MUTED}; }}
.iq-banner {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px;
  background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; padding: 14px 22px; margin: 6px 0 14px 0; }}
.iq-banner .human {{ color: {RED}; font-weight: 700; font-size: 1.15rem; }}
.iq-banner .human s {{ opacity: .75; }}
.iq-banner .bot {{ color: {GREEN}; font-weight: 800; font-size: 1.6rem; }}
.iq-banner .mid {{ color: {MUTED}; font-size: .92rem; }}
.iq-kpi-label {{ color: {MUTED}; font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; font-weight: 700; }}
.iq-kpi-value {{ color: {INK}; font-size: 1.75rem; font-weight: 800; margin-top: 2px; }}
.iq-kpi-note {{ color: {MUTED}; font-size: .78rem; }}
.iq-h {{ font-size: 1.15rem; font-weight: 800; color: {INK}; margin: 2px 0 2px 0; }}
.iq-hsub {{ color: {MUTED}; font-size: .85rem; margin-bottom: 10px; }}
.iq-issue {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; padding: 11px 14px; margin-bottom: 9px; }}
.iq-issue .top {{ display: flex; align-items: center; gap: 8px; }}
.iq-issue .name {{ font-weight: 800; color: {INK}; font-size: 1.02rem; }}
.iq-issue .count {{ margin-left: auto; font-weight: 800; font-size: 1.25rem; color: {INK}; }}
.iq-issue .loc {{ color: {INK}; font-size: .86rem; margin-top: 3px; }}
.iq-issue .meta {{ color: {MUTED}; font-size: .78rem; margin-top: 2px; }}
.iq-pill {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-weight: 800; font-size: .75rem; color: #fff; }}
.iq-bar {{ height: 5px; border-radius: 4px; background: #EFE6D2; margin-top: 7px; overflow: hidden; }}
.iq-bar > div {{ height: 5px; border-radius: 4px; }}
.iq-symptom {{ color: {MUTED}; font-size: .82rem; padding: 4px 2px; }}
.iq-chips {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 6px; }}
.iq-chip {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; padding: 5px 6px; text-align: center; }}
.iq-chip .n {{ color: {MUTED}; font-size: .66rem; }}
.iq-chip .k {{ color: {INK}; font-weight: 700; font-size: .86rem; }}
.iq-chip.last {{ border-color: {RED}; background: {RED_SOFT}; }}
.iq-facts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }}
.iq-fact {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; padding: 8px 12px; }}
.iq-fact .l {{ color: {MUTED}; font-size: .68rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }}
.iq-fact .v {{ color: {INK}; font-weight: 700; font-size: .95rem; }}
.iq-empty {{ text-align: center; padding: 48px 20px; }}
</style>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------ data
def file_signature() -> tuple[int, int] | None:
    try:
        stat = CSV_PATH.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


@st.cache_data(max_entries=4, show_spinner=False)
def load(signature: tuple[int, int]) -> tuple[pd.DataFrame, Analysis] | None:
    try:
        df = load_telemetry(str(CSV_PATH))
    except (pd.errors.EmptyDataError, KeyError, ValueError):
        return None
    return df, analyse(df, build_level())


@st.cache_data(max_entries=4, show_spinner=False)
def map_png(signature: tuple[int, int]) -> bytes | None:
    data = load(signature)
    if data is None:
        return None
    df, analysis = data
    return render_map(df, analysis.issues, build_level())


@st.cache_data(max_entries=64, show_spinner=False)
def snapshot(signature: tuple[int, int], event_index: int, zoom: bool) -> np.ndarray | None:
    data = load(signature)
    if data is None:
        return None
    df, analysis = data
    event = next((e for e in analysis.events if e.index == event_index), None)
    return None if event is None else render_snapshot(df, event, build_level(), zoom=zoom)


# --------------------------------------------------------------- helpers
def pill(tier: str) -> str:
    return f'<span class="iq-pill" style="background:{TIER_COLOURS[tier]}">{tier}</span>'


def key_label(token: str) -> str:
    glyphs = {"left": "←", "right": "→", "jump": "⤒ jump", "none": "·"}
    return " + ".join(glyphs.get(part, html.escape(part)) for part in token.split("+"))


def bot_process() -> subprocess.Popen[bytes] | None:
    proc = st.session_state.get("bot_proc")
    return proc if proc is not None and proc.poll() is None else None


def start_bot(args: list[str]) -> None:
    if bot_process() is not None:
        st.toast("The bot is already running.")
        return
    st.session_state.bot_proc = subprocess.Popen(
        [sys.executable, "main.py", *args], cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    st.toast("Bot started - the report updates by itself.")


# ---------------------------------------------------------------- header
head_l, head_r = st.columns([3, 2], vertical_alignment="center")
with head_l:
    st.markdown(
        '<div class="iq-brand">Indie<span>QA</span></div>'
        '<div class="iq-sub">Autonomous QA report · the bot plays your level and tells you what to fix first</div>',
        unsafe_allow_html=True,
    )
with head_r:
    b1, b2 = st.columns(2)
    if b1.button(f"▶ Watch the bot play (seed {DEMO_SEED})", width="stretch", type="primary"):
        start_bot(["--seed", str(DEMO_SEED)])
    if b2.button("⚡ Run a 10-min test (fast)", width="stretch"):
        start_bot(["--headless", "--frames", "36000", "--analyze"])
    auto = st.toggle("Auto-refresh (live)", value=True, help="Re-reads the telemetry every 2 seconds")


# ------------------------------------------------------------------ body
def body() -> None:
    signature = file_signature()
    running = bot_process() is not None
    data = load(signature) if signature else None

    if data is None or data[1].frames == 0:
        st.markdown(
            f'<div class="iq-card iq-empty"><div class="iq-h">No test data yet</div>'
            f'<div class="iq-hsub">Press <b>▶ Watch the bot play</b> above, or run '
            f"<code>python main.py --seed {DEMO_SEED}</code> in a terminal.</div></div>",
            unsafe_allow_html=True,
        )
        return
    df, analysis = data
    roots = [i for i in analysis.issues if i.symptom_of is None]
    symptoms = [i for i in analysis.issues if i.symptom_of is not None]
    p0 = sum(1 for i in roots if i.tier == "P0")
    minutes = analysis.game_minutes

    status = (
        '<span class="iq-status iq-live">● LIVE · bot is playing</span>'
        if running
        else f'<span class="iq-status iq-idle">Last run · {analysis.frames:,} frames</span>'
    )
    st.markdown(
        f"""<div class="iq-banner">
  <div class="human">Human QA <s>${HUMAN_RATE:.0f}/h</s></div>
  <div class="mid">{status}&nbsp;&nbsp; This run tested <b>{format_game_time(analysis.frames)}</b> of gameplay ·
  a human would cost <b>${minutes / 60 * HUMAN_RATE:.2f}</b> for it</div>
  <div class="bot">IndieQA ${INDIEQA_RATE:.2f}/h</div>
</div>""",
        unsafe_allow_html=True,
    )

    kpis = [
        ("Game time tested", format_game_time(analysis.frames), f"{FPS} frames per second"),
        ("Frames analysed", f"{analysis.frames:,}", "every frame checked"),
        ("Problems to fix", str(len(roots)), "unique root causes"),
        ("Bug events", str(len(analysis.events)), f"{sum(i.count for i in symptoms)} are side effects"),
        ("P0 · fix before launch", str(p0), "highest priority"),
        ("Ground covered", f"{analysis.coverage_pct:.0f}%",
         f"{analysis.surface_bins_visited}/{analysis.surface_bins_total} walkable sections"),
    ]
    for col, (label, value, note) in zip(st.columns(len(kpis)), kpis):
        accent = f"color:{TIER_COLOURS['P0']}" if label.startswith("P0") and value != "0" else ""
        col.markdown(
            f'<div class="iq-card"><div class="iq-kpi-label">{label}</div>'
            f'<div class="iq-kpi-value" style="{accent}">{value}</div><div class="iq-kpi-note">{note}</div></div>',
            unsafe_allow_html=True,
        )
    st.write("")

    # Map + priority board
    left, right = st.columns([3, 2], gap="medium")
    with left:
        st.markdown(
            '<div class="iq-h">Where the bugs are</div><div class="iq-hsub">Green = where the bot explored · '
            "markers = where each problem starts, coloured by priority</div>",
            unsafe_allow_html=True,
        )
        png = map_png(signature) if signature else None
        if png:
            st.image(png, width="stretch")
    with right:
        st.markdown(
            '<div class="iq-h">Fix first</div><div class="iq-hsub">Ranked by severity × how often the bot hit it</div>',
            unsafe_allow_html=True,
        )
        top_score = max((i.score for i in roots), default=1.0)
        if not roots:
            st.markdown('<div class="iq-card">No problems found yet - the bot is still exploring.</div>',
                        unsafe_allow_html=True)
        for issue in roots:
            colour = TIER_COLOURS[issue.tier]
            st.markdown(
                f"""<div class="iq-issue" style="border-left: 6px solid {colour}">
  <div class="top">{pill(issue.tier)}<span class="name">{html.escape(issue.type)}</span>
  <span class="count">×{issue.count}</span></div>
  <div class="loc">{html.escape(TYPE_BLURB.get(issue.type, ""))} · {html.escape(issue.location)}</div>
  <div class="meta">{issue.tier_label} · {issue.severity} · first at {issue.first.game_time} · score {issue.score:.1f}</div>
  <div class="iq-bar"><div style="width:{100 * issue.score / top_score:.0f}%; background:{colour}"></div></div>
</div>""",
                unsafe_allow_html=True,
            )
        if symptoms:
            lines = "".join(
                f'<div class="iq-symptom">{pill("P3")} {html.escape(s.type)} ×{s.count} · '
                f"{html.escape(s.tier_label.lower())}</div>"
                for s in symptoms
            )
            st.markdown(
                f'<div class="iq-card" style="padding:10px 14px"><div class="iq-kpi-label">Side effects '
                f"(fixed automatically with their cause)</div>{lines}</div>",
                unsafe_allow_html=True,
            )

    # Bug inspector
    st.write("")
    st.markdown(
        '<div class="iq-h">Bug inspector</div><div class="iq-hsub">Screenshot of the moment the bug happened '
        "(rebuilt from telemetry with the game's real geometry) and the exact buttons that led to it</div>",
        unsafe_allow_html=True,
    )
    choices: list[Issue] = roots + symptoms
    labels = [f"{i.tier} · {i.type} ×{i.count} — {i.location}" for i in choices]
    pick = st.selectbox("Problem", range(len(choices)), format_func=lambda k: labels[k], key="iq_issue")
    issue = choices[pick if pick is not None and pick < len(choices) else 0]
    events = sorted(issue.events, key=lambda e: e.frame_id)
    occ = st.select_slider(
        "Occurrence",
        options=list(range(len(events))),
        format_func=lambda k: f"#{k + 1} at {events[k].game_time}",
        key=f"iq_occ_{issue.key}",
    ) if len(events) > 1 else 0
    event = events[occ]

    shot_col, info_col = st.columns([3, 2], gap="medium")
    with shot_col:
        zoom = st.toggle("Zoom to the bug", value=True, key="iq_zoom")
        image = snapshot(signature, event.index, zoom) if signature else None
        if image is not None:
            st.image(image, width="stretch")
    with info_col:
        facts = [
            ("Priority", f"{issue.tier} · {issue.tier_label}"),
            ("Severity", event.severity),
            ("When", f"{event.game_time} (frame {event.frame_id:,})"),
            ("Bug position", f"x {event.x:,.0f} · y {event.y:,.0f}"),
            ("Where it starts", event.location),
            ("Seen", f"{issue.count}× in this run"),
        ]
        st.markdown(
            '<div class="iq-facts">'
            + "".join(f'<div class="iq-fact"><div class="l">{l}</div><div class="v">{html.escape(v)}</div></div>'
                      for l, v in facts)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="iq-kpi-label">How to reproduce · last {len(event.reproduction)} inputs</div>',
                    unsafe_allow_html=True)
        chips = "".join(
            f'<div class="iq-chip{" last" if n == len(event.reproduction) - 1 else ""}">'
            f'<div class="n">{n + 1}</div><div class="k">{key_label(tok)}</div></div>'
            for n, tok in enumerate(event.reproduction)
        )
        st.markdown(f'<div class="iq-chips">{chips}</div>', unsafe_allow_html=True)
        st.write("")
        st.download_button(
            "Download this bug report (.md)",
            bug_markdown(event, issue),
            file_name=f"indieqa_{issue.tier}_{event.type.replace(' ', '_')}_frame{event.frame_id}.md",
            mime="text/markdown",
            width="stretch",
            key=f"dl_md_{event.index}",
        )

    # Full log
    st.write("")
    st.markdown('<div class="iq-h">Bug log</div><div class="iq-hsub">Every detection in this run</div>',
                unsafe_allow_html=True)
    issue_of = {e.index: i for i in analysis.issues for e in i.events}
    rows: list[dict[str, Any]] = [
        {
            "Priority": issue_of[e.index].tier,
            "Type": e.type,
            "Side effect of": issue_of[e.index].symptom_of or "",
            "Severity": e.severity,
            "Game time": e.game_time,
            "Frame": e.frame_id,
            "Where it starts": e.location,
            "x": round(e.x, 1),
            "y": round(e.y, 1),
        }
        for e in sorted(analysis.events, key=lambda e: e.frame_id)
    ]
    log = pd.DataFrame(rows)
    f1, f2 = st.columns(2)
    tiers = f1.multiselect("Priority", [t for t, _, _ in TIERS], default=[t for t, _, _ in TIERS], key="iq_f_tier")
    types = sorted(log["Type"].unique()) if len(log) else []
    chosen = f2.multiselect("Type", types, default=types, key="iq_f_type")
    view = log[log["Priority"].isin(tiers) & log["Type"].isin(chosen)] if len(log) else log
    st.dataframe(view, width="stretch", hide_index=True, height=320)
    d1, d2 = st.columns(2)
    d1.download_button("Download bug log (.csv)", view.to_csv(index=False), "indieqa_bug_log.csv", "text/csv",
                       width="stretch", key="dl_csv")
    export = [
        {**{k: v for k, v in e.__dict__.items()}, "priority": issue_of[e.index].tier,
         "side_effect_of": issue_of[e.index].symptom_of}
        for e in analysis.events
    ]
    d2.download_button("Download all bugs (.json)", json.dumps(export, indent=2), "indieqa_bugs.json",
                       "application/json", width="stretch", key="dl_json")

    with st.expander("How the priority is calculated"):
        weights = ", ".join(f"{k} = {v:g}" for k, v in SEVERITY_WEIGHT.items())
        tiers_txt = " · ".join(f"**{n}** ≥ {t:g} ({lbl})" for n, t, lbl in TIERS)
        st.markdown(
            f"""
- **Score = severity × (1 + log₂(1 + occurrences per 10 min of gameplay))**, with severity {weights}.
  Frequent and severe problems rise to the top; the log keeps one very common bug from drowning out the rest.
- Tiers: {tiers_txt}.
- **Side effects** are bugs caused by another bug moments earlier (falling forever after clipping through a wall,
  or leaving the map after a fall). They are listed as P3 because fixing the cause fixes them too.
- **Ground covered** = share of walkable floor/platform sections (16 px wide) the bot stood on.
- Bugs come from Person 2's detector (`analysis/bug_detector.py`) run on the live telemetry.
"""
        )


if auto:
    st.fragment(run_every=2)(body)()
else:
    body()
