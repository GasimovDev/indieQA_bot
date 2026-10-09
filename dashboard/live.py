"""Read-only live telemetry, run tracking and presentation priorities."""
from __future__ import annotations
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from analysis.bug_detector import BugDetector, REQUIRED_COLUMNS

PRIORITIES = {
    'CRITICAL': ('P0', 'Release blocker', 'Player can escape the level or cross solid geometry.'),
    'HIGH': ('P1', 'Fix before release', 'Play cannot progress without recovery or a restart.'),
    'MEDIUM': ('P2', 'Schedule a fix', 'Investigate and fix in the next development cycle.'),
    'LOW': ('P3', 'Review', 'Review impact and schedule after higher-priority issues.'),
}
BUG_COLORS = {'Wall Clip': '#fb7185', 'Infinite Fall': '#38bdf8', 'Softlock': '#fbbf24', 'Out of Bounds': '#c084fc'}


def read_telemetry(path: Path) -> pd.DataFrame:
    """Ignore a writer's unfinished last line; reject invalid complete records."""
    if not path.exists():
        return pd.DataFrame()
    raw = path.read_bytes()
    end = raw.rfind(b'\n')
    if end < 0:
        return pd.DataFrame()
    data = pd.read_csv(BytesIO(raw[:end + 1]))
    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError('Telemetry is missing: ' + ', '.join(sorted(missing)))
    if data.empty:
        return data
    numeric = sorted(REQUIRED_COLUMNS - {'active_input', 'collision_state', 'is_grounded'})
    if not np.isfinite(data[numeric].to_numpy(dtype=float)).all():
        raise ValueError('Telemetry contains incomplete or non-finite values; waiting for a complete write.')
    if not data.frame_id.is_monotonic_increasing or data.frame_id.duplicated().any():
        raise ValueError('Frame IDs must increase without duplicates.')
    return data


def fingerprint(row: pd.Series) -> tuple[str, ...]:
    return tuple(str(row[col]) for col in sorted(REQUIRED_COLUMNS))


@dataclass
class LiveRun:
    detector: BugDetector = field(default_factory=BugDetector)
    rows_seen: int = 0
    first: tuple[str, ...] | None = None
    last: tuple[str, ...] | None = None
    generation: int = 0

    def update(self, data: pd.DataFrame) -> list[dict[str, Any]]:
        """Rebuild on replacement, even when a new run is longer than the old one."""
        if data.empty:
            if self.rows_seen:
                self.reset()
            return []
        changed = self.first is not None and (
            len(data) < self.rows_seen or fingerprint(data.iloc[0]) != self.first or
            fingerprint(data.iloc[self.rows_seen - 1]) != self.last)
        if changed:
            self.reset()
        # Validate before changing counters. Detector owns incremental event state.
        if len(data) > self.rows_seen:
            self.detector.process_telemetry(data.iloc[self.rows_seen:])
        self.rows_seen = len(data)
        self.first, self.last = fingerprint(data.iloc[0]), fingerprint(data.iloc[-1])
        return self.detector.detected_bugs

    def reset(self) -> None:
        self.detector = BugDetector()
        self.rows_seen = 0
        self.first = self.last = None
        self.generation += 1


def prioritize(bugs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for bug in bugs:
        priority, action, reason = PRIORITIES.get(bug['severity'], ('P3', 'Review', 'Unclassified impact; review manually.'))
        result.append({**bug, 'priority': priority, 'recommended_action': action,
                       'priority_reason': reason, 'event_key': f"{bug['type']}:{bug['frame_id']}"})
    return sorted(result, key=lambda b: (b['priority'], b['frame_id'], b['type']))


def event_window(data: pd.DataFrame, frame_id: int, preceding: int = 120) -> pd.DataFrame:
    """Include pre-event context, stopping at a respawn or frame gap."""
    window = data[(data.frame_id <= frame_id) & (data.frame_id >= frame_id - preceding)].copy()
    if len(window) < 2:
        return window
    dx = window.pos_x.diff() - window.vel_x
    dy = window.pos_y.diff() - window.vel_y
    from analysis.bug_detector import as_bool
    collision = window.collision_state.map(as_bool)
    breaks = (window.frame_id.diff() != 1) | ((np.hypot(dx, dy) > 25) & ~collision)
    breaks.iloc[0] = False
    positions = np.flatnonzero(breaks.to_numpy())
    return window.iloc[positions[-1]:] if len(positions) else window
