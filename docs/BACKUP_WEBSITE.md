# Backup website (branch `backup-plan1`)

A complete, working IndieQA website built as a **backup** in case the main website isn't ready for the pitch.
It lives in a separate file and does not touch Person 2's `dashboard/app.py`.

```powershell
git switch backup-plan1
.\venv\Scripts\activate
streamlit run dashboard/backup_site.py
```
Opens at http://localhost:8501. **☀ Light / ☾ Dark switch** at the top right (soft creme light mode, warm dark mode);
soft red = problems, green = IndieQA / coverage.

## What it shows
| Section | What |
|---|---|
| Cost banner | Human QA $25/h vs IndieQA $0.04/h, and what a human would have cost for the gameplay tested |
| KPIs | Game time tested, frames analysed, problems to fix, bug events, P0 count, ground covered |
| Map | The real level, green heatmap of where the bot went, markers where each problem starts, coloured by priority |
| **Fix first** | Priority board: P0 Fix before launch · P1 Fix this sprint · P2 Schedule · P3 Monitor / side effect |
| **Bug inspector** | Pick a problem (or press **Inspect** on a priority card) → step through every occurrence with **◀ Previous / Next ▶** or jump with the occurrence buttons → sharp 1600×1200 game-style screenshot of the bug moment (zoomed on the error point, rebuilt from telemetry with the real level), facts, the buttons that led to it, `.md` download |
| Bug log | Every detection, filter by priority/type, `.csv` / `.json` download |

**Priority score** = severity (CRITICAL 3, HIGH 2, MEDIUM 1) × (1 + log2(1 + occurrences per 10 min)).
Bugs caused by another bug moments earlier (falling forever after a wall clip, leaving the map after a fall)
are marked as **side effects** (P3), so the board lists only real root causes.

## Live demo
- Press **▶ Watch the bot play (seed 11)**: the game window opens and the page updates every 2 s.
  Wall Clip appears at ~1.4 s, Softlock at ~12.7 s.
- Press **⚡ Run a 10-min test (fast)**: 10 minutes of gameplay in ~3 s, full report.
- Or start the bot from a terminal (`python main.py --seed 11`); the page picks it up automatically.

Files: `dashboard/backup_site.py` (page), `dashboard/insights.py` (data, priority, map, screenshots),
`.streamlit/config.toml` (theme). Bugs come from Person 2's `analysis/bug_detector.py`.
