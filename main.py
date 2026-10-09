"""IndieQA system CLI test runner (Module 1, Person 1).

Wires the autonomous agent, the physics engine and the telemetry recorder:

    agent.decide(state) -> engine.step(inputs) -> telemetry.record(state) -> engine.render(...)

Usage:
    python main.py                      # rendered at 60 FPS (close window / Esc to stop)
    python main.py --headless           # as fast as possible, no window
    python main.py --headless --frames 36000 --seed 7
    python main.py --headless --analyze # then detect bugs + write reports for the dashboard
    python main.py --headless --verify  # --analyze + check detector results against engine ground truth
    python main.py --scan-seeds 50      # find the seed that shows all 3 glitches fastest (demo prep)

Episode policy (the engine itself never resets the player):
    * no collision for > 300 consecutive frames (Infinite_Fall / Wall_Clip aftermath) -> respawn
    * trapped in the Softlock_Pit for > 600 consecutive frames                        -> respawn
    * episode longer than --episode-max frames                                        -> respawn
Both trigger windows exceed the detector windows (120 / 300 frames), so every
glitch is fully recorded before the respawn. Spawn points rotate in a seeded order.

Ground truth (what the engine knows really happened, per episode):
    * Wall Clip     -- the engine's seam-ejection fired (FrameState.glitch_event)
    * Infinite Fall -- more than 120 consecutive frames without any collision
    * Softlock      -- more than 300 consecutive frames inside the Softlock_Pit
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Final

from core.agent import QAAgent
from core.engine import FPS, NO_INPUT, WORLD_HEIGHT, WORLD_WIDTH, FrameState, GameEngine, Glitch, Zone
from core.telemetry import DEFAULT_LOG_PATH, TelemetryRecorder

DEFAULT_REPORT_DIR: Final[str] = os.path.join("data", "reports")
FALL_RESET_FRAMES: Final[int] = 300
SOFTLOCK_RESET_FRAMES: Final[int] = 600
FALL_TRUTH_FRAMES: Final[int] = 120      # spec: Infinite Fall after > 120 frames without collision
SOFTLOCK_TRUTH_FRAMES: Final[int] = 300  # spec: Softlock after > 300 frames of input without progress

# Engine glitch -> bug type name used by analysis/bug_detector.py
DETECTOR_LABEL: Final[dict[Glitch, str]] = {
    Glitch.WALL_CLIP: "Wall Clip",
    Glitch.INFINITE_FALL: "Infinite Fall",
    Glitch.SOFTLOCK_PIT: "Softlock",
}


@dataclass
class EpisodeRecord:
    episode: int
    start_frame: int
    end_frame: int = -1
    truth: set[Glitch] = field(default_factory=set)


@dataclass
class RunSummary:
    frames: int = 0
    episodes: list[EpisodeRecord] = field(default_factory=list)
    reset_reasons: Counter[str] = field(default_factory=Counter)
    truth_events: Counter[Glitch] = field(default_factory=Counter)
    first_seen: dict[Glitch, int] = field(default_factory=dict)
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
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="afterwards run analysis.bug_detector on the CSV and write reports with analysis.reporter",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="--analyze, then compare the detector's bugs with the engine's ground truth (exit code 1 on mismatch)",
    )
    parser.add_argument(
        "--reports-dir",
        default=DEFAULT_REPORT_DIR,
        help=f"where --analyze writes bug reports (default {DEFAULT_REPORT_DIR}); old bug_* reports there are replaced",
    )
    parser.add_argument(
        "--scan-seeds",
        type=int,
        metavar="N",
        help="demo prep: headless-test seeds 0..N-1 (no CSV) and rank them by how fast all 3 glitches appear",
    )
    args = parser.parse_args(argv)
    if args.frames <= 0 or args.episode_max <= 0:
        parser.error("--frames and --episode-max must be positive")
    if args.scan_seeds is not None and args.scan_seeds <= 0:
        parser.error("--scan-seeds must be positive")
    return args


def run(
    args: argparse.Namespace,
    seed: int | None = None,
    record_telemetry: bool = True,
    verbose: bool = True,
) -> RunSummary:
    """Run one simulation. Headless runs need no display; rendered runs open a 60 FPS window."""
    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    run_seed: int = args.seed if seed is None else seed

    spawns = SpawnRotation(3, run_seed)
    engine = GameEngine(headless=args.headless, spawn_index=spawns.next())
    agent = QAAgent(engine.level, seed=run_seed)
    summary = RunSummary()
    telemetry: TelemetryRecorder | None = TelemetryRecorder(args.out) if record_telemetry else None

    airborne_frames: int = 0
    pit_frames: int = 0
    episode_frames: int = 0
    started: float = time.perf_counter()

    def mark(glitch: Glitch, frame_id: int) -> None:
        current.truth.add(glitch)
        summary.truth_events[glitch] += 1
        summary.first_seen.setdefault(glitch, frame_id)
        if verbose:
            print(f"  frame {frame_id:>6}  episode {current.episode:>3}  {glitch.value}")

    state: FrameState = engine.step(NO_INPUT)
    current = EpisodeRecord(episode=state.episode, start_frame=state.frame_id)
    try:
        if telemetry is not None:
            telemetry.start()
            telemetry.record(state)
        while state.frame_id + 1 < args.frames:
            inputs = agent.decide(state)
            state = engine.step(inputs)
            if telemetry is not None:
                telemetry.record(state)
            episode_frames += 1

            airborne_frames = 0 if state.collision_state else airborne_frames + 1
            pit_frames = pit_frames + 1 if state.zone is Zone.SOFTLOCK_PIT else 0
            if state.glitch_event is Glitch.WALL_CLIP:
                mark(Glitch.WALL_CLIP, state.frame_id)
            if airborne_frames == FALL_TRUTH_FRAMES + 1:
                mark(Glitch.INFINITE_FALL, state.frame_id)
            if pit_frames == SOFTLOCK_TRUTH_FRAMES + 1:
                mark(Glitch.SOFTLOCK_PIT, state.frame_id)

            reason: str | None = None
            if airborne_frames > FALL_RESET_FRAMES:
                reason = "fell (no collision > 300 frames)"
            elif pit_frames > SOFTLOCK_RESET_FRAMES:
                reason = "trapped in pit > 600 frames"
            elif episode_frames > args.episode_max:
                reason = "episode length limit"

            found: str = ", ".join(f"{g.value} {n}" for g, n in summary.truth_events.items()) or "-"
            if not engine.render(
                state,
                (
                    f"agent: {agent.mode.value}  heading {'right' if agent.heading > 0 else 'left'}  seed {run_seed}",
                    f"glitches so far: {found}",
                ),
            ):
                break

            if reason is not None:
                summary.reset_reasons[reason] += 1
                current.end_frame = state.frame_id
                summary.episodes.append(current)
                engine.reset(spawns.next())
                current = EpisodeRecord(episode=engine.episode, start_frame=state.frame_id + 1)
                airborne_frames = pit_frames = episode_frames = 0
    except KeyboardInterrupt:
        print("\nInterrupted - telemetry flushed.")
    finally:
        if telemetry is not None:
            telemetry.close()
        engine.close()

    current.end_frame = state.frame_id
    summary.episodes.append(current)
    summary.frames = state.frame_id + 1
    summary.wall_seconds = time.perf_counter() - started
    return summary


def analyze(csv_path: str, report_dir: str) -> list[dict[str, Any]] | None:
    """Hand the CSV to Person 2's detector and reporter (their APIs are used as-is, read-only).

    Reports from earlier runs (bug_*.json / bug_*.md) are removed first so the
    dashboard always shows exactly the bugs of the latest run.
    """
    try:
        import pandas as pd

        from analysis.bug_detector import BugDetector
        from analysis.reporter import BugReporter
    except ImportError as exc:
        print(f"[analyze] skipped: {exc}")
        return None
    bugs: list[dict[str, Any]] = BugDetector(WORLD_WIDTH, WORLD_HEIGHT).process_telemetry(pd.read_csv(csv_path))
    counts = Counter(str(b.get("type")) for b in bugs)
    print(f"[analyze] bug_detector reported {len(bugs)} bug(s): {dict(counts) or '-'}")

    stale: list[str] = [
        path
        for pattern in ("bug_*.json", "bug_*.md")
        for path in glob.glob(os.path.join(report_dir, pattern))
    ]
    for path in stale:
        os.remove(path)
    BugReporter(report_dir).generate_all_reports(bugs)
    print(f"[analyze] reports         : {len(bugs)} written to {os.path.abspath(report_dir)} ({len(stale)} old files replaced)")
    print("[analyze] dashboard       : streamlit run dashboard/app.py")
    return bugs


def verify(summary: RunSummary, bugs: list[dict[str, Any]]) -> bool:
    """Episode-level comparison of detector output against engine ground truth.

    For each glitch type: an episode where it really happened must contain at least one
    detector report of that type (else MISSED); a report in an episode where it did not
    happen is a FALSE ALARM.
    """
    detected: dict[int, set[str]] = {}
    for bug in bugs:
        frame = int(bug.get("frame_id", -1))
        for ep in summary.episodes:
            if ep.start_frame <= frame <= ep.end_frame:
                detected.setdefault(ep.episode, set()).add(str(bug.get("type")))
                break

    print("-" * 64)
    print(f"[verify] {len(summary.episodes)} episodes, ground truth vs analysis/bug_detector.py")
    print(f"  {'bug type':<14}{'real':>6}{'found':>7}{'missed':>8}{'false alarms':>14}   result")
    all_ok: bool = True
    for glitch, label in DETECTOR_LABEL.items():
        real = [ep for ep in summary.episodes if glitch in ep.truth]
        found = [ep for ep in real if label in detected.get(ep.episode, set())]
        false_alarms = [
            ep for ep in summary.episodes if glitch not in ep.truth and label in detected.get(ep.episode, set())
        ]
        ok: bool = len(real) > 0 and len(found) == len(real) and not false_alarms
        all_ok &= ok
        missed_eps = [ep.episode for ep in real if ep not in found][:5]
        false_eps = [ep.episode for ep in false_alarms][:5]
        detail = (f"  missed eps {missed_eps}" if missed_eps else "") + (f"  false eps {false_eps}" if false_eps else "")
        verdict = "PASS" if ok else ("NO DATA" if not real else "FAIL")
        print(f"  {label:<14}{len(real):>6}{len(found):>7}{len(real) - len(found):>8}{len(false_alarms):>14}   {verdict}{detail}")
    oob = sum(1 for b in bugs if b.get("type") == "Out of Bounds")
    print(f"  {'Out of Bounds':<14} {oob} report(s) (info only: depends on the detector's own OOB margins)")
    print(f"[verify] {'PASS - detector matches engine ground truth' if all_ok else 'FAIL - see rows above'}")
    return all_ok


def scan_seeds(args: argparse.Namespace) -> None:
    """Demo prep: rank seeds by the game time at which all 3 glitches have appeared."""
    args.headless = True
    results: list[tuple[float, int, dict[Glitch, int]]] = []
    for seed in range(args.scan_seeds):
        s = run(args, seed=seed, record_telemetry=False, verbose=False)
        all_found: bool = all(g in s.first_seen for g in Glitch)
        score: float = max(s.first_seen.values()) / FPS if all_found else float("inf")
        results.append((score, seed, s.first_seen))
    results.sort(key=lambda r: (r[0], r[1]))

    def fmt(first: dict[Glitch, int], g: Glitch) -> str:
        return f"{first[g] / FPS:6.1f}s" if g in first else "     - "

    print(f"Seeds 0..{args.scan_seeds - 1}, {args.frames} frames each - game time when each glitch FIRST appears:")
    print(f"  {'seed':>5}  {'Wall_Clip':>9}  {'Inf_Fall':>9}  {'Softlock':>9}   all three by")
    for score, seed, first in results[:10]:
        all_by = f"{score:6.1f}s" if score != float("inf") else "  never"
        print(
            f"  {seed:>5}  {fmt(first, Glitch.WALL_CLIP):>9}  {fmt(first, Glitch.INFINITE_FALL):>9}"
            f"  {fmt(first, Glitch.SOFTLOCK_PIT):>9}   {all_by}"
        )
    best = results[0]
    if best[0] != float("inf"):
        print(f"\nBest demo seed: {best[1]}  ->  python main.py --seed {best[1]}")
    else:
        print("\nNo seed showed all 3 glitches; try more seeds or a larger --frames.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.scan_seeds is not None:
        scan_seeds(args)
        return 0

    mode = "headless" if args.headless else f"rendered @ {FPS} FPS"
    print(f"IndieQA simulation: {mode}, {args.frames} frames, seed {args.seed}")
    summary = run(args)
    sim_seconds = summary.frames / FPS
    truth = {g.value: n for g, n in summary.truth_events.items()}
    print("-" * 64)
    print(f"frames simulated : {summary.frames} ({sim_seconds:.1f} s game time in {summary.wall_seconds:.1f} s)")
    print(f"episodes         : {len(summary.episodes)}  resets: {dict(summary.reset_reasons) or '-'}")
    print(f"glitches (truth) : {truth or '-'}")
    print(f"telemetry        : {os.path.abspath(args.out)}")
    if args.analyze or args.verify:
        bugs = analyze(args.out, args.reports_dir)
        if args.verify:
            if bugs is None:
                return 1
            return 0 if verify(summary, bugs) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
