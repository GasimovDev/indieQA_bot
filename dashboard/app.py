"""IndieQA live Streamlit dashboard. Run: streamlit run dashboard/app.py"""
from __future__ import annotations
from collections import Counter
from datetime import datetime
import importlib
import json
from pathlib import Path
import sys
import subprocess
import time
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from analysis.reporter import BugReporter
from dashboard.live import LiveRun, PRIORITIES, BUG_COLORS, prioritize, read_telemetry
from dashboard import visuals
from dashboard.advisor import AdvisorAPIError, LocalFixAdvisor, configured_advisor

# Streamlit can rerun this file without reloading an imported module. Reload the
# small rendering module so theme-aware function signatures stay in sync during
# local development and live dashboard updates.
visuals = importlib.reload(visuals)
overview = visuals.overview
evidence_png = visuals.evidence_png


def demo_process() -> subprocess.Popen | None:
    process = st.session_state.get('demo_process')
    return process if isinstance(process, subprocess.Popen) else None


def demo_is_running() -> bool:
    process = demo_process()
    return process is not None and process.poll() is None


def start_demo() -> None:
    """Launch the rendered seed-11 game beside the dashboard."""
    log_path = ROOT / 'data/logs/live_demo.log'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open('w', encoding='utf-8')
    flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    process = subprocess.Popen(
        [sys.executable, str(ROOT / 'main.py'), '--seed', '11'],
        cwd=str(ROOT), stdout=log_file, stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    st.session_state.demo_process = process
    st.session_state.demo_log = log_file
    st.session_state.demo_started = time.time()
    # The button starts a live session, so the dashboard should follow it
    # immediately without requiring a second manual toggle.
    st.session_state.live = True


def stop_demo() -> None:
    process = demo_process()
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
    log_file = st.session_state.pop('demo_log', None)
    if log_file is not None:
        log_file.close()
    st.session_state.demo_process = None


def advisor_backend():
    """Keep one configured backend for this browser session."""
    if 'advisor_backend' not in st.session_state:
        st.session_state.advisor_backend = configured_advisor()
    return st.session_state.advisor_backend


def advisor_answer(question: str, bug: dict) -> str:
    """Use the API when configured and fall back locally if it is unavailable."""
    backend = advisor_backend()
    try:
        return backend.answer(question, bug)
    except AdvisorAPIError as exc:
        st.session_state.advisor_api_warning = str(exc)
        local = LocalFixAdvisor().answer(question, bug)
        return f'{local}\n\n(API unavailable; using the local advisor for this answer.)'

st.set_page_config(page_title='IndieQA · Live QA', page_icon='🛡️', layout='wide')
light_mode = bool(st.session_state.get('light_mode', False))
theme_label = '☀️' if light_mode else '🌙'
theme = {
    'background': '#f5f7fb' if light_mode else '#0b1120',
    'sidebar': '#e8edf5' if light_mode else '#101c30',
    'panel': '#ffffff' if light_mode else '#101c30',
    'border': '#cbd5e1' if light_mode else '#28364d',
    'text': '#172033' if light_mode else '#f8fafc',
    'muted': '#52627a' if light_mode else '#94a3b8',
    'accent': '#087f73' if light_mode else '#5eead4',
}
st.markdown(f'''<style>
.stApp {{background:{theme['background']};color:{theme['text']};}}
[data-testid="stHeader"] {{background:{theme['background']};}}
[data-testid="stSidebar"] {{background:{theme['sidebar']};}}
[data-testid="stMetric"] {{background:{theme['panel']};border:1px solid {theme['border']};border-radius:12px;padding:16px;}}
[data-testid="stMetricLabel"] {{color:{theme['muted']};}}
[data-testid="stMetricValue"] {{color:{theme['text']};}}
h1,h2,h3 {{color:{theme['text']} !important;letter-spacing:-.025em;}}
.block-container {{padding-top:4rem;max-width:1600px;}}
.hero-kicker {{color:{theme['accent']};font-size:12px;letter-spacing:.18em;font-weight:700;}}
.type-card {{background:{theme['panel']};border:1px solid {theme['border']};border-radius:10px;padding:14px 18px;}}
.type-card strong {{font-size:24px;color:{theme['text']};}} .type-card span {{font-size:12px;color:{theme['muted']};}}
[data-testid="stCaptionContainer"] {{color:{theme['muted']};}}
[data-baseweb="select"] > div {{background:{theme['panel']};border-color:{theme['border']};color:{theme['text']};}}
[data-baseweb="select"] * {{color:{theme['text']} !important;}}
[role="listbox"],[role="option"],[data-baseweb="popover"],[data-baseweb="menu"] {{background:{theme['panel']} !important;color:{theme['text']} !important;}}
[role="listbox"] *,[role="option"] *,[data-baseweb="popover"] *,[data-baseweb="menu"] * {{color:{theme['text']} !important;}}
[role="option"]:hover {{background:{theme['sidebar']} !important;}}
.stSelectbox label,.stSelectbox label p {{color:{theme['text']} !important;}}
[data-testid="stExpander"] {{background:{theme['panel']};border-color:{theme['border']};}}
[data-testid="stExpander"] summary,[data-testid="stExpander"] p {{color:{theme['text']};}}
[data-testid="stDataFrame"] {{border:1px solid {theme['border']};}}
.theme-control {{display:flex;justify-content:flex-end;align-items:center;margin:-1rem 0 0.75rem;}}
.theme-control [data-testid="stCheckbox"] {{background:{theme['panel']};border:1px solid {theme['border']};border-radius:999px;padding:0.35rem 0.7rem 0.35rem 0.5rem;box-shadow:0 4px 14px rgba(15,23,42,.12);}}
.theme-control [data-testid="stWidgetLabel"] {{font-weight:700;color:{theme['text']};}}
.brand-lockup {{display:flex;align-items:center;gap:.65rem;margin:.15rem 0 .35rem;}}
.brand-mark {{width:2rem;height:2rem;flex:0 0 auto;}}
.brand-name {{font-size:1.25rem;font-weight:800;letter-spacing:-.03em;color:{theme['text']};}}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f'''<div class="brand-lockup">
        <svg class="brand-mark" viewBox="0 0 40 40" role="img" aria-label="IndieQA logo">
            <path d="M20 2.8 35 8.5v10.8c0 9.5-6.1 15.2-15 18-8.9-2.8-15-8.5-15-18V8.5L20 2.8Z" fill="{theme['accent']}" fill-opacity=".16" stroke="{theme['accent']}" stroke-width="2"/>
            <rect x="11" y="14" width="18" height="13" rx="4" fill="{theme['panel']}" stroke="{theme['accent']}" stroke-width="1.8"/>
            <path d="M20 10v4M15 20h.1M25 20h.1M15 24h10" stroke="{theme['accent']}" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span class="brand-name">IndieQA</span>
    </div>''', unsafe_allow_html=True)
    st.caption('AUTONOMOUS PLAYTESTING')
    live = st.toggle('Auto-refresh every second', value=False, key='live')
    show_heatmap = st.toggle('Show exploration heatmap', value=True, key='heatmap')
    st.button('Refresh now', key='refresh')
    st.divider()
    st.markdown('**Fix priorities**')
    for severity, (priority, action, _) in PRIORITIES.items():
        st.caption(f'{priority} · {action}  /  {severity}')
    st.divider()
    st.markdown('**Run the live demo**')
    if demo_is_running():
        st.success('Game demo is running')
        st.caption('The rendered game window should be beside this dashboard.')
        if st.button('■ Stop live demo', key='stop_demo', use_container_width=True):
            stop_demo()
            st.rerun()
    else:
        if st.button('▶ Start live demo', key='start_demo', type='primary', use_container_width=True, on_click=start_demo):
            st.rerun()
        st.caption('Launches the rendered seed-11 game and writes telemetry for this page.')
    if st.session_state.get('demo_started'):
        process = demo_process()
        if process is not None and process.poll() is not None:
            st.caption(f'Demo finished with exit code {process.returncode}.')
            st.session_state.demo_process = None
    st.markdown('**QA cost assumptions**')
    st.caption('Human QA: $25/hour\n\nIndieQA local compute: $0.04/hour\n\nTeam estimates, not measured savings.')

header_spacer, theme_column = st.columns([0.84, 0.16], vertical_alignment='center')
with theme_column:
    st.markdown('<div class="theme-control">', unsafe_allow_html=True)
    st.toggle(theme_label, value=light_mode, key='light_mode', help='Switch between dark and light dashboard themes.')
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="hero-kicker">PHYSICS TESTING / LIVE OBSERVATORY</div>', unsafe_allow_html=True)
st.title('Find the break. See the evidence.')
st.caption('Follow the bot through the real level, inspect failure points, and prioritize the fixes.')

@st.cache_data(show_spinner=False)
def geometry_data() -> dict:
    return json.loads((ROOT / 'docs/level_geometry.json').read_text(encoding='utf-8'))

@st.cache_data(show_spinner=False, max_entries=48)
def cached_evidence(window: pd.DataFrame, bug: dict, geometry: dict, light: bool) -> bytes:
    return evidence_png(window, bug, geometry, light_mode=light)


def duration(frames: int) -> str:
    seconds = frames // 60
    return f'{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}'


def load_recorded_reports(data: pd.DataFrame) -> list[dict]:
    """Use reports already written by --analyze for completed runs."""
    if data.empty:
        return []
    start, end = float(data.timestamp.min()), float(data.timestamp.max())
    reports = []
    for path in sorted((ROOT / 'data/reports').glob('bug_*.json')):
        try:
            bug = json.loads(path.read_text(encoding='utf-8'))
            if start <= float(bug.get('timestamp', -1)) <= end:
                reports.append(bug)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return reports


def render_fix_advisor(bug: dict) -> None:
    """Render the API-ready local advisor for the selected failure point."""
    event_key = str(bug['event_key'])
    chats = st.session_state.setdefault('advisor_chats', {})
    messages = chats.setdefault(event_key, [{
        'role': 'assistant',
        'content': advisor_answer('recommend a fix', bug),
    }])
    with st.container(border=True):
        st.markdown('### 💬 Fix Advisor')
        st.caption(f'{advisor_backend().name} · API key is optional; local fallback stays available.')
        if st.session_state.get('advisor_api_warning'):
            st.caption(f"API status: {st.session_state.advisor_api_warning}")
        for message in messages[-6:]:
            with st.chat_message(message['role']):
                st.write(message['content'])
        with st.form(f'advisor_form_{event_key}'):
            question = st.text_input('Ask about this failure', placeholder='Why is this P0? How do I reproduce it?')
            submitted = st.form_submit_button('Ask advisor', type='primary', use_container_width=True)
        question = question.strip()
        submission_key = f'advisor_last_question_{event_key}'
        if submitted and question and st.session_state.get(submission_key) != question:
            messages.append({'role': 'user', 'content': question})
            messages.append({'role': 'assistant', 'content': advisor_answer(question, bug)})
            st.session_state[submission_key] = question
            st.caption('Answer added. The next live refresh keeps this conversation in place.')


def _dashboard_fragment(function):
    """Enable Streamlit's timer only after the user explicitly turns live mode on."""
    return st.fragment(run_every=1)(function) if live else function


@_dashboard_fragment
def dashboard() -> None:
    if 'live_run' not in st.session_state:
        st.session_state.live_run = LiveRun()
    tracker = st.session_state.live_run
    try:
        data = read_telemetry(ROOT / 'data/logs/telemetry.csv')
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(f'Waiting for readable telemetry: {exc}')
        return
    if data.empty:
        st.info('Ready to explore. Start the simulation to see the live map and detected bugs.')
        st.code('python main.py --headless --seed 11 --analyze', language='bash')
        return
    stamp = (ROOT / 'data/logs/telemetry.csv').stat().st_mtime
    active = time.time() - stamp < 5
    if not active and tracker.rows_seen == 0:
        bugs = prioritize(load_recorded_reports(data))
        tracker.rows_seen = len(data)
    else:
        bugs = prioritize(tracker.update(data))
    geometry = geometry_data()
    status = '● RECEIVING TELEMETRY' if active else '● RECORDED RUN'
    st.caption(f'{status} · {"Auto-refresh on" if live else "Manual refresh"} · Run started {datetime.fromtimestamp(float(data.iloc[0].timestamp)).strftime("%H:%M:%S")} local · 60 FPS')
    counts = Counter(b['type'] for b in bugs)
    priorities = Counter(b['priority'] for b in bugs)
    metrics = st.columns(4)
    metrics[0].metric('Game time tested', duration(len(data)))
    metrics[1].metric('Frames analyzed', f'{len(data):,}')
    metrics[2].metric('Bugs detected', len(bugs))
    metrics[3].metric('P0 · release blockers', priorities['P0'])
    for col, (kind, color) in zip(st.columns(4), BUG_COLORS.items()):
        col.markdown(f'<div class="type-card" style="border-left:3px solid {color}"><span>{kind.upper()}</span><br><strong>{counts[kind]}</strong></div>', unsafe_allow_html=True)
    st.write('')
    filters = st.columns(3)
    severity = filters[0].selectbox('Severity', ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'], key='severity')
    kind = filters[1].selectbox('Bug type', ['ALL', *BUG_COLORS], key='kind')
    priority = filters[2].selectbox('Fix priority', ['ALL', 'P0', 'P1', 'P2', 'P3'], key='priority')
    filtered = [b for b in bugs if (severity == 'ALL' or b['severity'] == severity)
                and (kind == 'ALL' or b['type'] == kind) and (priority == 'ALL' or b['priority'] == priority)]
    options = [b['event_key'] for b in filtered]
    lookup = {b['event_key']: b for b in filtered}
    if st.session_state.get('selected_event') not in options:
        st.session_state.selected_event = options[0] if options else None
    selected = None
    if options:
        selected_key = st.selectbox('Inspect an event', options, key='selected_event',
            format_func=lambda key: f"{lookup[key]['priority']} · {lookup[key]['type']} · frame {lookup[key]['frame_id']:,}")
        if selected_key is not None:
            selected = lookup[selected_key]
    st.subheader('Exploration & failure points')
    map_col, detail_col = st.columns([1.85, 1])
    with map_col:
        figure = overview(data, filtered, geometry, selected['event_key'] if selected else None, show_heatmap, light_mode=light_mode)
        st.pyplot(figure)
        plt.close(figure)
        st.caption('Real level geometry · teal = recent trail/player · colored × = detected event · white ring = selected event')
        st.caption('Off-map events are anchored to the last recorded arena point, or the nearest border if none exists. Exact trigger coordinates appear in the evidence panel.')
    with detail_col:
        if selected:
            st.subheader(f"{selected['priority']} · {selected['type']}")
            st.write(f"**{selected['recommended_action']}**")
            st.caption(selected['priority_reason'])
            x, y, _ = selected['coordinates_xyz']
            st.markdown(f"**Severity:** {selected['severity']}  \n**Trigger frame:** {selected['frame_id']:,}  \n**Coordinates:** ({x:,.1f}, {y:,.1f}) px  \n**Game time:** {selected['frame_id'] / 60:.2f} seconds")
            st.caption(f"{counts[selected['type']]} event(s) of this type in the current run. Events may share an underlying cause.")
            st.markdown('**Recommended investigation**')
            st.write({'Wall Clip': 'Inspect the right-wall seam and collision resolution during diagonal jump inputs.',
                'Infinite Fall': 'Inspect floor coverage and add a safe recovery boundary below the level.',
                'Softlock': 'Check pit escape height against the player jump limit; provide an exit or recovery action.',
                'Out of Bounds': 'Trace the last in-arena position and verify world-boundary handling.'}.get(selected['type'], 'Inspect the frame context and reproduction inputs.'))
            render_fix_advisor(selected)
        else:
            st.info('Select a failure point above to inspect its evidence and fix advice.' if bugs else 'The bot is exploring. Detected events will appear here.')
    if selected:
        st.subheader('Visual evidence')
        window = data[(data.frame_id >= selected['frame_id'] - 180) & (data.frame_id <= selected['frame_id'])]
        png = cached_evidence(window, selected, geometry, light_mode)
        st.image(png, caption='Reconstructed from the recorded player position and the level geometry. This is not a game screenshot.')
        st.download_button('Download evidence PNG', png, f"indieqa-{selected['type'].lower().replace(' ', '-')}-{selected['frame_id']}.png", 'image/png', key='evidence')
        with st.expander('Reproduction inputs & frame context'):
            st.caption('Up to 30 inputs immediately before the detection. These are diagnostic context; a standalone deterministic replay also needs the initial game state.')
            sequence = selected['reproduction_sequence']
            st.dataframe(pd.DataFrame({'Frames before trigger': range(-len(sequence), 0), 'Input': sequence}), hide_index=True)
            st.dataframe(window.tail(31), hide_index=True)
    st.subheader('Fix queue')
    st.caption('Sorted by recommended priority, then detection frame. Priorities derive from report severity; the original severity is preserved.')
    columns = ['priority', 'type', 'severity', 'frame_id', 'coordinates_xyz', 'recommended_action']
    st.dataframe(pd.DataFrame(filtered, columns=columns), hide_index=True)
    if filtered:
        exported = [{k: v for k, v in bug.items() if k != 'event_key'} for bug in filtered]
        markdown = '# IndieQA prioritized diagnostics\n\n' + '\n---\n'.join(
            f"Priority: **{b['priority']} — {b['recommended_action']}**\n\n" + BugReporter.format_markdown(b) for b in exported)
        left, right = st.columns(2)
        left.download_button('Download Markdown report', markdown, 'indieqa-prioritized-report.md', 'text/markdown', key='markdown')
        right.download_button('Download JSON reports', json.dumps(exported, indent=2), 'indieqa-prioritized-reports.json', 'application/json', key='json')
    st.caption('Live analysis reads telemetry directly, so reports appear before the simulation ends. Downloads include the current filters.')


dashboard()
