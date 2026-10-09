"""IndieQA backup website (branch backup-plan1).

    streamlit run dashboard/backup_site.py

Reads data/logs/telemetry.csv (written live by main.py), runs Person 2's
detector on it, and shows: cost banner, KPIs, level map with bug locations,
a "fix first" priority board, per-bug screenshots with reproduction steps,
and an exportable bug log. Light / dark theme switch; refreshes automatically
while the bot is playing.
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
    SEVERITY_WEIGHT,
    TIERS,
    TYPE_BLURB,
    Analysis,
    BugEvent,
    Issue,
    analyse,
    bug_markdown,
    format_game_time,
    load_telemetry,
    palette,
    render_map,
    render_snapshot,
)

CSV_PATH = ROOT / "data" / "logs" / "telemetry.csv"
HUMAN_RATE = 25.0
INDIEQA_RATE = 0.04
DEMO_SEED = 11
THEME_OPTIONS = {"☀  Light": "light", "☾  Dark": "dark"}
MAX_LOG_ROWS = 400
MAX_OCCURRENCE_PILLS = 48

st.set_page_config(page_title="IndieQA · QA Report", page_icon="🧪", layout="wide")


# ----------------------------------------------------------------- theme
def remember_theme() -> None:
    choice = st.session_state.get("iq_theme_pick")
    if choice is not None:  # segmented control can be deselected; keep the last real choice
        st.session_state.iq_theme = THEME_OPTIONS[choice]


THEME: str = st.session_state.get("iq_theme", "light")
P: dict[str, str] = palette(THEME)

st.markdown(
    f"""
<style>
:root {{
  --bg: {P['bg']}; --card: {P['card']}; --card2: {P['card2']}; --border: {P['border']};
  --ink: {P['ink']}; --muted: {P['muted']}; --red: {P['red']}; --red-soft: {P['red_soft']};
  --green: {P['green']}; --green-soft: {P['green_soft']}; --on-red: {'#1A1714' if THEME == 'dark' else '#FFFFFF'};
}}
/* page + native widgets follow the selected theme */
[data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"] > div
  {{ background: var(--bg) !important; color: var(--ink); }}
header[data-testid="stHeader"] {{ background: transparent; }}
header[data-testid="stHeader"] * {{ color: var(--muted) !important; }}
.block-container {{ padding-top: 1.3rem; padding-bottom: 3rem; max-width: 1440px; }}
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p, label, [data-testid="stCaptionContainer"] {{ color: var(--ink); }}
[data-testid="stWidgetLabel"] p {{ font-weight: 700; font-size: .9rem; }}
code {{ background: var(--card2) !important; color: var(--ink) !important; }}
[data-testid="stBaseButton-secondary"], [data-testid="stButtonGroup"] button[role="radio"]
  {{ background: var(--card) !important; color: var(--ink) !important; border: 1px solid var(--border) !important; }}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stButtonGroup"] button[role="radio"]:hover
  {{ border-color: var(--red) !important; color: var(--red) !important; }}
[data-testid="stBaseButton-primary"] {{ background: var(--red) !important; border-color: var(--red) !important; color: var(--on-red) !important; font-weight: 700; }}
[data-testid="stBaseButton-primary"] p {{ color: var(--on-red) !important; }}
[data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"]
  {{ background: var(--red-soft) !important; color: var(--ink) !important; border: 1.5px solid var(--red) !important; font-weight: 700; }}
[data-testid="stButtonGroup"] button[role="radio"] p {{ font-size: .95rem; color: inherit !important; }}
[data-testid="stButtonGroup"] button[data-variant="pills"] {{ padding: 6px 14px !important; min-height: 2.3rem; }}
[data-testid="stButtonGroup"] button[role="radio"]:focus-visible {{ outline: 3px solid var(--red) !important; outline-offset: 2px; }}
[data-baseweb="select"] > div, [data-baseweb="select"] > div > div:first-child {{ background: var(--card) !important; border-color: var(--border) !important; color: var(--ink) !important; }}
[data-baseweb="select"] input {{ color: var(--ink) !important; }}
[data-testid="stMultiSelect"] [role="group"], [data-testid="stSelectbox"] [role="group"]
  {{ background: var(--card) !important; border: 1px solid var(--border) !important; color: var(--ink) !important; }}
[data-testid="stMultiSelect"] input, [data-testid="stSelectbox"] input, [data-testid="stSelectbox"] [role="group"] *
  {{ color: var(--ink) !important; }}
[role="listbox"] {{ background: var(--card) !important; border: 1px solid var(--border) !important; }}
[role="option"] {{ background: var(--card) !important; color: var(--ink) !important; }}
[role="option"]:hover, [role="option"][aria-selected="true"], [role="option"][data-focused="true"]
  {{ background: var(--card2) !important; }}
[data-baseweb="select"] svg {{ fill: var(--muted) !important; }}
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"]
  {{ background: var(--card) !important; }}
[data-baseweb="popover"] li {{ color: var(--ink) !important; background: var(--card) !important; }}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] {{ background: var(--card2) !important; }}
[data-baseweb="tag"] {{ background: var(--red-soft) !important; color: var(--ink) !important; }}
[data-baseweb="tag"] span {{ color: var(--ink) !important; }}
[data-testid="stExpander"] details {{ background: var(--card) !important; border-color: var(--border) !important; }}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {{ color: var(--ink) !important; }}
[data-testid="stToast"] {{ background: var(--card) !important; color: var(--ink) !important; }}

/* custom components */
.iq-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px 18px; }}
.iq-brand {{ font-size: 2.2rem; font-weight: 800; color: var(--ink); letter-spacing: -0.02em; line-height: 1; }}
.iq-brand span {{ color: var(--red); }}
.iq-sub {{ color: var(--muted); font-size: 1rem; margin-top: 5px; }}
.iq-status {{ display: inline-block; padding: 5px 12px; border-radius: 999px; font-weight: 700; font-size: .82rem; }}
.iq-live {{ background: var(--green-soft); color: var(--green); }}
.iq-idle {{ background: var(--card2); color: var(--muted); }}
.iq-banner {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px;
  background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 14px 22px; margin: 8px 0 14px 0; }}
.iq-banner .human {{ color: var(--red); font-weight: 700; font-size: 1.2rem; }}
.iq-banner .human s {{ opacity: .8; }}
.iq-banner .bot {{ color: var(--green); font-weight: 800; font-size: 1.65rem; }}
.iq-banner .mid {{ color: var(--muted); font-size: .95rem; }}
.iq-banner .mid b {{ color: var(--ink); }}
.iq-kpi-label {{ color: var(--muted); font-size: .74rem; text-transform: uppercase; letter-spacing: .07em; font-weight: 700; }}
.iq-kpi-value {{ color: var(--ink); font-size: 1.85rem; font-weight: 800; margin-top: 2px; }}
.iq-kpi-note {{ color: var(--muted); font-size: .82rem; }}
.iq-h {{ font-size: 1.22rem; font-weight: 800; color: var(--ink); margin: 2px 0 2px 0; }}
.iq-hsub {{ color: var(--muted); font-size: .9rem; margin-bottom: 10px; }}
.iq-issue {{ background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 11px 14px; margin-bottom: 4px; }}
.iq-issue .top {{ display: flex; align-items: center; gap: 8px; }}
.iq-issue .name {{ font-weight: 800; color: var(--ink); font-size: 1.05rem; }}
.iq-issue .count {{ margin-left: auto; font-weight: 800; font-size: 1.3rem; color: var(--ink); }}
.iq-issue .loc {{ color: var(--ink); font-size: .9rem; margin-top: 3px; }}
.iq-issue .meta {{ color: var(--muted); font-size: .82rem; margin-top: 2px; }}
.iq-pill {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-weight: 800; font-size: .76rem;
  color: {P['bg']}; }}
.iq-bar {{ height: 5px; border-radius: 4px; background: var(--card2); margin-top: 8px; overflow: hidden; }}
.iq-bar > div {{ height: 5px; border-radius: 4px; }}
.iq-symptom {{ color: var(--muted); font-size: .86rem; padding: 4px 2px; }}
.iq-chips {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 6px; }}
.iq-chip {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 5px 6px; text-align: center; }}
.iq-chip .n {{ color: var(--muted); font-size: .7rem; }}
.iq-chip .k {{ color: var(--ink); font-weight: 700; font-size: .9rem; }}
.iq-chip.last {{ border-color: var(--red); background: var(--red-soft); }}
.iq-facts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }}
.iq-fact {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 8px 12px; }}
.iq-fact .l {{ color: var(--muted); font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 700; }}
.iq-fact .v {{ color: var(--ink); font-weight: 700; font-size: 1rem; }}
.iq-occ {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 9px 14px;
  text-align: center; color: var(--ink); }}
.iq-occ .big {{ font-size: 1.15rem; font-weight: 800; }}
.iq-occ .small {{ color: var(--muted); font-size: .82rem; }}
.iq-empty {{ text-align: center; padding: 48px 20px; }}
.iq-tablewrap {{ max-height: 380px; overflow: auto; border: 1px solid var(--border); border-radius: 14px; background: var(--card); }}
.iq-table {{ width: 100%; border-collapse: collapse; font-size: .9rem; color: var(--ink); }}
.iq-table th {{ position: sticky; top: 0; background: var(--card2); color: var(--muted); text-align: left;
  font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; padding: 9px 12px; }}
.iq-table td {{ padding: 8px 12px; border-top: 1px solid var(--border); }}
.iq-table tr:hover td {{ background: var(--card2); }}
.iq-note {{ color: var(--muted); font-size: .82rem; margin-top: 6px; }}
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


@st.cache_data(max_entries=6, show_spinner=False)
def map_png(signature: tuple[int, int], theme: str) -> bytes | None:
    data = load(signature)
    if data is None:
        return None
    df, analysis = data
    return render_map(df, analysis.issues, build_level(), theme)


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
    return f'<span class="iq-pill" style="background:{P[tier]}">{tier}</span>'


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


def inspect_issue(index: int) -> None:
    st.session_state.iq_issue = index


def step_occurrence(key: str, delta: int, count: int) -> None:
    current = st.session_state.get(key)
    st.session_state[key] = ((current if current is not None else 0) + delta) % count


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
    t1, t2 = st.columns([3, 2], vertical_alignment="center")
    with t1:
        st.segmented_control(
            "Theme",
            list(THEME_OPTIONS),
            default=next(k for k, v in THEME_OPTIONS.items() if v == THEME),
            key="iq_theme_pick",
            on_change=remember_theme,
            label_visibility="collapsed",
        )
    with t2:
        auto = st.toggle("Live auto-refresh", value=True, help="Re-reads the telemetry every 2 seconds")


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
    choices: list[Issue] = roots + symptoms
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
        accent = f"color:{P['P0']}" if label.startswith("P0") and value != "0" else ""
        col.markdown(
            f'<div class="iq-card"><div class="iq-kpi-label">{label}</div>'
            f'<div class="iq-kpi-value" style="{accent}">{value}</div><div class="iq-kpi-note">{note}</div></div>',
            unsafe_allow_html=True,
        )
    st.write("")

    # ---- map + priority board
    left, right = st.columns([3, 2], gap="medium")
    with left:
        st.markdown(
            '<div class="iq-h">Where the bugs are</div><div class="iq-hsub">Green lines = every path the bot took (stronger = more often) · '
            "markers = where each problem starts, coloured by priority</div>",
            unsafe_allow_html=True,
        )
        png = map_png(signature, THEME) if signature else None
        if png:
            st.image(png, width="stretch")
    with right:
        st.markdown(
            '<div class="iq-h">Fix first</div><div class="iq-hsub">Ranked by severity × how often the bot hit it · '
            "press Inspect to see the bug</div>",
            unsafe_allow_html=True,
        )
        top_score = max((i.score for i in roots), default=1.0)
        if not roots:
            st.markdown('<div class="iq-card">No problems found yet - the bot is still exploring.</div>',
                        unsafe_allow_html=True)
        for idx, issue in enumerate(roots):
            colour = P[issue.tier]
            card, action = st.columns([5, 1.25], vertical_alignment="center")
            card.markdown(
                f"""<div class="iq-issue" style="border-left: 6px solid {colour}">
  <div class="top">{pill(issue.tier)}<span class="name">{html.escape(issue.type)}</span>
  <span class="count">×{issue.count}</span></div>
  <div class="loc">{html.escape(TYPE_BLURB.get(issue.type, ""))} · {html.escape(issue.location)}</div>
  <div class="meta">{issue.tier_label} · {issue.severity} · first at {issue.first.game_time} · score {issue.score:.1f}</div>
  <div class="iq-bar"><div style="width:{100 * issue.score / top_score:.0f}%; background:{colour}"></div></div>
</div>""",
                unsafe_allow_html=True,
            )
            action.button("Inspect", key=f"iq_inspect_{issue.key}", on_click=inspect_issue, args=(idx,),
                          width="stretch", help=f"Show {issue.type} in the bug inspector below")
        if symptoms:
            lines = "".join(
                f'<div class="iq-symptom">{pill("P3")} {html.escape(s.type)} ×{s.count} · '
                f"{html.escape(s.tier_label.lower())}</div>"
                for s in symptoms
            )
            st.markdown(
                f'<div class="iq-card" style="padding:10px 14px; margin-top:6px"><div class="iq-kpi-label">'
                f"Side effects (fixed automatically with their cause)</div>{lines}</div>",
                unsafe_allow_html=True,
            )

    # ---- bug inspector
    st.write("")
    st.markdown(
        '<div class="iq-h">Bug inspector</div><div class="iq-hsub">Screenshot of the moment the bug happened '
        "(rebuilt from telemetry with the game's real level) and the exact buttons that led to it</div>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("iq_issue") is None or st.session_state.iq_issue >= len(choices):
        st.session_state.iq_issue = 0
    picked = st.pills(
        "Problem",
        list(range(len(choices))),
        format_func=lambda k: f"{choices[k].tier} · {choices[k].type} ×{choices[k].count}"
        + (" (side effect)" if choices[k].symptom_of else ""),
        key="iq_issue",
    )
    issue = choices[picked if picked is not None else 0]
    events: list[BugEvent] = sorted(issue.events, key=lambda e: e.frame_id)
    n = len(events)
    occ_key = f"iq_occ_{issue.key}"
    current = st.session_state.get(occ_key)
    if current is None or current >= n:
        st.session_state[occ_key] = 0

    st.markdown(f'<div class="iq-kpi-label" style="margin-top:6px">Occurrences of {html.escape(issue.type)} · '
                f"{n} in this run</div>", unsafe_allow_html=True)
    prev_col, mid_col, next_col = st.columns([1, 2.2, 1], vertical_alignment="center")
    prev_col.button("◀  Previous", key=f"iq_prev_{issue.key}", on_click=step_occurrence, args=(occ_key, -1, n),
                    width="stretch", disabled=n < 2)
    next_col.button("Next  ▶", key=f"iq_next_{issue.key}", on_click=step_occurrence, args=(occ_key, 1, n),
                    width="stretch", disabled=n < 2)
    occ_index = st.session_state.get(occ_key) or 0
    event = events[occ_index]
    mid_col.markdown(
        f'<div class="iq-occ"><span class="big">Occurrence {occ_index + 1} of {n}</span><br>'
        f'<span class="small">game time {event.game_time} · frame {event.frame_id:,}</span></div>',
        unsafe_allow_html=True,
    )
    if 1 < n <= MAX_OCCURRENCE_PILLS:
        st.pills(
            "Jump to occurrence",
            list(range(n)),
            format_func=lambda k: f"#{k + 1} · {events[k].game_time}",
            key=occ_key,
        )
    elif n > MAX_OCCURRENCE_PILLS:
        st.selectbox("Jump to occurrence", list(range(n)), format_func=lambda k: f"#{k + 1} · {events[k].game_time}",
                     key=occ_key)
    occ_index = st.session_state.get(occ_key) or 0
    event = events[occ_index]

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
            f'<div class="iq-chip{" last" if k == len(event.reproduction) - 1 else ""}">'
            f'<div class="n">{k + 1}</div><div class="k">{key_label(tok)}</div></div>'
            for k, tok in enumerate(event.reproduction)
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

    # ---- full log
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
    tier_names = [t for t, _, _ in TIERS]
    tiers = f1.multiselect("Priority", tier_names, default=tier_names, key="iq_f_tier")
    types = sorted(log["Type"].unique()) if len(log) else []
    chosen = f2.multiselect("Type", types, default=types, key="iq_f_type")
    view = log[log["Priority"].isin(tiers) & log["Type"].isin(chosen)] if len(log) else log
    head = "".join(f"<th>{html.escape(c)}</th>" for c in log.columns)
    body_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{pill(str(v)) if c == 'Priority' else html.escape(str(v))}</td>" for c, v in row.items()
        )
        + "</tr>"
        for _, row in view.head(MAX_LOG_ROWS).iterrows()
    )
    st.markdown(f'<div class="iq-tablewrap"><table class="iq-table"><thead><tr>{head}</tr></thead>'
                f"<tbody>{body_rows}</tbody></table></div>", unsafe_allow_html=True)
    shown = min(len(view), MAX_LOG_ROWS)
    st.markdown(f'<div class="iq-note">Showing {shown} of {len(view)} rows'
                f'{" - download for the full list" if len(view) > MAX_LOG_ROWS else ""}</div>',
                unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    d1.download_button("Download bug log (.csv)", view.to_csv(index=False), "indieqa_bug_log.csv", "text/csv",
                       width="stretch", key="dl_csv")
    export = [
        {**e.__dict__, "priority": issue_of[e.index].tier, "side_effect_of": issue_of[e.index].symptom_of}
        for e in analysis.events
    ]
    d2.download_button("Download all bugs (.json)", json.dumps(export, indent=2), "indieqa_bugs.json",
                       "application/json", width="stretch", key="dl_json")

    with st.expander("How the priority is calculated"):
        weights = ", ".join(f"{k} = {v:g}" for k, v in SEVERITY_WEIGHT.items())
        tiers_txt = " · ".join(f"**{name}** ≥ {t:g} ({lbl})" for name, t, lbl in TIERS)
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
