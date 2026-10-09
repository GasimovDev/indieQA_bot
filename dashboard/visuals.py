"""Telemetry-reconstructed visual evidence on the team's real level geometry."""
from __future__ import annotations
from io import BytesIO
from typing import Any
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from dashboard.live import BUG_COLORS, event_window

BG, PANEL, TEXT, MUTED = '#0b1120', '#101c30', '#e2e8f0', '#94a3b8'


def palette(light_mode: bool = False) -> dict[str, str]:
    """Return map colors that preserve contrast in either dashboard theme."""
    if light_mode:
        return {
            'bg': '#f5f7fb', 'panel': '#ffffff', 'text': '#172033', 'muted': '#52627a',
            'collider': '#d9e2ef', 'collider_edge': '#94a3b8', 'spine': '#cbd5e1',
            'grid': '#cbd5e1', 'trail': '#087f73', 'label_edge': '#94a3b8',
        }
    return {
        'bg': BG, 'panel': PANEL, 'text': TEXT, 'muted': MUTED,
        'collider': '#33435b', 'collider_edge': '#61748f', 'spine': '#334155',
        'grid': '#283750', 'trail': '#5eead4', 'label_edge': '#64748b',
    }


def base_map(ax: Any, geometry: dict[str, Any], light_mode: bool = False) -> None:
    colors = palette(light_mode)
    ax.set_facecolor(colors['panel'])
    for solid in geometry['colliders']:
        ax.add_patch(Rectangle((solid['x'], solid['y']), solid['w'], solid['h'],
                              facecolor=colors['collider'], edgecolor=colors['collider_edge'], linewidth=.7, zorder=2))
    ax.set_xlim(-35, geometry['world']['width'] + 45)
    ax.set_ylim(geometry['world']['height'] + 35, -35)
    ax.set_aspect('equal')
    ax.tick_params(colors=colors['muted'], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(colors['spine'])
    ax.set_xlabel('X · pixels', color=colors['muted'], fontsize=9)
    ax.set_ylabel('Y · pixels downward', color=colors['muted'], fontsize=9)
    ax.grid(color=colors['grid'], alpha=.45 if light_mode else .3, linewidth=.5)


def plot_position(bug: dict[str, Any], data: pd.DataFrame, geometry: dict[str, Any]) -> tuple[float, float, bool]:
    x, y = bug['coordinates_xyz'][:2]
    w, h = geometry['world']['width'], geometry['world']['height']
    outside = not (0 <= x <= w and 0 <= y <= h)
    if outside:
        window = event_window(data, int(bug['frame_id']), preceding=600)
        visible = window[window.pos_x.between(0, w) & window.pos_y.between(0, h)]
        if not visible.empty:
            return float(visible.iloc[-1].pos_x), float(visible.iloc[-1].pos_y), True
        return float(np.clip(x, 0, w)), float(np.clip(y, 0, h)), True
    return float(x), float(y), False


def overview(data: pd.DataFrame, bugs: list[dict[str, Any]], geometry: dict[str, Any],
             selected: str | None = None, heatmap: bool = True,
             light_mode: bool = False) -> Figure:
    colors = palette(light_mode)
    fig, ax = plt.subplots(figsize=(11, 6.4), facecolor=colors['bg'])
    base_map(ax, geometry, light_mode)
    if heatmap and not data.empty:
        ax.hist2d(data.pos_x, data.pos_y, bins=(40, 30), range=[[0, 800], [0, 600]],
                  cmap='GnBu', cmin=1, norm=LogNorm(), alpha=.5, zorder=1)
    trail = data.tail(240).copy()
    if not trail.empty:
        jumps = (np.hypot(trail.pos_x.diff(), trail.pos_y.diff()) > 60) | ~trail.pos_x.between(-35, 845) | ~trail.pos_y.between(-35, 635)
        trail.loc[jumps, ['pos_x', 'pos_y']] = np.nan
        ax.plot(trail.pos_x + 16, trail.pos_y + 16, color=colors['trail'], lw=1.5, alpha=.8, zorder=3)
        latest = data.iloc[-1]
        if 0 <= latest.pos_x <= 800 and 0 <= latest.pos_y <= 600:
            ax.add_patch(Rectangle((latest.pos_x, latest.pos_y), 32, 32, facecolor=colors['trail'], edgecolor='white', zorder=5))
    grouped: dict[str, list[tuple[float, float]]] = {}
    for bug in bugs:
        x, y, _ = plot_position(bug, data, geometry)
        grouped.setdefault(bug['type'], []).append((x, y))
    for kind, points in grouped.items():
        ax.scatter(*zip(*points), color=BUG_COLORS.get(kind, '#fb7185'), marker='X', s=95,
                   edgecolors='white', linewidths=.5, zorder=6, label=f'{kind} · {len(points)}')
    focus = next((b for b in bugs if b.get('event_key') == selected), None)
    if focus:
        x, y, projected = plot_position(focus, data, geometry)
        ax.scatter([x], [y], s=460, facecolors='none', edgecolors='white', linewidths=2, zorder=7)
        label = f"{focus['priority']}  {focus['type']}\nframe {focus['frame_id']}" + (' · last arena point' if projected else '')
        ax.annotate(label, (x, y), xytext=(min(max(x-170, 25), 560), max(y-105, 50)),
                    color=colors['text'], fontsize=9, weight='bold', bbox=dict(boxstyle='round,pad=.6', fc=colors['bg'], ec=colors['label_edge']),
                    arrowprops=dict(arrowstyle='->', color=colors['text']), zorder=8)
    ax.text(270, 470, 'FLOOR GAP', color='#7dd3fc', ha='center', fontsize=7, rotation=90, zorder=4)
    ax.text(460, 485, 'PIT', color='#fcd34d', ha='center', fontsize=7, zorder=4)
    if grouped:
        legend = ax.legend(loc='upper left', facecolor=colors['bg'], edgecolor=colors['label_edge'], fontsize=8)
        for text in legend.get_texts():
            text.set_color(colors['text'])
    fig.tight_layout(pad=1.4)
    return fig


def evidence_png(data: pd.DataFrame, bug: dict[str, Any], geometry: dict[str, Any],
                 light_mode: bool = False) -> bytes:
    colors = palette(light_mode)
    window = event_window(data, int(bug['frame_id']), preceding=180)
    if window.empty:
        raise ValueError('Trigger frame is not present in this telemetry run.')
    trigger = window.iloc[-1]
    inside = window[window.pos_x.between(0, 800) & window.pos_y.between(0, 600)]
    before = inside.iloc[-1] if not inside.empty and not (0 <= trigger.pos_x <= 800 and 0 <= trigger.pos_y <= 600) else window.iloc[max(0, len(window)-31)]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), facecolor=colors['bg'])
    for ax, row, label in zip(axes, [before, trigger], ['Approach / last arena position', 'Detection frame']):
        base_map(ax, geometry, light_mode)
        x, y = float(row.pos_x), float(row.pos_y)
        ax.set_xlim(x-140, x+172)
        ax.set_ylim(y+130, y-110)
        partial = window[window.frame_id <= row.frame_id]
        ax.plot(partial.pos_x+16, partial.pos_y+16, color=colors['trail'], alpha=.8, lw=2)
        ax.add_patch(Rectangle((x, y), 32, 32, facecolor=BUG_COLORS.get(bug['type'], '#fb7185'), edgecolor='white', lw=2, zorder=9))
        ax.set_title(f"{label}\nframe {int(row.frame_id)} · ({x:,.1f}, {y:,.1f})", color=colors['text'], fontsize=10)
        ax.text(.03, .04, f"input: {row.active_input}\nvelocity: ({row.vel_x:.1f}, {row.vel_y:.1f}) px/frame", transform=ax.transAxes,
                color=colors['text'], fontsize=8, bbox=dict(fc=colors['bg'], ec=colors['label_edge'], alpha=.95), zorder=10)
    fig.suptitle(f"{bug['priority']}  /  {bug['type']}  /  {bug['severity']}", color=colors['text'], fontsize=16, weight='bold')
    fig.text(.5, .025, 'Visual reconstruction from recorded telemetry + level geometry · not a captured game screenshot', ha='center', color=colors['muted'], fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, .94))
    output = BytesIO()
    fig.savefig(output, format='png', dpi=140, facecolor=colors['bg'])
    plt.close(fig)
    return output.getvalue()
