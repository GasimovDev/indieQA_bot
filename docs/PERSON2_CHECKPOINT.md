# CHECKPOINT — Person 2 (Module 2: Detection Engine, Reporter & Dashboard)

> **Project:** IndieQA — Autonomous QA Bug & Collision Hunter
> **Event:** Neurobridge Game Summit 2026 Hackathon, Baku
> **Repo:** https://github.com/GasimovDev/indieQA_bot
> **Last updated:** 2026-10-09 ~14:30 (Baku)
> **Status:** ✅ All blockers resolved — ready for end-to-end pipeline test

---

## 0. TL;DR

| Task | Deliverable | Status |
|---|---|---|
| Bug Detector (`analysis/bug_detector.py`) | Threshold classifier for 4 anomaly types | ✅ Done — v3 (all blockers fixed) |
| Reporter (`analysis/reporter.py`) | Markdown & JSON diagnostic report builder | ✅ Done |
| Dashboard (`dashboard/app.py`) | Streamlit Web UI (Heatmap, Bug Log, Export) | ✅ Done — all blockers fixed |
| Requirements (`requirements.txt`) | Added `tabulate>=0.9` | ✅ Done |

---

## 1. Team Scope & Ownership

| Owner | Files | Notes |
|---|---|---|
| **Person 1** | `core/__init__.py`, `core/engine.py`, `core/agent.py`, `core/telemetry.py`, `main.py` | Produces `data/logs/telemetry.csv` |
| **Person 2** | `analysis/bug_detector.py`, `analysis/reporter.py`, `dashboard/app.py`, `analysis/run_analysis.py` | **This checkpoint** |
| **Person 3** | Pitch deck, quality metrics, benchmarks | PDF/PPT ≤ 30 MB, due before 20:00 |

**Rule:** Person 2 never writes or edits `core/` or `main.py`. The only interface is the **telemetry CSV contract** (§2).

---

## 2. Telemetry CSV Contract (consumed by Person 2)

File: **`data/logs/telemetry.csv`** — one row per frame, written by Person 1's `core/telemetry.py`.

| Column | Type | Meaning |
|---|---|---|
| `frame_id` | int | 0-based frame counter |
| `timestamp` | float | Simulated Unix time: `run_start_unix + frame_id / 60` |
| `pos_x` | float | Player x (px, top-left of hitbox) |
| `pos_y` | float | Player y (px, +y down) |
| `vel_x` | float | px/frame |
| `vel_y` | float | px/frame (+ = falling) |
| `is_grounded` | bool | Standing on a surface this frame |
| `active_input` | str | `"+"`-joined combo, e.g. `"right+jump"`, `"left"`, `"none"` |
| `collision_state` | bool | `True` if touching any geometry this frame |

---

## 3. What Was Done — Full History

### 3.1 Phase 1 — Initial Implementation (v1)

Created the first versions of all three Person 2 files:

- **`bug_detector.py` v1**: Basic threshold classifier with 4 checks (OOB, Infinite Fall, Wall Clip, Softlock).
- **`reporter.py` v1**: Dual-format output (JSON + Markdown) per bug, with reproduction sequence.
- **`dashboard/app.py` v1**: Streamlit UI with metrics header, economics banner, heatmap, and bug log table.
- **`analysis/__init__.py`** and **`dashboard/__init__.py`**: Package init files.

**Known issues at v1 (later identified by Person 1's testing):**
1. World size defaulted to 1920×1080, but engine is 800×600.
2. Bug checks used short-circuit `or` — OOB masked all other detectors.
3. No debouncing — OOB generated ~4,900+ duplicate bug reports.
4. Softlock measured displacement from first-input-frame, not sliding window.
5. Dashboard "Running Time" was hardcoded.
6. `to_markdown()` requires `tabulate` which was missing from requirements.
7. Streamlit `use_container_width` deprecated warning.

### 3.2 Phase 2 — First Fix Attempt (v2)

After Person 1 reported only OOB detections (4,900+), identified and partially fixed:

- ✅ Changed all 4 checks to run independently every frame (no short-circuit).
- ✅ Added debounce to OOB (log once per event).
- ✅ Added debounce/cooldown to Wall Clip (60-frame cooldown).
- ✅ Updated `BugDetector` default to `800×600`.
- ❌ Softlock still used start-of-input anchor (not sliding window).

### 3.3 Phase 3 — Full Blocker Resolution (v3, current)

After reading `TEAM_CHECKPOINT.md` from Person 1, systematically resolved every blocker:

| Blocker | Issue | Fix | Status |
|---|---|---|---|
| **B2** | Detector fix not pushed to GitHub | Fixed locally, ready to push | ✅ |
| **B3** | Softlock never fires — anchored to first input frame | Changed to **sliding window**: compares current position against position **300 frames ago** in `frame_history` buffer | ✅ |
| **B4** | `to_markdown()` crashes — `tabulate` missing | Added `tabulate>=0.9` to `requirements.txt` | ✅ |
| **B5** | "Running Time" hardcoded `02:15:30`; PDF button placeholder | Computed dynamically from telemetry `frames / 60`; PDF button hidden | ✅ |
| **B6** | `BugDetector()` defaults to 1920×1080 | Changed default to `800×600` | ✅ |
| **B7** | `use_container_width` deprecated | Replaced with `width="stretch"` | ✅ |

---

## 4. Detection Rules (final, v3)

| Bug Type | Severity | Rule | Debounce |
|---|---|---|---|
| **Out of Bounds** | CRITICAL | `x < -500 OR x > W+500 OR y < -500 OR y > H+1000` | Once per event (resets when player returns in-bounds) |
| **Infinite Fall** | HIGH | Not grounded + `abs(vel_y) > 0.5` for **exactly 120** consecutive frames | Fires once at frame 120 |
| **Wall Clip** | CRITICAL | Positional delta `> 25 px/frame` + collision evidence (current or previous frame, or `dx > 20`) | 60-frame cooldown after each detection |
| **Softlock** | HIGH | Continuous non-`"none"` input for ≥ 300 frames AND displacement from position **300 frames ago** `< 5 px` | Fires once, counter resets |

### 4.1 Key Design Decision: Softlock Sliding Window (B3 fix)

**Problem:** Agent always presses buttons → softlock counter never resets → old code anchored displacement to first-ever input frame → jumping in the pit creates >100px displacement → never triggers.

**Solution:** Instead of anchoring to the start of input, we compare `frame_history[-300]` (the frame exactly 300 frames ago) against the current frame. When the agent is trapped in the pit and lands back on the floor, displacement from 300 frames ago ≈ 0px → triggers correctly.

---

## 5. Files Delivered (final state)

### `analysis/bug_detector.py` — v3
- All 4 checks run independently every frame.
- OOB debounced (1 report per event).
- Wall Clip cooldown (60 frames).
- Softlock uses 300-frame sliding window.
- Default world size `800×600`.

### `analysis/reporter.py` — v1 (unchanged, works correctly)
- Generates `bug_{id}.json` + `bug_{id}.md` per bug.
- Report schema: `bug_id`, `severity`, `type`, `coordinates_xyz`, `frame_id`, `timestamp`, `reproduction_sequence`.

### `analysis/run_analysis.py` — standalone analysis runner
- Reads `data/logs/telemetry.csv`, runs `BugDetector(800, 600)`, writes reports via `BugReporter`.
- Can be run independently: `python analysis/run_analysis.py`.

### `dashboard/app.py` — v2
- **Section A**: Dynamic running time from telemetry, frame count, bug count, economics banner.
- **Section B**: Seaborn KDE heatmap + red ✖ bug markers.
- **Section C**: Filterable bug table, working Markdown export (with `tabulate`).

### `requirements.txt` — updated
- Added `tabulate>=0.9`.

---

## 6. What's Left / Dependencies

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Push all Person 2 fixes to GitHub | Person 2 | ⏳ Needs collaborator access (403 error) |
| 2 | `main.py --analyze` wiring (B1) | Person 1 / Team | Waiting for team decision — Person 1 to call `BugDetector` + `BugReporter` after run |
| 3 | End-to-end test: T4 + T5 from TEAM_CHECKPOINT | Everyone | After B1 is wired |
| 4 | Screenshots for pitch deck | Person 3 | After dashboard shows bugs |

---

## 7. How to Test Person 2's Code

```powershell
# After a simulation run that produced data/logs/telemetry.csv:
python analysis/run_analysis.py

# Check reports:
dir data/reports/

# Launch dashboard:
streamlit run dashboard/app.py
# Opens http://localhost:8501
```

Expected results after full pipeline:
- Bug detector finds Wall Clip, Infinite Fall, and Softlock events
- `data/reports/` contains JSON + MD files per bug
- Dashboard shows frame count, bug count, heatmap with red markers, filterable bug table
