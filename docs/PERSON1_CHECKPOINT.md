# CHECKPOINT — Person 1 (Module 1: Core Simulation Engine & Bot Agent)

> **Project:** IndieQA — Autonomous QA Bug & Collision Hunter
> **Event:** Neurobridge Game Summit 2026 Hackathon, Baku
> **Repo:** https://github.com/GasimovDev/indieQA_bot
> **Last updated:** 2026-10-09 — end of **Phase 1**
> **Status:** ✅ Phase 1 complete (local commit; push pending repo access for `Qaqu2`) · ⏭️ Phase 2 (`core/engine.py`) — level layout proposed, awaiting approval

---

## 0. TL;DR

| Phase | Deliverable | Status |
|---|---|---|
| 1 | Environment scaffolding (`requirements.txt`, `core/__init__.py`, `data/logs/`) | ✅ Done |
| 2 | Physics engine + 3 intentional glitches (`core/engine.py`) | ⏭️ Next |
| 3 | Telemetry recorder (`core/telemetry.py`) | ⏳ Pending |
| 4 | Autonomous agent (`core/agent.py`) | ⏳ Pending |
| 5 | CLI test runner (`main.py`) | ⏳ Pending |

Each phase is only started after the previous one is confirmed functional by Person 1.

---

## 1. Team Scope & Ownership

| Owner | Files | Notes |
|---|---|---|
| **Person 1** | `core/__init__.py`, `core/engine.py`, `core/agent.py`, `core/telemetry.py`, `main.py`, `requirements.txt` (shared) | This checkpoint |
| **Person 2** | `analysis/bug_detector.py`, `analysis/reporter.py`, `dashboard/app.py`, `data/reports/` | Consumes our telemetry CSV |
| **Person 3** | Pitch deck, quality metrics, benchmarks | PDF/PPT ≤ 30 MB, due before 20:00 |

**Rule:** Person 1 never writes or edits `analysis/`, `dashboard/`, or pitch material. The only interface between Module 1 and Module 2 is the **telemetry CSV contract** (§4).

---

## 2. Phase 1 — What We Did

### 2.1 Goal
Set up a working, reproducible Python environment and project skeleton so Phases 2–5 can be built without setup friction.

### 2.2 Actions
1. Read the system specification (`instructions.md`, kept outside the repo).
2. Collected all missing physics constants and data-contract details from Person 1 / Person 2 (see §3, §4).
3. Cloned `GasimovDev/indieQA_bot` (at clone time it contained only `README.md` and a standard Python `.gitignore`; see §2.3.1 for the upload that landed afterwards).
4. Created:
   - `requirements.txt` — **byte-identical** to the file Person 2 generated locally, so both commits merge cleanly with no conflict.
   - `core/__init__.py` — package docstring + `__version__`. No submodule imports yet (they don't exist until Phases 2–4).
   - `data/logs/.gitkeep` — keeps the telemetry output directory in git.
   - `docs/PERSON1_CHECKPOINT.md` — this file.
5. Created a local `venv/` (already git-ignored) and verified the install.

### 2.3 Verification Result
```
Python 3.11.9
pygame 2.6.1 (SDL 2.28.4) | numpy 2.4.6 | core 0.1.0
headless display OK (800, 600)   # via SDL_VIDEODRIVER=dummy
```
Headless Pygame works → `main.py` will be able to run without a window (fast batch testing) as well as at 60 FPS rendered.

### 2.3.1 ⚠️ Repo event during Phase 1 — teammate upload (commit `c349a0a`, author `LRigloo` = Person 2)
While Phase 1 was being pushed, commit `c349a0a "Add files via upload"` landed on `main` with **all three modules**, including Person 1's files: `core/engine.py`, `core/agent.py`, `core/telemetry.py`, `main.py` (plus `analysis/*`, `dashboard/*`, `requirements.txt`).

- Merge handling: the only conflict was `core/__init__.py` (Person 1 file) → kept the documented version. `requirements.txt` was identical (no conflict). **The uploaded `core/*.py` and `main.py` were left untouched** pending a team decision.
- Review of the uploaded `core/` vs. the approved spec (§3):

| # | Uploaded `core/` behaviour | Approved spec | Impact |
|---|---|---|---|
| 1 | Player 20×20, run speed 5, max fall 30 px/frame | 32×32, 6, 15 | Normal falls reach 30 px/frame > 25 threshold |
| 2 | `jump_impulse = -10.0` "reaches exactly 100px" | v0 = 10.25 | Real discrete apex is **95 px** (§6.2) |
| 3 | Wall_Clip = a **2 px-wide block** passed by a `dash` input at 26 px/frame | **2 px gap in corner geometry**, diagonal high-velocity input | `dash` is not in the spec; any dash anywhere moves > 25 px/frame |
| 4 | Infinite_Fall **teleports the player back at y > 4500**, fall speed capped at 30 | No kill-plane, uncapped acceleration | Contradicts spec; teleport frame is a huge Δp jump (false Wall_Clip / OOB) |
| 5 | Pit walls rise 150 px above the **same floor level as the approach** (y = 400) | Player must be able to fall **into** the pit | Pit is unreachable (100 px jump < 150 px wall) → agent gets stuck *outside* it |
| 6 | No outer boundary walls; right of x = 670 is open void | Bounded arena | Uncontrolled extra infinite falls |
| 7 | Telemetry written synchronously, no type hints, unseeded `random` | Background writer, explicit type hints, reproducible runs | Spec coding-standard violations |

**Empirical check** (uploaded engine run headless for 7,201 frames, `random.seed(0)`, CSV fed to the uploaded `BugDetector`):

```
frames 7201 | max vel_y 30.0 | max pos_y 4495.0
BugDetector(1920, 1080) -> {'Out of Bounds': 4932}
BugDetector(800, 600)   -> {'Out of Bounds': 4971}
```
→ **0 × Wall Clip, 0 × Infinite Fall, 0 × Softlock detected.** The current end-to-end pipeline does not demonstrate any of the 3 required glitches.

### 2.3.2 Findings in Person 2's `analysis/bug_detector.py` that affect Module 1 (for Person 2 — not edited by Person 1)
1. **World size:** `BugDetector` defaults to `1920 × 1080`; the engine is `800 × 600` → must be constructed as `BugDetector(800, 600)` or OOB never fires inside the visible arena.
2. **OOB masks Infinite Fall:** checks are chained with `or` (`_check_oob(...) or _check_infinite_fall(...)`). Once the player is out of bounds, OOB returns every frame (a new bug report **per frame**) and the infinite-fall counter never runs → with any realistic fall, **Infinite Fall is never reported**.
3. **Wall Clip requires `collision_state == True` on the clip frame** (`delta > 25 and collision_state`) → Module 1 must set `collision_state = True` on the ejection frame. (Will be honoured in Phase 2.)
4. **Softlock counter runs on any non-`"none"` input** → an agent that always presses something can false-trigger whenever it returns within 5 px of its position ≥ 300 frames earlier.

### 2.4 `requirements.txt` (shared, whole project)
```text
pygame>=2.5.0
streamlit>=1.30.0
pandas>=2.0.0
matplotlib>=3.8.0
seaborn>=0.13.0
numpy>=1.26.0
```
Decision: **one** requirements file for the whole project (agreed with Person 2) so that a single `pip install -r requirements.txt` runs engine + analysis + dashboard.

### 2.5 Setup for teammates
```bash
git clone https://github.com/GasimovDev/indieQA_bot.git
cd indieQA_bot
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

---

## 3. What We Needed → What We Got (Physics & Level Spec)

### 3.1 Approved engine constants
All units are **pixels** and **pixels/frame**. Fixed timestep **dt = 1/60 s** (60 FPS). Pygame coordinates: origin top-left, **+y points down**.

| Constant | Value | Source |
|---|---|---|
| World / window size `W × H` | **800 × 600** | Approved by Person 1 |
| Player hitbox | **32 × 32 px** | Approved by Person 1 |
| Gravity `g` | **0.5 px/frame²** (= 1800 px/s²) | Approved by Person 1 |
| Max jump height `j_max` | **100 px** (hard spec) | Spec |
| Jump impulse `v0` | **≈ 10 px/frame**, tuned so the *discrete* apex is exactly ≤ 100 px | Derived (§6.2) |
| Max run speed | **6 px/frame** | Approved |
| Run acceleration | **0.8 px/frame²** | Approved |
| Ground friction | velocity × **0.85** per frame when no input | Approved |
| Terminal fall speed (normal) | **15 px/frame** | Approved |
| Terminal fall speed (Infinite_Fall gap) | **none** (uncapped) | Spec: "infinite downward acceleration" |
| Wall-clip detector threshold (Person 2) | Δp **> 25 px/frame** through a solid | Spec |

**Safety margin check:** the fastest legitimate motion is diagonal at `√(6² + 15²) ≈ 16.2 px/frame` < 25 → normal gameplay can never false-trigger the Wall_Clip detector. Only the intentional glitches exceed it.

### 3.2 The 3 intentional glitches (approved approach)

| Glitch | Mechanism | What Person 2's detector sees |
|---|---|---|
| **Wall_Clip** | A corner is built from two collider segments with a **2 px seam**. Planted resolver bug: when the hitbox overlaps the seam with a high-speed diagonal velocity, the engine applies minimum-translation (shortest-exit) push-out — and inside the seam the shortest exit is the **far side** of the wall. | One-frame jump Δp ≥ wall thickness + player width (> 25 px) crossing a solid surface; player ends **outside** the arena (also OOB). |
| **Infinite_Fall** | One floor segment has **no collider and no kill-plane**; terminal velocity is disabled there. | `collision_state = False` for > 120 consecutive frames, `vel_y` monotonically increasing, `pos_y → +∞` (y-down coordinates, i.e. `y > H` OOB). |
| **Softlock_Pit** | Enclosed U-pit, wall height **h = 150 px** vs jump **j_max = 100 px** → 50 px unclimbable margin. No ledges, no wall-jump. Interior ≈ player width + small margin. | Continuous input > 300 frames, displacement (window start → current frame) < 5 px whenever the agent is back on the pit floor. |

---

## 4. Telemetry Contract with Person 2 (LOCKED)

File: **`data/logs/telemetry.csv`** — one row **every frame**.

| Column | Type | Meaning |
|---|---|---|
| `frame_id` | int | 0-based frame counter |
| `timestamp` | float | **Simulated** Unix time: `run_start_unix + frame_id / 60` |
| `pos_x` | float | Player x (px, top-left of hitbox) |
| `pos_y` | float | Player y (px, +y down) |
| `vel_x` | float | px/frame |
| `vel_y` | float | px/frame (+ = falling) |
| `is_grounded` | bool | Standing on a surface this frame |
| `active_input` | str | `"+"`-joined combo, e.g. `"right+jump"`, `"left"`, `"none"` |
| `collision_state` | bool | `True` if touching/colliding with **any** geometry this frame (floor included) |

Confirmed by Person 2:
- **Combo inputs** are welcome; `active_input` is treated as an opaque string → used for `reproduction_sequence`.
- **Simulated timestamps** (not wall clock), so headless runs don't look like thousands of FPS.
- **Softlock displacement** is measured from the first frame of continuous input to the *current* frame; jump-spamming in the pit is fine — detection fires when the agent lands back on the pit floor.

> Open item: confirm with Person 2 whether `pos_x/pos_y` should be hitbox **top-left** (Pygame `Rect` default) or **center**. Current plan: top-left.

---

## 5. Remaining Phases — Plan

### Phase 2 — `core/engine.py` (NEXT)
**Deliverables**
- `GameEngine` class with explicit type hints; works in **headless** (`SDL_VIDEODRIVER=dummy`, no clock throttle) and **rendered** (window, `clock.tick(60)`) modes.
- Physics step `step(inputs: InputState) -> FrameState` — deterministic, fixed dt.
- Kinematic player controller: run accel / friction / max speed, jump only when grounded, gravity, terminal velocity (disabled in the Infinite_Fall zone).
- Level geometry as a list of named `pygame.Rect` colliders: outer boundary walls, floor, platforms, plus the 3 glitch structures.
- Axis-separated AABB collision resolution (X then Y) for normal geometry; the deliberately flawed shortest-exit resolver only for the Wall_Clip seam colliders.
- `FrameState` dataclass exposing exactly what telemetry needs: `frame_id, pos_x, pos_y, vel_x, vel_y, is_grounded, collision_state, active_input`.
- Simple rendering (colored rects; glitch zones optionally highlighted for the demo/pitch).
- Self-test (`python -m core.engine`) that scripts inputs to prove: (a) jump apex ≤ 100 px, (b) each of the 3 glitches is reproducible.

**Design points to settle during Phase 2 (will be raised before coding)**
1. **Level layout on 800 × 600.** The Softlock pit must be 150 px deep *without* its floor leaving the world (else it reads as OOB). Plan: main floor surface raised (≈ y 420) so the pit (≈ 420 → 570) fits inside `H = 600`.
2. **Pit entrance width vs. agent speed.** A pit only 4 px wider than the player is a 4 px "drop-in window", but the agent moves up to 6 px/frame and could skip over it. Options: (a) ~40 px interior (8 px window ≥ max speed), (b) a narrow drop-in chute from a platform above. Must keep horizontal wiggle < 5 px for the detector.
3. **Infinite_Fall gap width** — must be > 32 px so the player actually falls through.
4. **Wall_Clip corner location** — which corner, wall thickness (sets the Δp jump size), and the velocity condition that arms the bug.

### Phase 3 — `core/telemetry.py`
- `TelemetryRecorder` with `record(state: FrameState) -> None`, `start()`, `close()`.
- Engine pushes rows to a `queue.Queue`; a **background writer thread** batches rows to CSV → no frame drops at 60 FPS.
- Exact header from §4; booleans written as `True`/`False`; simulated timestamps.
- Clean shutdown flush (context manager) so no rows are lost on exit/Ctrl+C.

### Phase 4 — `core/agent.py`
- `QAAgent` state machine: `decide(state: FrameState) -> InputState`.
- **Boundary_Seeker:** probes/raycasts against level colliders to find nearest walls, ledges and corners; moves to and hugs them.
- **Input_Spammer:** triggered on collision frames (wall/corner contact); rapid non-linear combos (diagonals + jump spam, direction toggles) to force clips. Returns to Boundary_Seeker after N frames or when contact ends.
- Seeded RNG → fully reproducible runs (helps Person 2's `reproduction_sequence`).
- Must keep spamming while trapped (so the Softlock detector fires).

### Phase 5 — `main.py`
- CLI flags (planned): `--headless`, `--frames N`, `--seed S`, `--fps 60`, `--out data/logs/telemetry.csv`.
- Loop: `agent.decide → engine.step → telemetry.record → (render)`.
- End-of-run summary printed to console (frames, time simulated, CSV path).
- Integration test: run headless, then hand the CSV to Person 2's `bug_detector.py` and confirm all 3 glitches are detected.

---

## 6. Technical Notes

### 6.1 Integration order (planned)
Semi-implicit Euler per frame: `vel += accel`, then `pos += vel`, then resolve collisions.

### 6.2 Jump impulse derivation (discrete, not continuous)
With semi-implicit Euler and jump set as `vel_y = -v0`, the rise over frames `k = 1..n` is
`Σ (v0 − k·g)` for all positive terms.
- `v0 = 10.0`, `g = 0.5` → apex **95 px** (continuous formula `v0²/2g` would wrongly predict 100).
- `v0 = 10.25`, `g = 0.5` → 20 rising frames, apex `20·10.25 − 0.5·(20·21/2) =` **100.0 px exactly**.

→ Planned `v0 = 10.25 px/frame`, to be verified by the Phase 2 self-test. Pit wall 150 px ⇒ 50 px unclimbable margin.

### 6.3 Coding standards (from spec)
- Python 3.11+, explicit type hints on all interfaces, **no `# TODO`/draft code**, fully local (no API keys).

---

## 7. Git Workflow

- **Branch:** working on `main` (small team, strictly disjoint file ownership → near-zero conflict risk; avoids PR overhead under hackathon time pressure).
- **Before every push:** `git pull --rebase origin main`.
- **Shared files** (`requirements.txt`, `.gitignore`, `README.md`): coordinate in chat before editing.
- **Suggested `.gitignore` addition** (for whoever owns it): `data/logs/*.csv` — telemetry is regenerated every run and can get large.

---

## 8. Open Questions / Risks

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | `pos_x/pos_y` = hitbox top-left or center? | Person 2 | Open |
| 2 | Pit entrance width vs. 6 px/frame agent speed (§5 Phase 2 point 2) | Person 1 | To decide in Phase 2 |
| 3 | Level layout coordinates (floor height, platforms, glitch locations) | Person 1 | To propose in Phase 2 |
| 4 | Person 2's local `requirements.txt` not yet pushed — identical content, should merge cleanly | Person 2 | Info |
| 5 | Add `data/logs/*.csv` to `.gitignore` | Team | Suggested |
| 6 | Who owns `core/`? `LRigloo` (= Person 2) uploaded `core/*.py` + `main.py` (§2.3.1) | Team | ✅ **Decided 2026-10-09: REPLACE** — Person 1 rebuilds `core/` + `main.py` to the approved spec, keeping the entry points (`python main.py [--headless]`, same CSV path/columns) |
| 10 | `Qaqu2` has no push access to `GasimovDev/indieQA_bot` (HTTP 403) | GasimovDev | Open — add as collaborator |
| 7 | `BugDetector` world size 1920×1080 vs engine 800×600 | Person 2 | Open |
| 8 | OOB check short-circuits Infinite Fall detection + per-frame OOB spam | Person 2 | Open |
| 9 | Softlock false positives from always-on agent input | Person 2 | Open |
