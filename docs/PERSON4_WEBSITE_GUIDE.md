# Person 4 — Website Guide (start here)

> Welcome! You own the **website** (the dashboard people look at during the pitch).
> Deadline for the whole project: **20:00 today**. Keep it simple and working.

---

## 1. The project in 30 seconds

IndieQA is a **robot game tester**.

1. A **bot** plays a small 2D game by itself, very fast, trying to break it.
2. Every frame of the game is saved to a file: `data/logs/telemetry.csv`.
3. A **detector** reads that file and finds the bugs (walking through walls, falling forever, getting stuck).
4. Each bug is saved as a small report file in `data/reports/`.
5. **The website shows all of this**: how much the bot explored, where the bugs are on the map, and a list of bugs with the buttons that caused them.

The game has 3 bugs planted on purpose: **Wall Clip**, **Infinite Fall**, **Softlock**. The website's job is to make it obvious to judges that the bot found them.

```
bot + game (Person 1)  →  telemetry.csv  →  detector + reports (Person 2)  →  WEBSITE (you)
```

---

## 2. First: talk to Person 2 ⚠️

The current website is `dashboard/app.py`, written by **Person 2** (Streamlit). Before you edit it, agree with Person 2 **who owns `dashboard/app.py` from now on**, so you don't overwrite each other.
Person 2 has a newer version of it on their laptop that is **not on GitHub yet** — get that version first.

**Don't edit:** `core/` and `main.py` (Person 1), `analysis/` (Person 2). You only *read* their output files.

---

## 3. Setup (≈ 5 min)

```powershell
git clone https://github.com/GasimovDev/indieQA_bot.git
cd indieQA_bot
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
You need **push access**: ask GasimovDev to add your GitHub account as a collaborator (Settings → Collaborators).

**Get real data and open the website:**
```powershell
python main.py --headless --frames 36000 --analyze
streamlit run dashboard/app.py
```
The first command plays 10 minutes of game in ~3 seconds and writes the CSV + bug reports. The second opens the website at **http://localhost:8501**.

To watch the bot play (nice for understanding): `python main.py --seed 11`

---

## 4. The data you get (the only interface)

### A) `data/logs/telemetry.csv` — one row per game frame (60 rows = 1 second)
| column | example | meaning |
|---|---|---|
| `frame_id` | `744` | frame number |
| `timestamp` | `1760012345.400000` | time (seconds) |
| `pos_x`, `pos_y` | `448.0000`, `558.0000` | player position in pixels. Map is **800 × 600**, **y goes DOWN** |
| `vel_x`, `vel_y` | `0.0000`, `0.5000` | speed |
| `is_grounded` | `True` | standing on something |
| `active_input` | `right+jump` | buttons pressed (`none` = nothing) |
| `collision_state` | `True` | touching a wall/floor |

Positions far outside 0–800 / 0–600 are normal: that's the player falling forever or clipped out of the map — **clip your plot axes** (e.g. x −50…850, y −50…650) or the map becomes a dot.

### B) `data/reports/bug_<id>.json` — one file per bug
```json
{
  "bug_id": "3f2a…",
  "type": "Wall Clip",                 // "Wall Clip" | "Infinite Fall" | "Softlock" | "Out of Bounds"
  "severity": "CRITICAL",              // CRITICAL | HIGH | MEDIUM
  "coordinates_xyz": [800.0, 389.0, 0.0],
  "frame_id": 85,
  "timestamp": 1760012341.416667,
  "reproduction_sequence": ["right+jump", "right", "..."]   // last 30 button presses before the bug
}
```
(There's also a `.md` version of each report.) Reports are **replaced every run**.

### C) The real level shape (optional, makes the map look great)
You can draw the actual walls/floors behind the heatmap:
```python
from core.engine import build_level
level = build_level()
for c in level.colliders:          # c.name, c.rect (x, y, w, h)
    ...                            # draw a grey rectangle
level.fall_gap, level.pit, level.seam   # rectangles of the 3 bug zones
```
This only *reads* Person 1's code — no edits needed.

---

## 5. What to build (priority order)

**Must have (for the pitch):**
1. **Header numbers:** game time tested (`frames / 60`), frames analysed, bugs found, and the banner **Human QA $25/h vs IndieQA $0.04/h**.
2. **Map:** the level drawn (section 4C) + heatmap of where the bot went + **big red markers at each bug** (colour/icon per bug type).
3. **Bug table:** type, severity, position, time; filter by severity/type.
4. **Bug detail:** click/select a bug → show its `reproduction_sequence` (the 30 buttons) — this is our "we tell you how to reproduce it" selling point.
5. **Works with no data** (shows a friendly "run `python main.py --headless --analyze` first" message instead of crashing).

**Nice to have:**
6. **Bug summary cards:** one card per type with count (Wall Clip 22 · Infinite Fall 48 · Softlock 16).
7. **Export** button for a Markdown report (needs `tabulate`, already in requirements on Person 2's version).
8. **"Live" mode:** while `python main.py` runs, the CSV grows. Streamlit 1.65 can re-run a part of the page every few seconds:
   ```python
   @st.fragment(run_every=3)
   def live_panel(): ...   # re-read the CSV, update numbers + map
   ```
   For live *bugs* you'd run Person 2's detector inside the page: `from analysis.bug_detector import BugDetector` → `BugDetector(800, 600).process_telemetry(df)`.

**Don't spend time on:** login, databases, deploying online, a separate React site. Streamlit on localhost is what the spec asks for and is enough for the demo.

---

## 6. Check your work

- [ ] `python main.py --headless --frames 36000 --analyze` then reload the site → numbers change
- [ ] Map shows the level; red markers sit on the right wall, the gap (x≈240–300) and the pit (x≈440–480)
- [ ] Delete `data/reports/*` → site still loads (no crash)
- [ ] Looks good on the projector: big fonts, dark theme, nothing overlapping
- [ ] Commit + push before **19:00**, so Person 3 can take screenshots for the deck

## 7. Who to ask
| Question about | Ask |
|---|---|
| CSV, the game, the bot, `main.py` | Person 1 |
| Bug types, detector, report files, current `dashboard/app.py` | Person 2 |
| What the judges should see / slides | Person 3 |

More detail: `docs/TEAM_CHECKPOINT.md`.
