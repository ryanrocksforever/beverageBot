#!/usr/bin/env python3
"""
ArUco Marker Calibration Tool
Used for calibrating robot positions relative to ArUco markers
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from aruco_navigation import ArUcoNavigator, CalibrationMode
import argparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main calibration tool."""
    parser = argparse.ArgumentParser(description='ArUco Marker Calibration Tool')
    parser.add_argument('--interactive', action='store_true',
                       help='Run interactive calibration mode')
    parser.add_argument('--save', type=int,
                       help='Save current position for specified marker ID')
    parser.add_argument('--list', action='store_true',
                       help='List all saved marker positions')
    parser.add_argument('--test', type=int,
                       help='Test navigation to specified marker')
    parser.add_argument('--simulation', action='store_true',
                       help='Run in simulation mode')
    
    args = parser.parse_args()
    
    # Initialize navigator
    navigator = ArUcoNavigator(simulation_mode=args.simulation)
    
    if not navigator.init_camera():
        logger.error("Failed to initialize camera")
        return 1
    
    try:
        if args.interactive:
            # Run interactive calibration
            calibrator = CalibrationMode(navigator)
            calibrator.run_interactive()
            
        elif args.save is not None:
            # Save current position
            success = navigator.save_current_position(args.save)
            if success:
                print(f"✓ Saved position for marker {args.save}")
            else:
                print(f"✗ Failed to save position")
                
        elif args.list:
            # List saved positions
            if not navigator.saved_positions:
                print("No saved positions")
            else:
                print("\nSaved Marker Positions:")
                print("-" * 50)
                for marker_id, pos in navigator.saved_positions.items():
                    print(f"Marker {marker_id}: {pos.name}")
                    print(f"  Position: ({pos.target_x:.1f}, {pos.target_y:.1f})")
                    print(f"  Distance: {pos.target_distance:.1f} cm")
                    print(f"  Size: {pos.target_size:.1f} px")
                    print()
                    
        elif args.test is not None:
            # Test navigation
            print(f"Testing navigation to marker {args.test}...")
            success = navigator.navigate_to_marker(args.test)
            if success:
                print("✓ Successfully navigated to marker")
            else:
                print("✗ Navigation failed")
                
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\nCalibration interrupted")
    finally:
        navigator.cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())