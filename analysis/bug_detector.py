"""Telemetry-only anomaly detection; coordinates use +y down, pixels/frame."""
from __future__ import annotations
from collections import deque
from math import hypot
from typing import Any
from uuid import uuid4
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"frame_id", "timestamp", "pos_x", "pos_y", "vel_x", "vel_y",
                    "is_grounded", "active_input", "collision_state"}


def as_bool(value: Any) -> bool:
    """Handle CSV strings as well as pandas booleans."""
    if isinstance(value, str):
        if value.lower() in {"true", "1"}:
            return True
        if value.lower() in {"false", "0"}:
            return False
        raise ValueError(f"Invalid telemetry boolean: {value!r}")
    if value in (True, False):
        return bool(value)
    raise ValueError(f"Invalid telemetry boolean: {value!r}")


class BugDetector:
    def __init__(self, world_width: float = 800.0, world_height: float = 600.0,
                 softlock_zone: tuple[float, float, float, float] = (440., 440., 480., 590.),
                 player_size: tuple[float, float] = (32., 32.)) -> None:
        self.world_width = world_width
        self.world_height = world_height
        # Static arena geometry from the agreed map contract, not engine truth.
        self.softlock_zone = softlock_zone
        self.player_size = player_size
        self.detected_bugs: list[dict[str, Any]] = []
        self.frame_history: deque[dict[str, Any]] = deque(maxlen=301)
        self.fall_frames = 0
        self.softlock_frames = 0
        self._oob = False
        self._softlock = False
        self._clip_frame = -60

    def process_telemetry(self, telemetry_data: pd.DataFrame) -> list[dict[str, Any]]:
        """Append consecutive batches and return all accumulated reports."""
        missing = REQUIRED_COLUMNS - set(telemetry_data.columns)
        if missing:
            raise ValueError(f"Missing telemetry columns: {', '.join(sorted(missing))}")
        numeric = list(REQUIRED_COLUMNS - {"is_grounded", "active_input", "collision_state"})
        if not np.isfinite(telemetry_data[numeric].to_numpy(dtype=float)).all():
            raise ValueError("Telemetry contains missing or non-finite numeric values")
        for frame in telemetry_data.to_dict("records"):
            frame["is_grounded"] = as_bool(frame["is_grounded"])
            frame["collision_state"] = as_bool(frame["collision_state"])
            self._analyze_frame(frame)
        return self.detected_bugs

    def _analyze_frame(self, frame: dict[str, Any]) -> None:
        prev = self.frame_history[-1] if self.frame_history else None
        # A respawn is a discontinuity inconsistent with post-step velocity.
        discontinuity = prev is not None and (
            frame["frame_id"] != prev["frame_id"] + 1 or
            (not frame["collision_state"] and hypot(
                frame["pos_x"] - prev["pos_x"] - frame["vel_x"],
                frame["pos_y"] - prev["pos_y"] - frame["vel_y"]) > 25)
        )
        if discontinuity:
            self.frame_history.clear()
            self.fall_frames = self.softlock_frames = 0
            self._oob = self._softlock = False
            self._clip_frame = -60
            prev = None
        self.frame_history.append(frame)
        x, y = frame["pos_x"], frame["pos_y"]
        oob = x < 0 or x > self.world_width or y < 0 or y > self.world_height
        if oob and not self._oob:
            self._report("Out of Bounds", "CRITICAL", frame)
        self._oob = oob
        falling = (frame["vel_y"] > 0 and not frame["is_grounded"]
                   and not frame["collision_state"])
        self.fall_frames = self.fall_frames + 1 if falling else 0
        if self.fall_frames == 121:
            self._report("Infinite Fall", "HIGH", frame)
        if (prev is not None and frame["collision_state"]
                and frame["frame_id"] - self._clip_frame >= 60
                and hypot(x - prev["pos_x"], y - prev["pos_y"]) > 25):
            self._report("Wall Clip", "CRITICAL", frame)
            self._clip_frame = frame["frame_id"]
        active = bool(set(str(frame["active_input"]).lower().split("+")) & {"left", "right", "jump"})
        left, top, right, bottom = self.softlock_zone
        cx, cy = x + self.player_size[0] / 2, y + self.player_size[1] / 2
        trapped = left <= cx < right and top <= cy < bottom
        self.softlock_frames = self.softlock_frames + 1 if active and trapped else 0
        if not active or not trapped:
            self._softlock = False
        if self.softlock_frames > 300 and len(self.frame_history) == 301:
            # Compare landing positions: jump spam changes y by 100px even in
            # an inescapable pit. A periodic patrol outside the zone is not stuck.
            landings = [f for f in list(self.frame_history)[:-30] if f["is_grounded"]]
            stuck = frame["is_grounded"] and any(
                hypot(x - f["pos_x"], y - f["pos_y"]) < 5 for f in landings)
            if stuck and not self._softlock:
                self._report("Softlock", "HIGH", frame)
                self._softlock = True

    def _report(self, bug_type: str, severity: str, frame: dict[str, Any]) -> None:
        self.detected_bugs.append({
            "bug_id": str(uuid4()), "type": bug_type, "severity": severity,
            "coordinates_xyz": [frame["pos_x"], frame["pos_y"], 0.0],
            "frame_id": frame["frame_id"], "timestamp": frame["timestamp"],
            "reproduction_sequence": [f["active_input"] for f in list(self.frame_history)[-31:-1]],
        })
