"""Data layer for the IndieQA backup website (branch backup-plan1).

Turns raw telemetry + Person 2's detector output into what the site shows:
bug events with their on-map origin, grouped issues with a priority tier,
walkable-ground coverage, a map figure and per-bug "screenshots"
(reconstructed from telemetry with the exact game geometry and colours).
"""

from __future__ import annotations

import io
import math
import os
from dataclasses import dataclass, field
from typing import Any, Final, Sequence

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pygame
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

from analysis.bug_detector import BugDetector
from core.engine import FPS, PLAYER_HEIGHT, PLAYER_WIDTH, WORLD_HEIGHT, WORLD_WIDTH, ColliderKind, Level

# ---------------------------------------------------------------- palette
# Two themes: a soft (low-glare) creme light mode and a warm dark mode, with the same colour roles.
THEMES: Final[dict[str, dict[str, str]]] = {
    "light": {
        "bg": "#EFE8D8", "card": "#F8F3E8", "card2": "#ECE3D0", "border": "#D9CCB1",
        "ink": "#2B251D", "muted": "#675D4B", "red": "#B4513D", "red_soft": "#EFD3C9",
        "green": "#4A8758", "green_soft": "#D3E5CE", "sand": "#B98E43",
        "solid": "#CDBF9F", "seam": "#D69A8D", "zone": "#EBCFC6",
        "P0": "#B3443A", "P1": "#D2786A", "P2": "#B98E43", "P3": "#5C9A69",
    },
    "dark": {
        "bg": "#181613", "card": "#221F1A", "card2": "#2C2822", "border": "#3A342B",
        "ink": "#EEE6D4", "muted": "#ADA18A", "red": "#E58771", "red_soft": "#43271F",
        "green": "#86C493", "green_soft": "#1F3526", "sand": "#D8B272",
        "solid": "#4A443A", "seam": "#8C4E43", "zone": "#3A221D",
        "P0": "#E6705C", "P1": "#EBA092", "P2": "#D8B272", "P3": "#86C493",
    },
}


def palette(theme: str) -> dict[str, str]:
    return THEMES.get(theme, THEMES["light"])

# --------------------------------------------------------------- priority
SEVERITY_WEIGHT: Final[dict[str, float]] = {"CRITICAL": 3.0, "HIGH": 2.0, "MEDIUM": 1.0, "LOW": 0.5}
ROOT_TYPES: Final[tuple[str, ...]] = ("Wall Clip", "Infinite Fall", "Softlock")
# A bug is a SYMPTOM when its cause is another bug close in time: (types it can follow, root frame window
# relative to the symptom frame). Checked in this order, so OOB links to real root causes only.
SYMPTOM_RULES: Final[tuple[tuple[str, tuple[str, ...], int, int], ...]] = (
    ("Infinite Fall", ("Wall Clip",), -200, 0),             # falling forever after being clipped out of the map
    ("Out of Bounds", ("Wall Clip", "Infinite Fall", "Softlock"), -150, 150),
)
TIERS: Final[tuple[tuple[str, float, str], ...]] = (
    ("P0", 12.0, "Fix before launch"),
    ("P1", 8.0, "Fix this sprint"),
    ("P2", 4.0, "Schedule"),
    ("P3", 0.0, "Monitor"),
)
TYPE_BLURB: Final[dict[str, str]] = {
    "Wall Clip": "Player passed through a solid wall",
    "Infinite Fall": "Player fell with no ground and no reset",
    "Softlock": "Player is stuck while still pressing buttons",
    "Out of Bounds": "Player left the map",
}
SURFACE_BIN: Final[int] = 16  # px, resolution of the walkable-ground coverage metric


@dataclass
class BugEvent:
    index: int
    type: str
    severity: str
    frame_id: int
    timestamp: float
    x: float
    y: float
    origin_x: float
    origin_y: float
    location: str
    reproduction: list[str]
    root_index: int | None = None  # for symptoms: the bug that caused it

    @property
    def game_time(self) -> str:
        return format_game_time(self.frame_id)


@dataclass
class Issue:
    key: str
    type: str
    severity: str
    location: str
    events: list[BugEvent] = field(default_factory=list)
    score: float = 0.0
    tier: str = "P3"
    tier_label: str = "Monitor"
    symptom_of: str | None = None

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def first(self) -> BugEvent:
        return min(self.events, key=lambda e: e.frame_id)

    @property
    def origin(self) -> tuple[float, float]:
        return (
            float(np.mean([e.origin_x for e in self.events])),
            float(np.mean([e.origin_y for e in self.events])),
        )


@dataclass
class Analysis:
    frames: int
    game_minutes: float
    events: list[BugEvent]
    issues: list[Issue]
    coverage_pct: float
    surface_bins_total: int
    surface_bins_visited: int


def format_game_time(frame_id: int) -> str:
    seconds = frame_id / FPS
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


# ------------------------------------------------------------------ input
def load_telemetry(path: str) -> pd.DataFrame:
    """Read the (possibly still growing) telemetry CSV; incomplete trailing rows are dropped."""
    df = pd.read_csv(path, on_bad_lines="skip")
    numeric = ["frame_id", "timestamp", "pos_x", "pos_y", "vel_x", "vel_y"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=numeric + ["is_grounded", "collision_state"])
    df = df[df["is_grounded"].astype(str).isin(["True", "False"]) & df["collision_state"].astype(str).isin(["True", "False"])]
    df["frame_id"] = df["frame_id"].astype(int)
    df["active_input"] = df["active_input"].fillna("none").astype(str)
    return df.reset_index(drop=True)


def analyse(df: pd.DataFrame, level: Level) -> Analysis:
    raw: list[dict[str, Any]] = BugDetector(WORLD_WIDTH, WORLD_HEIGHT).process_telemetry(df) if len(df) else []
    events = _build_events(df, raw, level)
    game_minutes = len(df) / FPS / 60.0
    issues = _build_issues(events, game_minutes)
    total, visited = _surface_coverage(df, level)
    return Analysis(
        frames=len(df),
        game_minutes=game_minutes,
        events=events,
        issues=issues,
        coverage_pct=100.0 * visited / total if total else 0.0,
        surface_bins_total=total,
        surface_bins_visited=visited,
    )


# ---------------------------------------------------------------- events
def _in_world(x: float, y: float) -> bool:
    cx, cy = x + PLAYER_WIDTH / 2, y + PLAYER_HEIGHT / 2
    return 0 <= cx <= WORLD_WIDTH and 0 <= cy <= WORLD_HEIGHT


def _location(x: float, y: float, level: Level) -> str:
    cx, cy = x + PLAYER_WIDTH / 2, y + PLAYER_HEIGHT / 2
    if level.seam.inflate(120, 100).collidepoint(cx, cy):
        return f"Right wall seam (x {level.seam.left}, y {level.seam.top}-{level.seam.bottom})"
    gap = level.fall_gap
    if gap.left - 8 <= cx <= gap.right + 8 and cy >= gap.top - PLAYER_HEIGHT:
        return f"Floor gap (x {gap.left}-{gap.right})"
    pit = level.pit
    if pit.left - 8 <= cx <= pit.right + 8 and cy >= pit.top - PLAYER_HEIGHT:
        return f"Pit (x {pit.left}-{pit.right}, {pit.height} px deep)"
    return f"Map cell x {int(cx // 100) * 100}-{int(cx // 100) * 100 + 100}, y {int(cy // 100) * 100}-{int(cy // 100) * 100 + 100}"


def _build_events(df: pd.DataFrame, raw: Sequence[dict[str, Any]], level: Level) -> list[BugEvent]:
    if not len(df):
        return []
    frames = df["frame_id"].to_numpy()
    xs = df["pos_x"].to_numpy()
    ys = df["pos_y"].to_numpy()
    events: list[BugEvent] = []
    for i, bug in enumerate(raw):
        frame = int(bug["frame_id"])
        row = int(np.searchsorted(frames, frame))
        row = min(row, len(frames) - 1)
        # Origin = last in-map position before the bug (the clip/fall starts there).
        ox, oy = float(xs[row]), float(ys[row])
        for r in range(row - 1, max(-1, row - 300), -1):
            if _in_world(xs[r], ys[r]):
                ox, oy = float(xs[r]), float(ys[r])
                break
        x, y, _ = bug.get("coordinates_xyz", [xs[row], ys[row], 0.0])
        events.append(
            BugEvent(
                index=i,
                type=str(bug["type"]),
                severity=str(bug.get("severity", "MEDIUM")),
                frame_id=frame,
                timestamp=float(bug.get("timestamp", 0.0)),
                x=float(x),
                y=float(y),
                origin_x=ox,
                origin_y=oy,
                location=_location(ox, oy, level),
                reproduction=[str(s) for s in bug.get("reproduction_sequence", [])],
            )
        )
    # Consequences of another bug (e.g. the fall after a wall clip) are symptoms, not separate problems.
    for symptom_type, cause_types, lo, hi in SYMPTOM_RULES:
        roots = [r for r in events if r.type in cause_types and r.root_index is None]
        for e in events:
            if e.type != symptom_type or e.root_index is not None:
                continue
            near = [r for r in roots if e.frame_id + lo <= r.frame_id <= e.frame_id + hi]
            if near:
                e.root_index = min(near, key=lambda r: abs(r.frame_id - e.frame_id)).index
    return events


def _tier(score: float) -> tuple[str, str]:
    for name, threshold, label in TIERS:
        if score >= threshold:
            return name, label
    return TIERS[-1][0], TIERS[-1][2]


def priority_score(severity: str, count: int, game_minutes: float) -> float:
    """severity x (1 + log2(1 + occurrences per 10 min of gameplay)); observation time floored at 1 min."""
    rate = count * 10.0 / max(game_minutes, 1.0)
    return SEVERITY_WEIGHT.get(severity, 1.0) * (1.0 + math.log2(1.0 + rate))


def _build_issues(events: list[BugEvent], game_minutes: float) -> list[Issue]:
    by_index = {e.index: e for e in events}
    groups: dict[str, Issue] = {}
    for e in events:
        if e.root_index is not None:
            root = by_index[e.root_index]
            key = f"{e.type}|symptom|{root.type}|{root.location}"
            issue = groups.setdefault(
                key, Issue(key, e.type, e.severity, f"After {root.type} at {root.location}", symptom_of=root.type)
            )
        else:
            key = f"{e.type}|{e.location}"
            issue = groups.setdefault(key, Issue(key, e.type, e.severity, e.location))
        issue.events.append(e)
    for issue in groups.values():
        issue.score = priority_score(issue.severity, issue.count, game_minutes)
        if issue.symptom_of is not None:
            issue.tier, issue.tier_label = "P3", f"Symptom of {issue.symptom_of}"
        else:
            issue.tier, issue.tier_label = _tier(issue.score)
    order = {name: i for i, (name, _, _) in enumerate(TIERS)}
    return sorted(groups.values(), key=lambda i: (order[i.tier], -i.score, i.first.frame_id))


# -------------------------------------------------------------- coverage
def _walkable_surfaces(level: Level) -> list[tuple[int, int, int]]:
    """(left, right, top) of every collider top that a player can stand on."""
    surfaces: list[tuple[int, int, int]] = []
    rects = [c.rect for c in level.colliders]
    for r in rects:
        if r.top <= 16 or r.width < SURFACE_BIN:
            continue  # ceiling / walls
        x = r.left
        while x < r.right:
            seg_end = min(x + SURFACE_BIN, r.right)
            probe = pygame.Rect(x, r.top - PLAYER_HEIGHT, seg_end - x, PLAYER_HEIGHT)
            if not any(o is not r and o.colliderect(probe) for o in rects):
                surfaces.append((x, seg_end, r.top))
            x = seg_end
    return surfaces


def _surface_coverage(df: pd.DataFrame, level: Level) -> tuple[int, int]:
    surfaces = _walkable_surfaces(level)
    if not len(df):
        return len(surfaces), 0
    grounded = df[df["is_grounded"].astype(str) == "True"]
    feet = (grounded["pos_y"] + PLAYER_HEIGHT).to_numpy()
    left = grounded["pos_x"].to_numpy()
    visited = 0
    for s_left, s_right, top in surfaces:
        on = (np.abs(feet - top) < 1.0) & (left < s_right) & (left + PLAYER_WIDTH > s_left)
        visited += bool(on.any())
    return len(surfaces), visited


# ------------------------------------------------------------------ map
def _blur(a: np.ndarray, passes: int = 2) -> np.ndarray:
    kernel = np.array([1.0, 4.0, 6.0, 4.0, 1.0]) / 16.0
    for _ in range(passes):
        a = np.apply_along_axis(lambda r: np.convolve(r, kernel, mode="same"), 0, a)
        a = np.apply_along_axis(lambda r: np.convolve(r, kernel, mode="same"), 1, a)
    return a


def render_map(df: pd.DataFrame, issues: Sequence[Issue], level: Level, theme: str = "light") -> bytes:
    pal = palette(theme)
    fig, ax = plt.subplots(figsize=(8.0, 6.2), dpi=170)
    fig.patch.set_facecolor(pal["card"])
    ax.set_facecolor(pal["bg"])
    for zone in (level.fall_gap, level.pit):
        ax.add_patch(Rectangle((zone.left, zone.top), zone.width, zone.height, color=pal["zone"], zorder=1))
    for c in level.colliders:
        colour = pal["seam"] if c.kind is ColliderKind.SEAM else pal["solid"]
        ax.add_patch(Rectangle((c.rect.left, c.rect.top), c.rect.width, c.rect.height, color=colour, zorder=2))
    ax.add_patch(
        Rectangle((level.seam.left - 4, level.seam.top - 3), level.seam.width + 8, level.seam.height + 6,
                  fill=False, edgecolor=pal["red"], linewidth=1.6, zorder=3)
    )
    if len(df):
        cx = (df["pos_x"] + PLAYER_WIDTH / 2).to_numpy()
        cy = (df["pos_y"] + PLAYER_HEIGHT / 2).to_numpy()
        keep = (cx >= 0) & (cx <= WORLD_WIDTH) & (cy >= 0) & (cy <= WORLD_HEIGHT)
        if keep.any():
            heat, _, _ = np.histogram2d(cx[keep], cy[keep], bins=(160, 120), range=((0, WORLD_WIDTH), (0, WORLD_HEIGHT)))
            heat = _blur(np.log1p(heat.T))
            if heat.max() > 0:
                g = matplotlib.colors.to_rgb(pal["green"])
                cmap = LinearSegmentedColormap.from_list("iq_heat", [(*g, 0.0), (*g, 0.95 if theme == "dark" else 0.85)])
                ax.imshow((heat / heat.max()) ** 0.6, extent=(0, WORLD_WIDTH, WORLD_HEIGHT, 0), cmap=cmap,
                          interpolation="bicubic", zorder=4)
    for issue in issues:
        if issue.symptom_of is not None:
            continue
        ox, oy = issue.origin
        px, py = ox + PLAYER_WIDTH / 2, oy + PLAYER_HEIGHT / 2
        colour = pal[issue.tier]
        size = 260 + 50 * min(issue.count, 30)
        ax.scatter([px], [py], s=size, color=colour, alpha=0.28, zorder=5, linewidths=0)
        ax.scatter([px], [py], s=130, color=colour, edgecolors=pal["card"], linewidths=1.8, zorder=6)
        label = f"{issue.tier} · {issue.type} ×{issue.count}"
        dx = -12 if (px > WORLD_WIDTH * 0.7 or WORLD_WIDTH * 0.2 < px < WORLD_WIDTH * 0.45) else 12
        ax.annotate(label, (px, py), xytext=(dx, 20), textcoords="offset points",
                    ha="right" if dx < 0 else "left", fontsize=10, fontweight="bold", color=pal["ink"], zorder=7,
                    bbox=dict(boxstyle="round,pad=0.35", fc=pal["card"], ec=colour, lw=1.2))
    ax.set_xlim(-10, WORLD_WIDTH + 10)
    ax.set_ylim(WORLD_HEIGHT + 10, -10)
    ax.set_aspect("equal")
    ax.tick_params(colors=pal["muted"], labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(pal["border"])
    fig.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------ snapshots
SNAP_W: Final[int] = 1600
SNAP_H: Final[int] = 1200
_GAME_BG = (24, 26, 32)
_SOLID = (110, 115, 125)
_SEAM = (150, 70, 70)


def _trail(df: pd.DataFrame, frame_id: int, trail_frames: int) -> tuple[np.ndarray, np.ndarray]:
    frames = df["frame_id"].to_numpy()
    row = min(int(np.searchsorted(frames, frame_id)), len(frames) - 1)
    start = max(0, row - trail_frames)
    xs = df["pos_x"].to_numpy()[start : row + 1]
    ys = df["pos_y"].to_numpy()[start : row + 1]
    vxs = df["vel_x"].to_numpy()[start : row + 1]
    vys = df["vel_y"].to_numpy()[start : row + 1]
    # Cut the trail at a respawn: a jump that the velocity does not explain (the bug frame itself is kept).
    for k in range(len(xs) - 2, 0, -1):
        if math.hypot(xs[k] - xs[k - 1] - vxs[k], ys[k] - ys[k - 1] - vys[k]) > 25:
            return xs[k:], ys[k:]
    return xs, ys


def render_snapshot(
    df: pd.DataFrame, event: BugEvent, level: Level, trail_frames: int = 240, zoom: bool = True
) -> np.ndarray:
    """Game-style 'screenshot' of the bug moment at 1600x1200, rebuilt from telemetry.

    The level is drawn with the game's own geometry and colours directly at output resolution
    (no upscaling), optionally zoomed onto the error point.
    """
    from pygame import gfxdraw

    if not pygame.font.get_init():
        pygame.font.init()
    xs, ys = _trail(df, event.frame_id, trail_frames)
    half_w, half_h = PLAYER_WIDTH / 2, PLAYER_HEIGHT / 2
    sx, sy = event.origin_x + half_w, event.origin_y + half_h  # last on-map position (centre)
    ex, ey = event.x + half_w, event.y + half_h  # bug position (centre)
    inside = 0 <= ex <= WORLD_WIDTH and 0 <= ey <= WORLD_HEIGHT
    norm = math.hypot(ex - sx, ey - sy) or 1.0
    ux, uy = (ex - sx) / norm, (ey - sy) / norm

    # View in world coordinates, 4:3.
    if zoom:
        fx = [sx, min(max(ex, 0.0), WORLD_WIDTH)] + [float(x) + half_w for x in xs[-60:] if 0 <= x <= WORLD_WIDTH]
        fy = [sy, min(max(ey, 0.0), WORLD_HEIGHT)] + [float(y) + half_h for y in ys[-60:] if 0 <= y <= WORLD_HEIGHT]
        if not inside:
            fx.append(sx + ux * 70)
            fy.append(sy + uy * 70)
        lx, rx, ty, by = min(fx) - 110, max(fx) + 110, min(fy) - 110, max(fy) + 110
        vw = min(max(rx - lx, (by - ty) * 4 / 3, 360.0), float(WORLD_WIDTH))
        vh = vw * 3 / 4
        vx = min(max((lx + rx) / 2 - vw / 2, 0.0), WORLD_WIDTH - vw)
        vy = min(max((ty + by) / 2 - vh / 2, 0.0), WORLD_HEIGHT - vh)
    else:
        vx, vy, vw, vh = 0.0, 0.0, float(WORLD_WIDTH), float(WORLD_HEIGHT)
    scale = SNAP_W / vw

    def pt(x: float, y: float) -> tuple[int, int]:
        return round((x - vx) * scale), round((y - vy) * scale)

    def rect(x: float, y: float, w: float, h: float) -> pygame.Rect:
        left, top = pt(x, y)
        return pygame.Rect(left, top, max(1, round(w * scale)), max(1, round(h * scale)))

    surf = pygame.Surface((SNAP_W, SNAP_H))
    surf.fill(_GAME_BG)
    for zone, colour in ((level.fall_gap, (90, 30, 30)), (level.pit, (90, 80, 20))):
        pygame.draw.rect(surf, colour, rect(zone.x, zone.y, zone.w, zone.h))
    for c in level.colliders:
        pygame.draw.rect(surf, _SEAM if c.kind is ColliderKind.SEAM else _SOLID, rect(c.rect.x, c.rect.y, c.rect.w, c.rect.h))
    seam = level.seam.inflate(6, 0)
    pygame.draw.rect(surf, (255, 60, 60), rect(seam.x, seam.y, seam.w, seam.h), max(2, round(scale)))

    # Path before the bug.
    dot = max(3, round(1.6 + scale))
    n = len(xs)
    for k, (px, py) in enumerate(zip(xs[:-1], ys[:-1])):
        cx, cy = px + half_w, py + half_h
        if 0 <= cx <= WORLD_WIDTH and 0 <= cy <= WORLD_HEIGHT:
            shade = int(80 + 175 * (k + 1) / max(n, 1))
            colour = (shade // 3, shade, 255)
            qx, qy = pt(cx, cy)
            gfxdraw.filled_circle(surf, qx, qy, dot, colour)
            gfxdraw.aacircle(surf, qx, qy, dot, colour)

    # Last on-map position + bug.
    line_w = max(3, round(scale * 1.2))
    pygame.draw.rect(surf, (80, 200, 255), rect(event.origin_x, event.origin_y, PLAYER_WIDTH, PLAYER_HEIGHT), line_w)
    if inside:
        pygame.draw.line(surf, (255, 200, 200), pt(sx, sy), pt(ex, ey), line_w)
        pygame.draw.rect(surf, (255, 70, 70), rect(event.x, event.y, PLAYER_WIDTH, PLAYER_HEIGHT))
    else:
        length = 70.0
        tx, ty = sx + ux * length, sy + uy * length
        for _ in range(25):  # keep the arrow tip inside the view
            tx, ty = sx + ux * length, sy + uy * length
            if vx + 4 <= tx <= vx + vw - 4 and vy + 4 <= ty <= vy + vh - 4:
                break
            length *= 0.85
        head, wing = 16.0, 9.0
        bx, by = tx - ux * head, ty - uy * head
        pygame.draw.line(surf, (255, 120, 120), pt(sx, sy), pt(bx, by), line_w + 1)
        tri = [pt(tx, ty), pt(bx - uy * wing, by + ux * wing), pt(bx + uy * wing, by - ux * wing)]
        gfxdraw.filled_polygon(surf, tri, (255, 70, 70))
        gfxdraw.aapolygon(surf, tri, (255, 70, 70))

    # Text, rendered at output resolution so it stays crisp.
    font = pygame.font.Font(None, 44)
    small = pygame.font.Font(None, 34)
    panel = pygame.Surface((SNAP_W, 60), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 165))
    surf.blit(panel, (0, 0))
    header = f"{event.type}   |   frame {event.frame_id:,}   |   game time {event.game_time}"
    surf.blit(font.render(header, True, (242, 242, 242)), (22, 16))
    legend = small.render("blue box = last position on map  ·  red = bug  ·  dots = path before the bug", True,
                          (215, 215, 215))
    lbg = pygame.Surface((legend.get_width() + 20, legend.get_height() + 12), pygame.SRCALPHA)
    lbg.fill((0, 0, 0, 120))
    surf.blit(lbg, (SNAP_W - legend.get_width() - 32, 72))
    surf.blit(legend, (SNAP_W - legend.get_width() - 22, 78))
    if not inside:
        note = font.render(f"player left the map  ->  x {event.x:,.0f}, y {event.y:,.0f}", True, (255, 222, 222))
        bg = pygame.Surface((note.get_width() + 28, note.get_height() + 18), pygame.SRCALPHA)
        bg.fill((125, 32, 32, 215))
        surf.blit(bg, (22, SNAP_H - note.get_height() - 40))
        surf.blit(note, (36, SNAP_H - note.get_height() - 31))
    return pygame.surfarray.array3d(surf).swapaxes(0, 1).copy()


def bug_markdown(event: BugEvent, issue: Issue) -> str:
    steps = "\n".join(f"{i + 1}. `{s}`" for i, s in enumerate(event.reproduction))
    return (
        f"# {issue.tier} - {event.type}\n\n"
        f"- **Priority:** {issue.tier} ({issue.tier_label}), score {issue.score:.1f}\n"
        f"- **Severity:** {event.severity}\n"
        f"- **Where:** {event.location}\n"
        f"- **When:** frame {event.frame_id} (game time {event.game_time})\n"
        f"- **Bug position:** x {event.x:.1f}, y {event.y:.1f}\n"
        f"- **Occurrences of this issue:** {issue.count}\n\n"
        f"## How to reproduce (last {len(event.reproduction)} inputs before the bug)\n{steps}\n"
    )
