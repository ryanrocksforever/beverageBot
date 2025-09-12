#!/usr/bin/env python3
"""
BevBot Control Center - Main Launch Script
Production-ready robot control system
"""

import sys
import os
from pathlib import Path

# Get the absolute paths
root_dir = Path(__file__).parent.parent.absolute()
src_dir = root_dir / 'src'
core_dir = Path(__file__).parent / 'core'
gui_dir = Path(__file__).parent / 'gui'

# Add necessary paths
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(core_dir))
sys.path.insert(0, str(gui_dir))

print(f"Python path configured:")
print(f"  Source: {src_dir}")
print(f"  Core: {core_dir}")
print(f"  GUI: {gui_dir}")

def main():
    """Main entry point."""
    try:
        # Check for required dependencies
        import tkinter
        print("[OK] Tkinter available")
    except ImportError:
        print("[ERROR] Tkinter not found. Please install python3-tk")
        return 1
    
    try:
        import cv2
        print("[OK] OpenCV available")
    except ImportError:
        print("[WARNING] OpenCV not found. Vision features will be disabled")
    
    try:
        import numpy
        print("[OK] NumPy available")
    except ImportError:
        print("[ERROR] NumPy not found. Please install numpy")
        return 1
    
    try:
        from PIL import Image
        print("[OK] PIL available")
    except ImportError:
        print("[ERROR] PIL not found. Please install pillow")
        return 1
    
    # Check hardware availability
    try:
        from gpiozero import Device
        print("[OK] Hardware interface available")
        mode = "Hardware"
    except ImportError:
        print("[WARNING] Hardware interface not available. Running in simulation mode")
        mode = "Simulation"
    
    print(f"\n>>> BevBot Control Center")
    print(f"Mode: {mode}")
    print("-" * 40)
    
    # Launch the application
    from bevbot_control_center import main as launch_gui
    return launch_gui()

if __name__ == "__main__":
    sys.exit(main() or 0)