# Person 2 demo runbook

Work from this repository directory. No API keys are required.

```powershell
python main.py --headless --frames 36000 --seed 42 --verify
python -m unittest discover -s tests -v
python -m streamlit run dashboard/app.py
```

For the live game demo, use `python main.py --seed 11 --analyze`.
The game opens for two simulated minutes; Escape ends it early and writes reports.
Refresh the dashboard after the analysis finishes.
For an existing recording, use `python analysis/run_analysis.py`.

Dashboard exports contain the currently filtered bugs and their reproduction inputs.
Markdown export does not need tabulate. JSON is also downloadable. Direct PDF export
is not implemented; print the Markdown from a document viewer if needed.

Environment note: this machine has Python 3.14. The original pygame 2.6.1 source
build failed here, so local verification uses pygame-ce (the same pygame import).
The shared requirements file is unchanged. On the team's supported Python 3.11/3.12
setup, install the repository requirements as usual. On this Python 3.14 machine:

```powershell
python -m pip install pygame-ce streamlit pandas matplotlib seaborn numpy
```

The implementation was tested first in an archive checkout, then applied to a fresh
Git clone of main to preserve the team's latest work. Only Person 2 files are in the
commit; core/, main.py and the shared requirements are unchanged.
