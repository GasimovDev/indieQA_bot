import pandas as pd
import uuid
from typing import List, Dict, Any, Optional

class BugDetector:
    def __init__(self, world_width: float = 1920.0, world_height: float = 1080.0):
        self.world_width = world_width
        self.world_height = world_height
        
        # State tracking for bugs
        self.fall_frames = 0
        self.softlock_frames = 0
        self.softlock_start_x = 0.0
        self.softlock_start_y = 0.0
        
        self.detected_bugs: List[Dict[str, Any]] = []
        self.frame_history: List[Dict[str, Any]] = []
        
    def process_telemetry(self, telemetry_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Processes a batch or single frame of telemetry data."""
        for _, row in telemetry_data.iterrows():
            self._analyze_frame(row.to_dict())
            
        return self.detected_bugs

    def _analyze_frame(self, frame: Dict[str, Any]) -> None:
        self.frame_history.append(frame)
        if len(self.frame_history) > 300:
            self.frame_history.pop(0)
            
        bug = self._check_oob(frame) or \
              self._check_infinite_fall(frame) or \
              self._check_wall_clip(frame) or \
              self._check_softlock(frame)
              
        if bug:
            self.detected_bugs.append(bug)

    def _check_oob(self, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        x, y = frame.get('pos_x', 0), frame.get('pos_y', 0)
        if x < 0 or x > self.world_width or y < 0 or y > self.world_height:
            return self._create_bug_report("Out of Bounds", "CRITICAL", frame)
        return None

    def _check_infinite_fall(self, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        vel_y = frame.get('vel_y', 0)
        is_grounded = frame.get('is_grounded', True)
        collision_state = frame.get('collision_state', True)
        
        # In many 2D games, y goes down as value increases, so falling means vel_y > 0.
        if vel_y > 0 and not is_grounded and not collision_state:
            self.fall_frames += 1
            if self.fall_frames > 120:
                self.fall_frames = 0  # Reset to avoid continuous spam
                return self._create_bug_report("Infinite Fall", "HIGH", frame)
        else:
            self.fall_frames = 0
        return None

    def _check_wall_clip(self, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if len(self.frame_history) < 2:
            return None
            
        prev_frame = self.frame_history[-2]
        dx = abs(frame.get('pos_x', 0) - prev_frame.get('pos_x', 0))
        dy = abs(frame.get('pos_y', 0) - prev_frame.get('pos_y', 0))
        
        delta = (dx**2 + dy**2)**0.5
        collision_state = frame.get('collision_state', False)
        
        if delta > 25.0 and collision_state: 
            return self._create_bug_report("Wall Clip", "CRITICAL", frame)
        return None

    def _check_softlock(self, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        active_input = frame.get('active_input', '')
        
        if active_input and active_input != 'none':
            if self.softlock_frames == 0:
                self.softlock_start_x = frame.get('pos_x', 0)
                self.softlock_start_y = frame.get('pos_y', 0)
            
            self.softlock_frames += 1
            
            if self.softlock_frames > 300:
                dx = abs(frame.get('pos_x', 0) - self.softlock_start_x)
                dy = abs(frame.get('pos_y', 0) - self.softlock_start_y)
                dist = (dx**2 + dy**2)**0.5
                
                if dist < 5.0:
                    self.softlock_frames = 0 # Reset after detection
                    return self._create_bug_report("Softlock", "HIGH", frame)
        else:
            self.softlock_frames = 0
            
        return None

    def _create_bug_report(self, bug_type: str, severity: str, frame: Dict[str, Any]) -> Dict[str, Any]:
        sequence = [f.get('active_input', '') for f in self.frame_history[-30:]]
        
        return {
            "bug_id": str(uuid.uuid4()),
            "type": bug_type,
            "severity": severity,
            "coordinates_xyz": (frame.get('pos_x', 0), frame.get('pos_y', 0), 0.0), 
            "frame_id": frame.get('frame_id', -1),
            "timestamp": frame.get('timestamp', 0),
            "reproduction_sequence": sequence
        }
