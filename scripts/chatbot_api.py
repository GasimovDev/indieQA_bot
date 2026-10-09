"""Smoke-test the IndieQA Fix Advisor from a terminal.

Examples:
    python scripts/chatbot_api.py --bug-type "Wall Clip" --question "How do we fix it?"
    python scripts/chatbot_api.py --bug-json data/reports/bug_example.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.advisor import AdvisorAPIError, configured_advisor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Ask the IndieQA Fix Advisor.')
    parser.add_argument('--question', default='Recommend a fix and a regression test.')
    parser.add_argument('--bug-json', type=Path, help='Existing bug report JSON file.')
    parser.add_argument('--bug-type', default='Wall Clip')
    parser.add_argument('--priority', default='P0')
    parser.add_argument('--severity', default='CRITICAL')
    parser.add_argument('--frame', type=int, default=85)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bug_json:
        bug = json.loads(args.bug_json.read_text(encoding='utf-8'))
    else:
        bug = {
            'type': args.bug_type,
            'priority': args.priority,
            'severity': args.severity,
            'frame_id': args.frame,
            'coordinates_xyz': [784.0, 390.0, 0.0],
            'reproduction_sequence': ['right+jump', 'right', 'right+jump'],
        }
    advisor = configured_advisor()
    print(f'Backend: {advisor.name}', file=sys.stderr)
    try:
        print(advisor.answer(args.question, bug))
    except AdvisorAPIError as exc:
        print(f'Advisor API error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
