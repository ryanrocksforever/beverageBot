#!/usr/bin/env python3
"""
Launch script for ArUco Precision Alignment Tool
Dedicated tool for precise marker alignment
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("ArUco Precision Alignment Tool")
print("=" * 40)
print("A robust system for precise robot alignment with ArUco markers")
print("-" * 40)

# Check dependencies
try:
    import cv2
    print("[OK] OpenCV available")
except ImportError:
    print("[ERROR] OpenCV required for marker detection")
    print("Install: pip install opencv-python")
    sys.exit(1)

try:
    import numpy
    print("[OK] NumPy available")
except ImportError:
    print("[ERROR] NumPy required")
    print("Install: pip install numpy")
    sys.exit(1)

try:
    from PIL import Image
    print("[OK] PIL available")
except ImportError:
    print("[ERROR] PIL required for GUI")
    print("Install: pip install pillow")
    sys.exit(1)

try:
    import tkinter
    print("[OK] Tkinter available")
except ImportError:
    print("[ERROR] Tkinter required for GUI")
    print("Install: python3-tk")
    sys.exit(1)

# Check hardware
try:
    from gpiozero import Device
    print("[OK] Hardware interface available")
    mode = "Hardware"
except ImportError:
    print("[INFO] Hardware not available - simulation mode")
    mode = "Simulation"

print(f"\nMode: {mode}")
print("-" * 40)

# Import the aligner
from aruco_precision_aligner import main, AlignmentGUI, RobustAligner

def launch_gui():
    """Launch the alignment GUI."""
    import tkinter as tk
    
    print("\nLaunching Alignment GUI...")
    print("\nFeatures:")
    print("  - PID-controlled precision alignment")
    print("  - Visual feedback with camera feed")
    print("  - Save/load alignment positions")
    print("  - Coarse and fine alignment modes")
    print("  - Real-time error displays")
    print("  - Emergency stop button")
    print("\n")
    
    root = tk.Tk()
    app = AlignmentGUI(root)
    root.mainloop()

def launch_cli():
    """Launch command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ArUco Precision Alignment Tool')
    parser.add_argument('--align', type=int, help='Align with marker ID')
    parser.add_argument('--distance', type=float, default=30.0, help='Target distance (cm)')
    parser.add_argument('--save', type=int, help='Save current position for marker ID')
    parser.add_argument('--list', action='store_true', help='List saved positions')
    
    args = parser.parse_args()
    
    if args.list:
        # List saved positions
        import json
        try:
            with open('alignment_targets.json', 'r') as f:
                targets = json.load(f)
                print("\nSaved Alignment Positions:")
                print("-" * 40)
                for marker_id, target in targets.items():
                    print(f"Marker {marker_id}: {target.get('name', 'Unnamed')}")
                    print(f"  Distance: {target['target_distance_cm']:.1f} cm")
                    print(f"  X Position: {target['target_x_ratio']:.2f}")
                    print()
        except FileNotFoundError:
            print("No saved positions found")
            
    elif args.align is not None:
        # Align with marker
        aligner = RobustAligner(simulation_mode=(mode == "Simulation"))
        
        if not aligner.init_camera():
            print("[ERROR] Failed to initialize camera")
            return 1
            
        print(f"\nAligning with marker {args.align}")
        print(f"Target distance: {args.distance} cm")
        print("Press Ctrl+C to stop\n")
        
        from aruco_precision_aligner import AlignmentTarget
        
        # Try to load saved position
        target = aligner.load_alignment_target(args.align)
        if not target:
            # Create new target
            target = AlignmentTarget(
                marker_id=args.align,
                name=f"Marker_{args.align}",
                target_x_ratio=0.5,
                target_y_ratio=0.5,
                target_distance_cm=args.distance
            )
            
        try:
            success = aligner.align_with_marker(target)
            if success:
                print("\n[SUCCESS] Alignment complete!")
            else:
                print("\n[FAILED] Alignment failed")
        except KeyboardInterrupt:
            print("\n[STOPPED] Alignment interrupted")
        finally:
            aligner.cleanup()
            
    elif args.save is not None:
        # Save current position
        aligner = RobustAligner(simulation_mode=(mode == "Simulation"))
        
        if not aligner.init_camera():
            print("[ERROR] Failed to initialize camera")
            return 1
            
        print(f"\nPosition robot at desired location relative to marker {args.save}")
        input("Press Enter when ready to save position...")
        
        target = aligner.save_alignment_position(args.save)
        if target:
            print(f"[SUCCESS] Saved position for marker {args.save}")
        else:
            print("[ERROR] Failed to save position - no marker visible")
            
        aligner.cleanup()
        
    else:
        # No arguments, launch GUI
        launch_gui()
        
    return 0

if __name__ == "__main__":
    # Check if any command line arguments provided
    if len(sys.argv) > 1:
        sys.exit(launch_cli())
    else:
        # No arguments, launch GUI
        print("\nNo arguments provided, launching GUI mode...")
        print("For command line options, use --help\n")
        launch_gui()