"""IndieQA system CLI test runner (Module 1, Person 1).

Wires the autonomous agent, the physics engine and the telemetry recorder:

    agent.decide(state) -> engine.step(inputs) -> telemetry.record(state) -> engine.render(...)

Usage:
    python main.py                      # rendered at 60 FPS (close window / Esc to stop)
    python main.py --headless           # as fast as possible, no window
    python main.py --headless --frames 36000 --seed 7
    python main.py --headless --analyze # also run Person 2's bug detector on the CSV

Episode policy (the engine itself never resets the player):
    * no collision for > 300 consecutive frames (Infinite_Fall / Wall_Clip aftermath) -> respawn
    * trapped in the Softlock_Pit for > 600 consecutive frames                        -> respawn
    * episode longer than --episode-max frames                                        -> respawn
Both trigger windows exceed the detector windows (120 / 300 frames), so every
glitch is fully recorded before the respawn. Spawn points rotate in a seeded order.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

from core.agent import QAAgent
from core.engine import FPS, NO_INPUT, WORLD_HEIGHT, WORLD_WIDTH, FrameState, GameEngine, Zone
from core.telemetry import DEFAULT_LOG_PATH, TelemetryRecorder

FALL_RESET_FRAMES: int = 300
SOFTLOCK_RESET_FRAMES: int = 600


@dataclass
class RunSummary:
    frames: int = 0
    episodes: int = 1
    reset_reasons: Counter[str] = field(default_factory=Counter)
    glitch_events: Counter[str] = field(default_factory=Counter)
    wall_seconds: float = 0.0


class SpawnRotation:
    """Seeded order over all spawn points; reshuffled after every full cycle."""

    def __init__(self, count: int, seed: int) -> None:
        self._count: int = count
        self._rng: random.Random = random.Random(seed)
        self._queue: list[int] = []

    def next(self) -> int:
        if not self._queue:
            self._queue = list(range(self._count))
            self._rng.shuffle(self._queue)
        return self._queue.pop()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IndieQA autonomous QA simulation runner")
    parser.add_argument("--headless", action="store_true", help="run without a window, as fast as possible")
    parser.add_argument("--frames", type=int, default=7200, help="frames to simulate (default 7200 = 2 min at 60 FPS)")
    parser.add_argument("--seed", type=int, default=42, help="seed for the agent and spawn rotation (default 42)")
    parser.add_argument("--out", default=DEFAULT_LOG_PATH, help=f"telemetry CSV path (default {DEFAULT_LOG_PATH})")
    parser.add_argument("--episode-max", type=int, default=3600, help="max frames per episode (default 3600)")
    parser.add_argument("--analyze", action="store_true", help="run analysis.bug_detector on the CSV afterwards")
    args = parser.parse_args(argv)
    if args.frames <= 0 or args.episode_max <= 0:
        parser.error("--frames and --episode-max must be positive")
    return args


def run(args: argparse.Namespace) -> RunSummary:
    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    spawns = SpawnRotation(3, args.seed)
    engine = GameEngine(headless=args.headless, spawn_index=spawns.next())
    agent = QAAgent(engine.level, seed=args.seed)
    summary = RunSummary()

    airborne_frames: int = 0
    pit_frames: int = 0
    episode_frames: int = 0
    started: float = time.perf_counter()

    try:
        with TelemetryRecorder(args.out) as telemetry:
            state: FrameState = engine.step(NO_INPUT)
            telemetry.record(state)
            while state.frame_id + 1 < args.frames:
                inputs = agent.decide(state)
                state = engine.step(inputs)
                telemetry.record(state)
                episode_frames += 1

                if state.glitch_event is not None:
                    summary.glitch_events[state.glitch_event.value] += 1
                    print(f"  frame {state.frame_id:>6}  episode {state.episode:>3}  {state.glitch_event.value}")

                airborne_frames = 0 if state.collision_state else airborne_frames + 1
                pit_frames = pit_frames + 1 if state.zone is Zone.SOFTLOCK_PIT else 0

                reason: str | None = None
                if airborne_frames > FALL_RESET_FRAMES:
                    reason = "fell (no collision > 300 frames)"
                elif pit_frames > SOFTLOCK_RESET_FRAMES:
                    reason = "trapped in pit > 600 frames"
                elif episode_frames > args.episode_max:
                    reason = "episode length limit"

                if not engine.render(
                    state,
                    (
                        f"agent: {agent.mode.value}  heading {'right' if agent.heading > 0 else 'left'}  seed {args.seed}",
                        f"glitch events so far: {dict(summary.glitch_events) or '-'}",
                    ),
                ):
                    break

                if reason is not None:
                    summary.reset_reasons[reason] += 1
                    summary.episodes += 1
                    engine.reset(spawns.next())
                    airborne_frames = pit_frames = episode_frames = 0
    except KeyboardInterrupt:
        print("\nInterrupted - telemetry flushed.")
    finally:
        engine.close()

    summary.frames = state.frame_id + 1
    summary.wall_seconds = time.perf_counter() - started
    return summary


def analyze(csv_path: str) -> None:
    """Hand the CSV to Person 2's detector (read-only use of analysis/)."""
    try:
        import pandas as pd

        from analysis.bug_detector import BugDetector
    except ImportError as exc:
        print(f"[analyze] skipped: {exc}")
        return
    bugs = BugDetector(WORLD_WIDTH, WORLD_HEIGHT).process_telemetry(pd.read_csv(csv_path))
    counts = Counter(str(b.get("type")) for b in bugs)
    print(f"[analyze] bug_detector reported {len(bugs)} bug(s): {dict(counts) or '-'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "headless" if args.headless else f"rendered @ {FPS} FPS"
    print(f"IndieQA simulation: {mode}, {args.frames} frames, seed {args.seed}")
    summary = run(args)
    sim_seconds = summary.frames / FPS
    print("-" * 64)
    print(f"frames simulated : {summary.frames} ({sim_seconds:.1f} s game time in {summary.wall_seconds:.1f} s)")
    print(f"episodes         : {summary.episodes}  resets: {dict(summary.reset_reasons) or '-'}")
    print(f"glitch events    : {dict(summary.glitch_events) or '-'} (engine ground truth: Wall_Clip frames)")
    print(f"telemetry        : {os.path.abspath(args.out)}")
    if args.analyze:
        analyze(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
