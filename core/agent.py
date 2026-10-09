import random

class AutonomousAgent:
    def __init__(self):
        self.mode = "Boundary_Seeker"
        self.spammer_frames = 0
        self.direction = 1 # 1 for right, -1 for left
        self.stuck_frames = 0
        self.last_x = 0.0
        
    def get_action(self, pos_x, pos_y, is_grounded, collision_state):
        active_input = []
        
        # Check stuck status for boundary seeking
        if abs(pos_x - self.last_x) < 0.5:
            self.stuck_frames += 1
        else:
            self.stuck_frames = 0
        self.last_x = pos_x

        # Mode Transitions
        if collision_state and self.mode == "Boundary_Seeker" and self.stuck_frames > 5 and random.random() < 0.2:
            self.mode = "Input_Spammer"
            self.spammer_frames = 30
            
        if self.mode == "Input_Spammer":
            self.spammer_frames -= 1
            if self.spammer_frames <= 0:
                self.mode = "Boundary_Seeker"
                if random.random() < 0.5:
                    self.direction *= -1 
                
        # Action Logic
        if self.mode == "Boundary_Seeker":
            active_input.append("right" if self.direction == 1 else "left")
            
            # If stuck against a wall, try jumping.
            if self.stuck_frames > 15:
                active_input.append("jump")
                
            # If stuck for a very long time (>400 frames), reverse direction to explore elsewhere.
            # We wait 400 frames to ensure the 300-frame softlock anomaly is successfully triggered.
            if self.stuck_frames > 400: 
                self.direction *= -1
                self.stuck_frames = 0
                
        elif self.mode == "Input_Spammer":
            # Rapid non-linear action combinations
            active_input.append("right" if self.direction == 1 else "left")
            
            if random.random() < 0.8:
                active_input.append("jump")
                
            # Dash forces high velocity (specifically tested for the Wall Clip anomaly)
            if random.random() < 0.5:
                active_input.append("dash")
                
        return "+".join(active_input) if active_input else "none"
