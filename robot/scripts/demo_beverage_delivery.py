#!/usr/bin/env python3
"""Demo program showing complete beverage delivery workflow using ArUco navigation."""

import sys
import time
import logging

# Add parent directory to path
sys.path.append('..')

from src.aruco_navigation import ArUcoNavigator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define marker IDs for stations
MARKER_HOME = 0
MARKER_PICKUP = 1
MARKER_DELIVERY_A = 2
MARKER_DELIVERY_B = 3
MARKER_CHARGING = 4

def run_delivery_cycle(navigator: ArUcoNavigator):
    """Run a complete delivery cycle."""
    
    logger.info("=== Starting Beverage Delivery Cycle ===")
    
    # Step 1: Navigate to pickup station
    logger.info("Step 1: Going to pickup station")
    if not navigator.navigate_to_marker(MARKER_PICKUP, timeout=30):
        logger.error("Failed to reach pickup station")
        return False
    
    logger.info("Reached pickup station - waiting for beverage placement")
    time.sleep(3)  # Simulate beverage being placed
    
    # Step 2: Navigate to first delivery point
    logger.info("Step 2: Delivering to point A")
    if not navigator.navigate_to_marker(MARKER_DELIVERY_A, timeout=30):
        logger.error("Failed to reach delivery point A")
        return False
    
    logger.info("Reached delivery point A - beverage delivered")
    time.sleep(2)  # Simulate delivery
    
    # Step 3: Return to pickup for next beverage
    logger.info("Step 3: Returning to pickup station")
    if not navigator.navigate_to_marker(MARKER_PICKUP, timeout=30):
        logger.error("Failed to return to pickup station")
        return False
    
    logger.info("Back at pickup station - loading next beverage")
    time.sleep(3)
    
    # Step 4: Navigate to second delivery point
    logger.info("Step 4: Delivering to point B")
    if not navigator.navigate_to_marker(MARKER_DELIVERY_B, timeout=30):
        logger.error("Failed to reach delivery point B")
        return False
    
    logger.info("Reached delivery point B - beverage delivered")
    time.sleep(2)
    
    # Step 5: Return home
    logger.info("Step 5: Returning to home position")
    if not navigator.navigate_to_marker(MARKER_HOME, timeout=30):
        logger.error("Failed to return home")
        return False
    
    logger.info("=== Delivery Cycle Complete ===")
    return True

def setup_demo_positions(navigator: ArUcoNavigator):
    """Interactive setup for demo positions."""
    
    print("\n=== Demo Setup Wizard ===")
    print("This will help you set up the marker positions for the demo.")
    print("\nYou'll need 5 ArUco markers:")
    print(f"  Marker {MARKER_HOME}: Home position")
    print(f"  Marker {MARKER_PICKUP}: Pickup station")
    print(f"  Marker {MARKER_DELIVERY_A}: Delivery point A")
    print(f"  Marker {MARKER_DELIVERY_B}: Delivery point B")
    print(f"  Marker {MARKER_CHARGING}: Charging station (optional)")
    print()
    
    positions_to_setup = [
        (MARKER_HOME, "Home Position"),
        (MARKER_PICKUP, "Pickup Station"),
        (MARKER_DELIVERY_A, "Delivery Point A"),
        (MARKER_DELIVERY_B, "Delivery Point B"),
        (MARKER_CHARGING, "Charging Station")
    ]
    
    for marker_id, name in positions_to_setup:
        print(f"\n--- Setting up {name} (Marker {marker_id}) ---")
        print(f"1. Place marker {marker_id} at the {name} location")
        print(f"2. Position the robot EXACTLY where it should stop")
        print(f"3. Make sure marker {marker_id} is clearly visible to the camera")
        
        input("Press Enter when ready to save position...")
        
        if navigator.save_current_position(marker_id, name, 
                                          tolerance_x=8, 
                                          tolerance_y=8, 
                                          tolerance_size=5):
            print(f"✓ Position saved for {name}")
        else:
            print(f"✗ Failed to save position for {name}")
            print("Make sure the marker is visible and try again")
            return False
    
    print("\n✓ All positions saved successfully!")
    print("The demo is now ready to run.")
    return True

def main():
    """Main demo program."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Beverage delivery demo using ArUco navigation')
    parser.add_argument('--setup', action='store_true',
                       help='Run setup wizard to configure marker positions')
    parser.add_argument('--cycles', type=int, default=1,
                       help='Number of delivery cycles to run (default: 1)')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously until interrupted')
    
    args = parser.parse_args()
    
    # Initialize navigator
    print("Initializing BevBot navigation system...")
    navigator = ArUcoNavigator()
    
    if not navigator.init_camera():
        print("Failed to initialize camera")
        return 1
    
    try:
        if args.setup:
            # Run setup wizard
            if not setup_demo_positions(navigator):
                print("Setup failed")
                return 1
        else:
            # Check if positions are configured
            required_markers = [MARKER_HOME, MARKER_PICKUP, 
                              MARKER_DELIVERY_A, MARKER_DELIVERY_B]
            
            missing = [m for m in required_markers 
                      if m not in navigator.saved_positions]
            
            if missing:
                print(f"Missing positions for markers: {missing}")
                print("Run with --setup to configure positions")
                return 1
            
            # Run delivery cycles
            if args.continuous:
                print("Running continuous delivery mode (Ctrl+C to stop)")
                cycle_count = 0
                while True:
                    cycle_count += 1
                    print(f"\n=== Cycle {cycle_count} ===")
                    if not run_delivery_cycle(navigator):
                        print("Delivery cycle failed")
                        break
                    print(f"Completed {cycle_count} cycles")
                    time.sleep(5)  # Pause between cycles
            else:
                for i in range(args.cycles):
                    if args.cycles > 1:
                        print(f"\n=== Cycle {i+1}/{args.cycles} ===")
                    if not run_delivery_cycle(navigator):
                        print("Delivery cycle failed")
                        break
                    if i < args.cycles - 1:
                        time.sleep(5)  # Pause between cycles
        
        print("\nDemo completed successfully!")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    finally:
        navigator.cleanup()
    
    return 0

if __name__ == "__main__":
    exit(main())