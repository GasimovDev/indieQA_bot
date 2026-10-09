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
CREME: Final[str] = "#F7F1E3"
CARD: Final[str] = "#FFFBF3"
BORDER: Final[str] = "#E6DAC3"
INK: Final[str] = "#3A3328"
MUTED: Final[str] = "#857A66"
RED: Final[str] = "#C8553D"
RED_SOFT: Final[str] = "#F4D9D1"
GREEN: Final[str] = "#5E9C6B"
GREEN_SOFT: Final[str] = "#DCEBD8"
SAND: Final[str] = "#D4A85F"

TIER_COLOURS: Final[dict[str, str]] = {"P0": "#B8463A", "P1": "#DE8577", "P2": SAND, "P3": "#6FA77A"}

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
_HEAT = LinearSegmentedColormap.from_list("iq_heat", [(0.0, (0.37, 0.61, 0.42, 0.0)), (1.0, (0.37, 0.61, 0.42, 0.85))])


def render_map(df: pd.DataFrame, issues: Sequence[Issue], level: Level) -> bytes:
    fig, ax = plt.subplots(figsize=(8.0, 6.3), dpi=110)
    fig.patch.set_facecolor(CARD)
    ax.set_facecolor(CREME)
    for zone in (level.fall_gap, level.pit):
        ax.add_patch(Rectangle((zone.left, zone.top), zone.width, zone.height, color=RED_SOFT, zorder=1))
    for c in level.colliders:
        colour = "#D9A397" if c.kind is ColliderKind.SEAM else "#CFC3A8"
        ax.add_patch(Rectangle((c.rect.left, c.rect.top), c.rect.width, c.rect.height, color=colour, zorder=2))
    ax.add_patch(
        Rectangle((level.seam.left - 4, level.seam.top - 3), level.seam.width + 8, level.seam.height + 6,
                  fill=False, edgecolor=RED, linewidth=1.6, zorder=3)
    )
    if len(df):
        cx = (df["pos_x"] + PLAYER_WIDTH / 2).to_numpy()
        cy = (df["pos_y"] + PLAYER_HEIGHT / 2).to_numpy()
        keep = (cx >= 0) & (cx <= WORLD_WIDTH) & (cy >= 0) & (cy <= WORLD_HEIGHT)
        if keep.any():
            heat, _, _ = np.histogram2d(cx[keep], cy[keep], bins=(80, 60), range=((0, WORLD_WIDTH), (0, WORLD_HEIGHT)))
            heat = np.log1p(heat.T)
            if heat.max() > 0:
                ax.imshow(heat / heat.max(), extent=(0, WORLD_WIDTH, WORLD_HEIGHT, 0), cmap=_HEAT,
                          interpolation="bilinear", zorder=4)
    for issue in issues:
        if issue.symptom_of is not None:
            continue
        ox, oy = issue.origin
        px, py = ox + PLAYER_WIDTH / 2, oy + PLAYER_HEIGHT / 2
        colour = TIER_COLOURS[issue.tier]
        size = 260 + 50 * min(issue.count, 30)
        ax.scatter([px], [py], s=size, color=colour, alpha=0.25, zorder=5, linewidths=0)
        ax.scatter([px], [py], s=130, color=colour, edgecolors="white", linewidths=1.8, zorder=6)
        label = f"{issue.tier} · {issue.type} ×{issue.count}"
        dx = -12 if (px > WORLD_WIDTH * 0.7 or WORLD_WIDTH * 0.2 < px < WORLD_WIDTH * 0.45) else 12
        ax.annotate(label, (px, py), xytext=(dx, 20), textcoords="offset points",
                    ha="right" if dx < 0 else "left", fontsize=10, fontweight="bold", color=INK, zorder=7,
                    bbox=dict(boxstyle="round,pad=0.35", fc=CARD, ec=colour, lw=1.2))
    ax.set_xlim(-10, WORLD_WIDTH + 10)
    ax.set_ylim(WORLD_HEIGHT + 10, -10)
    ax.set_aspect("equal")
    ax.tick_params(colors=MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    fig.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------ snapshots
_GAME_BG = (24, 26, 32)
_SOLID = (110, 115, 125)
_SEAM = (150, 70, 70)


def render_snapshot(
    df: pd.DataFrame, event: BugEvent, level: Level, trail_frames: int = 240, zoom: bool = True
) -> np.ndarray:
    """Game-style 'screenshot' of the bug moment, rebuilt from telemetry (same geometry + colours as the game)."""
    if not pygame.font.get_init():
        pygame.font.init()
    surf = pygame.Surface((WORLD_WIDTH, WORLD_HEIGHT))
    surf.fill(_GAME_BG)
    pygame.draw.rect(surf, (90, 30, 30), level.fall_gap)
    pygame.draw.rect(surf, (90, 80, 20), level.pit)
    for c in level.colliders:
        pygame.draw.rect(surf, _SEAM if c.kind is ColliderKind.SEAM else _SOLID, c.rect)
    pygame.draw.rect(surf, (255, 60, 60), level.seam.inflate(6, 0), 1)

    frames = df["frame_id"].to_numpy()
    row = min(int(np.searchsorted(frames, event.frame_id)), len(frames) - 1)
    start = max(0, row - trail_frames)
    xs = df["pos_x"].to_numpy()[start : row + 1]
    ys = df["pos_y"].to_numpy()[start : row + 1]
    vxs = df["vel_x"].to_numpy()[start : row + 1]
    vys = df["vel_y"].to_numpy()[start : row + 1]
    # Cut the trail at a respawn: a jump that the velocity does not explain (the bug frame itself is kept).
    for k in range(len(xs) - 2, 0, -1):
        if math.hypot(xs[k] - xs[k - 1] - vxs[k], ys[k] - ys[k - 1] - vys[k]) > 25:
            xs, ys = xs[k:], ys[k:]
            break

    def clamp(px: float, py: float) -> tuple[int, int, bool]:
        inside = 0 <= px <= WORLD_WIDTH and 0 <= py <= WORLD_HEIGHT
        return int(min(max(px, 6), WORLD_WIDTH - 6)), int(min(max(py, 6), WORLD_HEIGHT - 6)), inside

    for k, (px, py) in enumerate(zip(xs[:-1], ys[:-1])):
        cx, cy, inside = clamp(px + PLAYER_WIDTH / 2, py + PLAYER_HEIGHT / 2)
        if inside:
            shade = int(70 + 185 * (k + 1) / max(len(xs), 1))
            pygame.draw.circle(surf, (shade // 3, shade, 255), (cx, cy), 2)

    font = pygame.font.Font(None, 22)
    small = pygame.font.Font(None, 19)
    ox, oy = event.origin_x, event.origin_y
    pygame.draw.rect(surf, (80, 200, 255), pygame.Rect(round(ox), round(oy), PLAYER_WIDTH, PLAYER_HEIGHT), 2)

    bx, by, inside = clamp(event.x + PLAYER_WIDTH / 2, event.y + PLAYER_HEIGHT / 2)
    if inside:
        pygame.draw.rect(surf, (255, 70, 70), pygame.Rect(round(event.x), round(event.y), PLAYER_WIDTH, PLAYER_HEIGHT))
        pygame.draw.line(surf, (255, 200, 200), (round(ox + 16), round(oy + 16)), (bx, by), 2)
    else:
        # Off-map: arrow from the last on-map position toward where the player really went.
        sx, sy = ox + PLAYER_WIDTH / 2, oy + PLAYER_HEIGHT / 2
        vx, vy = event.x + PLAYER_WIDTH / 2 - sx, event.y + PLAYER_HEIGHT / 2 - sy
        norm = math.hypot(vx, vy) or 1.0
        ux, uy = vx / norm, vy / norm
        length = 70.0
        for _ in range(20):  # shorten until the arrow tip stays inside the picture
            tx, ty = sx + ux * length, sy + uy * length
            if 4 <= tx <= WORLD_WIDTH - 4 and 4 <= ty <= WORLD_HEIGHT - 4:
                break
            length *= 0.8
        base = (tx - ux * 16, ty - uy * 16)
        left = (base[0] - uy * 9, base[1] + ux * 9)
        right = (base[0] + uy * 9, base[1] - ux * 9)
        pygame.draw.line(surf, (255, 120, 120), (round(sx), round(sy)), (round(base[0]), round(base[1])), 3)
        pygame.draw.polygon(surf, (255, 70, 70), [(tx, ty), left, right])
        bx, by = int(tx), int(ty)

    if zoom:
        # Crop around the action (last on-map position, recent path, bug) and scale it up, keeping 4:3.
        focus_x = [ox + 16, float(bx)] + [float(px) + 16 for px in xs[-60:] if 0 <= px <= WORLD_WIDTH]
        focus_y = [oy + 16, float(by)] + [float(py) + 16 for py in ys[-60:] if 0 <= py <= WORLD_HEIGHT]
        left_x, right_x = min(focus_x) - 110, max(focus_x) + 110
        top_y, bottom_y = min(focus_y) - 110, max(focus_y) + 110
        w = max(right_x - left_x, (bottom_y - top_y) * 4 / 3, 360.0)
        w = min(w, float(WORLD_WIDTH))
        h = w * 3 / 4
        cx, cy = (left_x + right_x) / 2, (top_y + bottom_y) / 2
        x0 = int(min(max(cx - w / 2, 0), WORLD_WIDTH - w))
        y0 = int(min(max(cy - h / 2, 0), WORLD_HEIGHT - h))
        crop = surf.subsurface(pygame.Rect(x0, y0, int(w), int(h))).copy()
        surf = pygame.transform.smoothscale(crop, (WORLD_WIDTH, WORLD_HEIGHT))

    header = f"{event.type}  |  frame {event.frame_id}  |  game time {event.game_time}"
    panel = pygame.Surface((WORLD_WIDTH, 30), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 150))
    surf.blit(panel, (0, 0))
    surf.blit(font.render(header, True, (240, 240, 240)), (12, 7))
    legend = small.render("blue box = last position on map  ·  red = bug  ·  dots = path before the bug", True, (205, 205, 205))
    surf.blit(legend, (WORLD_WIDTH - legend.get_width() - 12, 40))
    if not inside:
        note = font.render(f"player left the map -> x {event.x:,.0f}, y {event.y:,.0f}", True, (255, 215, 215))
        bg = pygame.Surface((note.get_width() + 16, note.get_height() + 10), pygame.SRCALPHA)
        bg.fill((120, 30, 30, 200))
        surf.blit(bg, (12, WORLD_HEIGHT - note.get_height() - 22))
        surf.blit(note, (20, WORLD_HEIGHT - note.get_height() - 17))
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
