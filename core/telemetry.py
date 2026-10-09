"""IndieQA telemetry recorder (Module 1, Person 1).

Records one CSV row per simulated frame to `data/logs/telemetry.csv` using a
background writer thread, so disk I/O never stalls the 60 FPS engine loop.
The game loop only enqueues a small tuple per frame (O(1), no I/O).

CSV contract (agreed with Person 2, see docs/PERSON1_CHECKPOINT.md section 4):
    frame_id, timestamp, pos_x, pos_y, vel_x, vel_y, is_grounded, active_input, collision_state

`timestamp` is SIMULATED Unix time: run_start_unix + frame_id / 60, so a fast
headless run still reads as a 60 FPS game in the analysis.
"""

from __future__ import annotations

import csv
import os
import queue
import threading
import time
from types import TracebackType
from typing import Final

from core.engine import FPS, FrameState

CSV_COLUMNS: Final[tuple[str, ...]] = (
    "frame_id",
    "timestamp",
    "pos_x",
    "pos_y",
    "vel_x",
    "vel_y",
    "is_grounded",
    "active_input",
    "collision_state",
)
DEFAULT_LOG_PATH: Final[str] = os.path.join("data", "logs", "telemetry.csv")

_Row = tuple[int, float, float, float, float, bool, str, bool]
_STOP: Final[object] = object()


class TelemetryRecorder:
    """Thread-backed per-frame CSV logger.

    Usage:
        with TelemetryRecorder() as telemetry:
            telemetry.record(engine.step(inputs))
    """

    def __init__(
        self,
        path: str = DEFAULT_LOG_PATH,
        run_start_unix: float | None = None,
        batch_size: int = 512,
    ) -> None:
        self.path: str = path
        self.run_start_unix: float = time.time() if run_start_unix is None else run_start_unix
        self.batch_size: int = batch_size
        self.frames_written: int = 0

        self._queue: queue.SimpleQueue[_Row | object] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self._closed: bool = False

    # -------------------------------------------------------------- lifecycle
    def start(self) -> TelemetryRecorder:
        """Create the output file (overwriting), write the header and start the writer thread."""
        if self._thread is not None:
            raise RuntimeError("TelemetryRecorder already started")
        directory: str = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        # Open in the caller's thread so path/permission errors surface immediately.
        handle = open(self.path, "w", newline="", encoding="utf-8")
        csv.writer(handle).writerow(CSV_COLUMNS)
        self._thread = threading.Thread(target=self._writer_loop, args=(handle,), name="telemetry-writer", daemon=True)
        self._thread.start()
        return self

    def record(self, state: FrameState) -> None:
        """Enqueue one frame. Cheap and non-blocking; called from the game loop."""
        if self._thread is None or self._closed:
            raise RuntimeError("TelemetryRecorder is not running (call start() first)")
        if self._error is not None:
            raise RuntimeError("telemetry writer thread failed") from self._error
        self._queue.put(
            (
                state.frame_id,
                state.pos_x,
                state.pos_y,
                state.vel_x,
                state.vel_y,
                state.is_grounded,
                state.active_input,
                state.collision_state,
            )
        )

    def close(self) -> None:
        """Flush every queued row, stop the writer thread and close the file. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self._thread is not None:
            self._queue.put(_STOP)
            self._thread.join()
        if self._error is not None:
            raise RuntimeError("telemetry writer thread failed") from self._error

    def __enter__(self) -> TelemetryRecorder:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ---------------------------------------------------------- writer thread
    def _format(self, row: _Row) -> list[str]:
        frame_id, pos_x, pos_y, vel_x, vel_y, grounded, active_input, collision = row
        return [
            str(frame_id),
            f"{self.run_start_unix + frame_id / FPS:.6f}",
            f"{pos_x:.4f}",
            f"{pos_y:.4f}",
            f"{vel_x:.4f}",
            f"{vel_y:.4f}",
            "True" if grounded else "False",
            active_input or "none",
            "True" if collision else "False",
        ]

    def _writer_loop(self, handle: object) -> None:
        import io

        assert isinstance(handle, io.TextIOBase)
        writer = csv.writer(handle)
        batch: list[list[str]] = []
        try:
            while True:
                item = self._queue.get()  # blocks until a row (or stop) arrives
                stop: bool = item is _STOP
                if not stop:
                    batch.append(self._format(item))  # type: ignore[arg-type]
                # Drain whatever else is already queued without blocking.
                while not stop and len(batch) < self.batch_size:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if item is _STOP:
                        stop = True
                    else:
                        batch.append(self._format(item))  # type: ignore[arg-type]
                if batch:
                    writer.writerows(batch)
                    handle.flush()  # whole rows on disk now -> the dashboard can read the CSV live
                    self.frames_written += len(batch)
                    batch.clear()
                if stop:
                    break
            handle.flush()
        except BaseException as exc:  # surfaced to the game loop via record()/close()
            self._error = exc
        finally:
            handle.close()


# --------------------------------------------------------------------------
# Self-test:  python -m core.telemetry
# --------------------------------------------------------------------------
def _self_test() -> None:
    import tempfile

    from core.engine import NO_INPUT, GameEngine, InputState, Zone

    # Scripted tour: S1 -> Infinite_Fall, S2 -> Softlock_Pit, S3 -> Wall_Clip.
    engine = GameEngine(headless=True, spawn_index=0)
    script: list[tuple[int, InputState, int]] = [
        (0, InputState(right=True), 400),
        (1, InputState(right=True), 120),
        (1, InputState(left=True, jump=True), 400),
        (2, InputState(right=True, jump=True), 400),
    ]
    out_path: str = os.path.join(tempfile.mkdtemp(prefix="indieqa_"), "telemetry.csv")
    start_unix: float = 1_760_000_000.0

    record_times: list[float] = []
    with TelemetryRecorder(out_path, run_start_unix=start_unix) as telemetry:
        for spawn, inp, frames in script:
            engine.reset(spawn)
            for _ in range(frames):
                state = engine.step(inp)
                t0 = time.perf_counter()
                telemetry.record(state)
                record_times.append(time.perf_counter() - t0)
                if state.zone is Zone.OUT_OF_WORLD and state.pos_y > 5000:
                    break
        engine.step(NO_INPUT)  # not recorded; recorder must be unaffected
    total: int = len(record_times)

    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    assert tuple(header) == CSV_COLUMNS, header
    assert len(body) == total == telemetry.frames_written, (len(body), total, telemetry.frames_written)
    ids = [int(r[0]) for r in body]
    assert ids == list(range(ids[0], ids[0] + len(ids))), "frame_id not contiguous"
    for r in body:
        assert abs(float(r[1]) - (start_unix + int(r[0]) / FPS)) < 1e-5, "timestamp != start + frame/60"
        assert r[6] in ("True", "False") and r[8] in ("True", "False")
    inputs_seen = {r[7] for r in body}
    clip_rows = [
        (body[i - 1], body[i])
        for i in range(1, len(body))
        if ((float(body[i][2]) - float(body[i - 1][2])) ** 2 + (float(body[i][3]) - float(body[i - 1][3])) ** 2) ** 0.5
        > 25.0
        and body[i][8] == "True"
    ]
    worst_ms: float = max(record_times) * 1000
    mean_us: float = sum(record_times) / total * 1e6

    print(f"[PASS] header matches contract  : {','.join(header)}")
    print(f"[PASS] rows written             : {len(body)} (frame_id {ids[0]}..{ids[-1]}, contiguous)")
    print(f"[PASS] simulated timestamps     : start + frame_id/{FPS}")
    print(f"[PASS] combo inputs recorded    : {sorted(inputs_seen)}")
    print(f"[PASS] >25px + collision frames : {len(clip_rows)} (expected 1 = Wall_Clip)")
    assert len(clip_rows) == 1
    print(f"[PASS] record() cost            : mean {mean_us:.1f} us, worst {worst_ms:.3f} ms (frame budget 16.7 ms)")
    assert worst_ms < 16.7
    print(f"       sample CSV               : {out_path}")


if __name__ == "__main__":
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    _self_test()
