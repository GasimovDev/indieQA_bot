# TEAM CHECKPOINT — IndieQA (whole project)

> **Event:** Neurobridge Game Summit 2026 Hackathon, Baku · **Repo:** https://github.com/GasimovDev/indieQA_bot
> **Snapshot:** 2026-10-09 ~14:00 (Baku) · `main` @ Module 1 merged · Pitch deadline **20:00**
> Detailed Person 1 log: [`docs/PERSON1_CHECKPOINT.md`](PERSON1_CHECKPOINT.md)

---

## 1. What does IndieQA do? (plain language)

Small indie studios can't afford a QA team. A human tester costs ~**$25/hour** and still misses physics bugs like walking through walls or falling out of the map — the bugs that cause angry Steam reviews on launch day.

**IndieQA replaces the human tester for physics/collision bugs.** A bot plays the level by itself, thousands of times faster than real time, deliberately pushing into walls, corners, edges and gaps. Every frame of what happens is recorded. Afterwards, a detector scans the recording for the tell-tale "signatures" of bugs and a dashboard shows **what** broke, **where** on the map, and **the exact button sequence to reproduce it**. Cost: ~**$0.04/hour** of local compute.

For the hackathon we built our own small test level with **3 bugs planted on purpose**, so we can prove the bot finds them:

| Planted bug | What a player would see |
|---|---|
| **Wall_Clip** | Jumping into the right wall at the wrong spot teleports you *through* it, outside the map |
| **Infinite_Fall** | One hole in the floor has no bottom — you fall forever |
| **Softlock_Pit** | A pit 150 px deep, but you can only jump 100 px — you're stuck forever while still pressing buttons |

---

## 2. How does it work?

```
 ┌──────────────┐  buttons  ┌──────────────┐ frame state ┌──────────────┐  CSV   ┌───────────────┐ bugs ┌──────────────┐ JSON/MD ┌──────────────┐
 │  QA AGENT    │ ────────► │ GAME ENGINE  │ ──────────► │  TELEMETRY   │ ─────► │ BUG DETECTOR  │ ───► │   REPORTER   │ ──────► │  DASHBOARD   │
 │ core/agent   │ ◄──────── │ core/engine  │             │ core/telem.  │        │ analysis/     │      │ analysis/    │         │ dashboard/   │
 └──────────────┘ what it   └──────────────┘             └──────────────┘        │ bug_detector  │      │ reporter     │         │ app.py       │
                  "sees"           ▲                     data/logs/telemetry.csv  └───────────────┘      └──────────────┘         └──────────────┘
                                   │ main.py runs this loop 60×/game-second                               data/reports/*.json       localhost:8501
        └──────────────────── Person 1 (Module 1) ─────────────────────┘          └───────────────────── Person 2 (Module 2) ──────────────────────┘
```

1. **`main.py`** starts the loop. Every frame: the **agent** looks at the player's state → picks buttons → the **engine** moves the player one frame (gravity, collisions) → **telemetry** writes that frame to `data/logs/telemetry.csv` (position, speed, buttons, grounded, touching-something).
2. When the player is lost (fell / clipped out) or stuck in the pit for a while, `main.py` respawns it at another start point, so one run tests the whole map.
3. **Bug detector** reads the CSV and applies rules:
   - moved **> 25 px in one frame while colliding** → *Wall Clip*
   - falling **> 120 frames** without touching anything → *Infinite Fall*
   - holding buttons **> 300 frames** but moved **< 5 px** → *Softlock*
   - outside the 800 × 600 map → *Out of Bounds*
4. **Reporter** writes one JSON + Markdown report per bug into `data/reports/` (type, severity, location, last 30 button presses = reproduction steps).
5. **Dashboard** (Streamlit website on your own PC) shows: frames analysed, bug count, a heatmap of where the bot went with red ✖ on bug locations, and a filterable bug table with export.

---

## 3. Where is the "AI"?

Be precise in the pitch — judges will ask.

| Part | What it really is | How to describe it honestly |
|---|---|---|
| **QA Agent** (`core/agent.py`) | An **autonomous rule-based agent**: a 2-mode state machine with seeded randomness. *Boundary_Seeker* "senses" the level with raycasts (wall ahead?) and ground probes (ledge ahead?), walks to boundaries and hugs edges. When it touches a wall it switches to *Input_Spammer*, which fires rapid button combos to force glitches. | "An autonomous agent that explores the level and adversarially stress-tests geometry." It is **not** machine learning and **not** an LLM. |
| **Bug Detector** (`analysis/bug_detector.py`) | **Rule-based anomaly classification** on physics signals (thresholds on displacement, fall time, input-vs-movement). | "Physics-anomaly classifier based on kinematic signatures." |

Why no ML is a **strength** (Feasibility slide): **zero training data**, runs fully **offline**, **deterministic** (same seed ⇒ same run ⇒ every bug is reproducible), **cheap** ($0.04/h), and explainable (each bug comes with the exact input sequence).

---

## 4. Does it work live while the game runs?

**Current behaviour: run first, look after (batch), not live streaming.**

- While `main.py` runs, telemetry is written to the CSV continuously (in small batches).
- The dashboard re-reads the CSV at most every 5 s **when the page reruns** (reload / interact). So reloading during a run shows growing frame counts and heatmap, but there's **no automatic live refresh**.
- **Bugs appear after** `python main.py --headless --analyze` (detection + reports), then reload the dashboard.

What the demo can show today: (1) `python main.py` — watch the bot play in the game window, glitch counter in the HUD; (2) the dashboard with the resulting data (once B1 is solved).
Optional upgrade (post-blockers): run the detector incrementally from `main.py` and have the dashboard auto-refresh every few seconds → a real "live" view.

---

## 5. Module status (verified 2026-10-09)

| Module | Owner | On GitHub `main`? | Verified |
|---|---|---|---|
| Engine + 3 glitches (`core/engine.py`) | Person 1 | ✅ | Self-test 5/5: jump apex 100.0 px, pit inescapable, fall uncapped, clip 48.8 px, no false > 25 px moves in 20k random frames |
| Telemetry (`core/telemetry.py`) | Person 1 | ✅ | Self-test 6/6: exact columns, contiguous frames, simulated timestamps, 0.6 µs/frame |
| Agent (`core/agent.py`) | Person 1 | ✅ | Self-test 5/5: deterministic, both modes, finds all 3 glitches unaided |
| Runner (`main.py`) | Person 1 | ✅ | 36,000 frames (10 game-min) in 2.1 s; rendered mode real-time 60 FPS |
| Bug detector (`analysis/bug_detector.py`) | Person 2 | ⚠️ old version only | Wall Clip 22/22 ✅ · Infinite Fall 0 ❌ · Softlock 0 ❌ · Out of Bounds spam (14,424) ❌ |
| Reporter (`analysis/reporter.py`) | Person 2 | ⚠️ | Works when called, **but nothing calls it** |
| Dashboard (`dashboard/app.py`) | Person 2 | ⚠️ | Loads, frame count correct; 0 bugs shown (no reports); Markdown export crashes; running time mocked |
| Pitch deck | Person 3 | — | Not in repo (due 20:00, PDF/PPT ≤ 30 MB) |

**Ground truth the telemetry already contains** (10 game-min run, seed 42), checked against the spec rules directly: **22 Wall Clips, 48 Infinite Falls, 13 Softlocks.** The data side is done; detection/reporting is the gap.

---

## 6. Blockers & issues (owner → action)

| # | Issue | Owner | Action |
|---|---|---|---|
| ~~B1~~ | ✅ **Fixed (Person 1):** `main.py --analyze` now runs `BugDetector(800, 600)` **and** `BugReporter` → `data/reports/bug_*.json/.md`; old `bug_*` reports are replaced each run so the dashboard shows the latest run only. `--reports-dir` to change the folder. Until B2 lands, the old detector still produces ~1 report per out-of-bounds frame (3,318 files for a 2-min run). | Person 1 | Done |
| **B2** | Person 2's detector fix (all checks every frame + debounce) **is not pushed** — GitHub still has the 12:32 version | Person 2 | `git pull origin main`, then commit & push `analysis/` |
| **B3** | Softlock never fires: start position anchored at first input; our agent always presses something | Person 2 | Compare against position **300 frames ago** (sliding window) |
| B4 | Dashboard "Export Markdown" crashes: `tabulate` not installed | Person 2 (+ shared `requirements.txt`) | add `tabulate>=0.9` to requirements |
| B5 | "Running Time" metric hardcoded `02:15:30`; "Export PDF" is a placeholder message | Person 2 | compute from telemetry (`frames / 60`) or relabel; hide PDF button if not implemented |
| B6 | `BugDetector()` defaults to 1920×1080 | Person 2 | use `BugDetector(800, 600)` wherever it's constructed |
| B7 | Streamlit warning: `use_container_width` deprecated | Person 2 | cosmetic, `width="stretch"` |

---

## 7. What to test, and how

All commands from the repo folder in PowerShell:
```powershell
cd C:\Users\Fidan-HP\Desktop\instruction\indieQA_bot
git pull origin main
.\venv\Scripts\activate
```
(First time on a new PC: `python -m venv venv`, then `pip install -r requirements.txt`.)

### T1 — Module 1 self-tests (≈ 10 s)
```powershell
python -m core.engine
python -m core.telemetry
python -m core.agent
```
✅ Expect only `[PASS]` lines (5 + 6 + 5).

### T2 — Play the level yourself (understand the bugs)
```powershell
python -m core.engine --play
```
Arrows/WASD move, Space jump, 1/2/3 respawn, Esc quit.
- [ ] Press **1**, walk right into the red gap → you fall forever
- [ ] Press **2**, walk right into the yellow pit → you can't jump out
- [ ] Press **3**, hold → and jump at the right wall → you pass through it (HUD: `last glitch: Wall_Clip`)

### T3 — Watch the bot play (demo view)
```powershell
python main.py
```
- [ ] HUD shows the mode switching between `Boundary_Seeker` and `Input_Spammer`
- [ ] Within ~2 minutes it falls in the gap, gets stuck in the pit and clips the wall; the console prints `Wall_Clip` lines

### T4 — Full pipeline, fast
```powershell
python main.py --headless --frames 36000 --analyze
```
- [ ] Finishes in a few seconds, prints episodes and `glitch events`
- [ ] `[analyze]` line: **today** expect only Wall Clip + huge Out of Bounds; **after B2/B3** expect Wall Clip, Infinite Fall and Softlock

### T5 — Dashboard
```powershell
streamlit run dashboard/app.py
```
Opens http://localhost:8501.
- [ ] "Total Frames Analyzed" = frames of your last run
- [ ] Heatmap shows where the bot walked (floor line, pit, right wall)
- [ ] Bug count / table / red ✖ — after T4 with `--analyze` (clean results only after B2)
- [ ] Severity filter, Export Markdown (after B4)

### T6 — Reproducibility (good pitch point)
```powershell
python main.py --headless --seed 7 --out data/logs/a.csv
python main.py --headless --seed 7 --out data/logs/b.csv
```
```powershell
python -c "import pandas as pd; a, b = (pd.read_csv(f'data/logs/{n}.csv').drop(columns='timestamp') for n in 'ab'); print('identical:', a.equals(b))"
```
- [ ] Prints `identical: True` (verified: 7,200 / 7,200 rows). Only `timestamp` differs, because it starts from each run's real clock time.

### T7 — Demo dry run (before 20:00)
- [ ] Fresh `git pull`, run T3 + T4 + T5 in the order you'll present
- [ ] Pick a seed where a Wall_Clip happens early in rendered mode for the live demo
- [ ] Screenshot game window + dashboard for the deck (Person 3)

---

## 8. Next steps (in order)

1. **Person 2:** pull, push the detector fix (B2), sliding-window softlock (B3), `BugDetector(800, 600)` (B6), `tabulate` (B4).
2. ~~B1~~ done: `--analyze` writes reports.
3. **Everyone:** re-run T4 + T5 → all 3 bug types visible on the dashboard.
4. **Person 3:** screenshots + numbers from §5 and §1 into the deck; slides "3 Failure Modes" and "Feasibility" (zero training data, $0.04/h, deterministic).
5. Demo dry run (T7).
