import sys
from core.engine import Engine

if __name__ == "__main__":
    # Check if we should run in headless mode
    headless = "--headless" in sys.argv
    print(f"Starting IndieQA Simulation Engine... (Headless: {headless})")
    
    # Initialize and run the simulation
    engine = Engine(headless=headless)
    engine.run()
    
    print("Simulation complete. Telemetry saved to data/logs/telemetry.csv")
