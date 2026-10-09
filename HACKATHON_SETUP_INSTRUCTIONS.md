# IndieQA — Hackathon Jury Setup Instructions

IndieQA is an autonomous QA system for finding physics and collision failures in small 2D games. The project runs locally and does not require an account, cloud service, or API key.

## 1. Requirements

- Python 3.11 or newer
- Windows PowerShell, macOS Terminal, or Linux shell
- 500 MB of free disk space

## 2. Install the project

Clone the repository and enter its directory:

```bash
git clone https://github.com/GasimovDev/indieQA_bot.git
cd indieQA_bot
```

Create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## 3. Run the automated verification

This command runs the simulation, analyzes the telemetry, generates reports, and checks the detector against the planted failures:

```bash
python main.py --headless --frames 36000 --verify
```

The verification should finish with `PASS` for Wall Clip, Infinite Fall, and Softlock, with no false alarms. It also creates or refreshes:

- `data/logs/telemetry.csv` — one row per game frame
- `data/reports/bug_*.json` — structured diagnostic reports
- `data/reports/bug_*.md` — readable diagnostic reports

To run the unit and dashboard interaction tests:

```bash
python -m unittest discover -s tests
```

## 4. Open the dashboard

Start the Streamlit dashboard:

```bash
streamlit run dashboard/app.py
```

Open the local URL printed in the terminal, normally:

```text
http://localhost:8501
```

The dashboard presents:

- Total game time and frames analyzed
- Counts of Wall Clip, Infinite Fall, Softlock, and Out of Bounds events
- The real level geometry and exploration trail
- Color-coded failure markers and event selection
- Severity and priority filters
- Trigger coordinates, frame number, and recommended investigation
- Reproduction inputs immediately before each failure
- Downloadable Markdown and JSON diagnostics

## 5. Live demonstration

For the interactive demo, keep the dashboard open and run this command in a second terminal:

```bash
python main.py --seed 11
```

In the dashboard sidebar, click **Start live demo** or enable **Auto-refresh every second**. The telemetry trail grows as the bot explores, and detected failure points appear on the map.

The demo level contains three intentional failures:

1. **Wall Clip** — collision resolution can eject the player through the right wall.
2. **Infinite Fall** — a floor gap has no safe recovery boundary.
3. **Softlock** — the player can become trapped in a pit that is higher than its jump capability.

## 6. How the system works

```text
autonomous agent → Pygame level → frame telemetry → rule-based detector → reports → Streamlit dashboard
```

The system uses a deterministic exploration agent and explainable physics rules. It does not require machine-learning training data. Each finding includes the event type, severity, location, trigger frame, and recent input sequence needed for investigation.

## 7. Troubleshooting

If the dashboard says that telemetry is missing, run:

```bash
python main.py --headless --frames 36000 --analyze
```

Then refresh the dashboard page.

If PowerShell blocks virtual-environment activation, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

If port `8501` is already in use, start Streamlit on another port:

```bash
streamlit run dashboard/app.py --server.port 8502
```

