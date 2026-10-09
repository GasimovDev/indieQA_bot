import pygame
import sys
from core.telemetry import TelemetryLogger
from core.agent import AutonomousAgent

class Engine:
    def __init__(self, headless=False):
        self.headless = headless
        self.width = 800
        self.height = 600
        
        if not self.headless:
            pygame.init()
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("IndieQA Core Engine")
            self.clock = pygame.time.Clock()
            
        self.telemetry = TelemetryLogger()
        self.agent = AutonomousAgent()
        
        self.reset()
        
    def reset(self):
        self.frame_id = 0
        self.running = True
        
        # Player state
        self.pos_x = 50.0
        self.pos_y = 100.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.is_grounded = False
        self.collision_state = False
        self.rect = pygame.Rect(int(self.pos_x), int(self.pos_y), 20, 20)
        
        # Physics constants
        self.gravity = 0.5
        self.jump_impulse = -10.0 # Reaches exactly j_max = 100px height
        self.speed = 5.0
        self.max_fall_speed = 30.0
        
        # Build Level Geometry
        self.platforms = []
        
        # 1. Spawn Area Floor
        self.platforms.append(pygame.Rect(0, 400, 200, 200)) 
        
        # 2. Infinite Fall Gap (x=200 to 300) 
        # Missing ground collision -> causes y -> +infinity
        
        # 3. Middle Area
        self.platforms.append(pygame.Rect(300, 400, 200, 200))
        
        # 4. Wall Clip Glitch block (2px gap geometry at x=400)
        self.platforms.append(pygame.Rect(400, 380, 2, 20))
        
        # 5. Softlock Pit (x=500 to 650)
        # Left wall (h=150px)
        self.platforms.append(pygame.Rect(500, 250, 20, 150))
        # Pit Floor
        self.platforms.append(pygame.Rect(520, 400, 130, 200))
        # Right wall (h=150px)
        self.platforms.append(pygame.Rect(650, 250, 20, 150))

    def step(self):
        # 1. Agent Input
        active_input = self.agent.get_action(self.pos_x, self.pos_y, self.is_grounded, self.collision_state)
        
        # 2. Physics & Movement
        self.vel_y += self.gravity
        if self.vel_y > self.max_fall_speed:
            self.vel_y = self.max_fall_speed
            
        if "left" in active_input:
            self.vel_x = -self.speed
            if "dash" in active_input:
                self.vel_x = -26.0
        elif "right" in active_input:
            self.vel_x = self.speed
            if "dash" in active_input:
                self.vel_x = 26.0
        else:
            self.vel_x = 0.0
            
        if "jump" in active_input and self.is_grounded:
            self.vel_y = self.jump_impulse
            self.is_grounded = False
            
        # 3. Collision Detection (AABB)
        self.pos_x += self.vel_x
        self.rect.x = int(self.pos_x)
        
        self.collision_state = False
        
        # X Collisions
        for plat in self.platforms:
            if self.rect.colliderect(plat):
                self.collision_state = True
                
                # Intentional Wall Clip Glitch implementation
                if plat.width == 2 and abs(self.vel_x) >= 25.0:
                    # Narrow 2px gap lets high-velocity input pass through
                    pass
                else:
                    if self.vel_x > 0:
                        self.rect.right = plat.left
                    elif self.vel_x < 0:
                        self.rect.left = plat.right
                    self.pos_x = float(self.rect.x)
                
        # Y Collisions
        self.pos_y += self.vel_y
        self.rect.y = int(self.pos_y)
        self.is_grounded = False
        
        for plat in self.platforms:
            if self.rect.colliderect(plat):
                self.collision_state = True
                if self.vel_y > 0:
                    self.rect.bottom = plat.top
                    self.is_grounded = True
                    self.vel_y = 0.0
                elif self.vel_y < 0:
                    self.rect.top = plat.bottom
                    self.vel_y = 0.0
                self.pos_y = float(self.rect.y)
                
        # Infinite Fall Reset Map Traversal Logic 
        if self.pos_y > 4500:
            # Teleport to middle area to allow agent to test the remaining glitches
            self.pos_x = 350.0
            self.pos_y = 100.0
            self.vel_y = 0.0
            self.vel_x = 0.0
                
        # 4. Log state
        self.telemetry.log_frame(
            self.frame_id, self.pos_x, self.pos_y, 
            self.vel_x, self.vel_y, self.is_grounded, 
            active_input, self.collision_state
        )
        
        # 5. Render if not headless
        if not self.headless:
            self.screen.fill((30, 30, 30))
            for plat in self.platforms:
                pygame.draw.rect(self.screen, (100, 100, 100), plat)
                
            pygame.draw.rect(self.screen, (200, 50, 50), self.rect)
            
            pygame.display.flip()
            self.clock.tick(60)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    
        self.frame_id += 1
        
        # End simulation after sufficient frames (2 minutes = 7200 frames)
        if self.frame_id > 7200:
            self.running = False

    def run(self):
        while self.running:
            self.step()
        self.telemetry.close()
        if not self.headless:
            pygame.quit()
