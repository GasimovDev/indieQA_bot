"""Analyze a recorded run: python analysis/run_analysis.py [--csv PATH]."""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import sys
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from analysis.bug_detector import BugDetector
from analysis.reporter import BugReporter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "data/logs/telemetry.csv")
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "data/reports")
    args = parser.parse_args(argv)
    try:
        bugs = BugDetector().process_telemetry(pd.read_csv(args.csv))
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        parser.exit(1, f"Analysis failed: {exc}\n")
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    for pattern in ("bug_*.json", "bug_*.md"):
        for path in args.reports_dir.glob(pattern):
            path.unlink()
    BugReporter(str(args.reports_dir)).generate_all_reports(bugs)
    print(f"Reports: {dict(Counter(b['type'] for b in bugs))}")
    print(f"Written to {args.reports_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
