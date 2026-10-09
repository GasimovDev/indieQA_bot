import csv
import os
import time

class TelemetryLogger:
    def __init__(self, log_path="data/logs/telemetry.csv"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        
        self.file = open(self.log_path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.file)
        self.writer.writerow([
            "frame_id", "timestamp", "pos_x", "pos_y", 
            "vel_x", "vel_y", "is_grounded", "active_input", "collision_state"
        ])
        self.start_unix = time.time()
        
    def log_frame(self, frame_id, pos_x, pos_y, vel_x, vel_y, is_grounded, active_input, collision_state):
        timestamp = self.start_unix + (frame_id / 60.0)
        self.writer.writerow([
            frame_id, 
            f"{timestamp:.3f}", 
            f"{pos_x:.2f}", 
            f"{pos_y:.2f}", 
            f"{vel_x:.2f}", 
            f"{vel_y:.2f}", 
            str(bool(is_grounded)), 
            active_input if active_input else "none", 
            str(bool(collision_state))
        ])
        
    def close(self):
        if self.file and not self.file.closed:
            self.file.close()
