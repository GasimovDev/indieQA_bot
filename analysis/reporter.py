import json
import os
from typing import List, Dict, Any

class BugReporter:
    def __init__(self, output_dir: str = "data/reports") -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(self, bug: Dict[str, Any]) -> None:
        """Generates both Markdown and JSON reports for a single bug."""
        bug_id = bug.get('bug_id', 'unknown')
        
        # Save JSON
        json_path = os.path.join(self.output_dir, f"bug_{bug_id}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(bug, f, indent=4)
            
        # Save Markdown
        md_path = os.path.join(self.output_dir, f"bug_{bug_id}.md")
        md_content = self.format_markdown(bug)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
    @staticmethod
    def format_markdown(bug: Dict[str, Any]) -> str:
        bug_id = bug.get('bug_id', 'unknown')
        bug_type = bug.get('type', 'Unknown')
        severity = bug.get('severity', 'UNKNOWN')
        frame_id = bug.get('frame_id', -1)
        timestamp = bug.get('timestamp', 0)
        coords = bug.get('coordinates_xyz', (0,0,0))
        sequence = bug.get('reproduction_sequence', [])
        
        return f"""# Bug Report: {bug_type} ({bug_id})

## Overview
- **Type**: {bug_type}
- **Severity**: {severity}
- **Frame ID**: {frame_id}
- **Timestamp**: {timestamp}

## Location
- **Coordinates (X, Y, Z)**: {coords}

## Reproduction
**Last 30 Inputs**:
```json
{json.dumps(sequence, indent=2)}
```
"""
            
    def generate_all_reports(self, bugs: List[Dict[str, Any]]) -> None:
        """Generates reports for a list of bugs."""
        for bug in bugs:
            self.generate_report(bug)
