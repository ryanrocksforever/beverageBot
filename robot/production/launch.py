#!/usr/bin/env python3
"""
BevBot Control Center - Main Launch Script
Production-ready robot control system
"""

import sys
import os
from pathlib import Path

# Add necessary paths
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'core'))
sys.path.insert(0, str(Path(__file__).parent / 'gui'))

def main():
    """Main entry point."""
    try:
        # Check for required dependencies
        import tkinter
        print("✓ Tkinter available")
    except ImportError:
        print("✗ Tkinter not found. Please install python3-tk")
        return 1
    
    try:
        import cv2
        print("✓ OpenCV available")
    except ImportError:
        print("⚠ OpenCV not found. Vision features will be disabled")
    
    try:
        import numpy
        print("✓ NumPy available")
    except ImportError:
        print("✗ NumPy not found. Please install numpy")
        return 1
    
    try:
        from PIL import Image
        print("✓ PIL available")
    except ImportError:
        print("✗ PIL not found. Please install pillow")
        return 1
    
    # Check hardware availability
    try:
        from gpiozero import Device
        print("✓ Hardware interface available")
        mode = "Hardware"
    except ImportError:
        print("⚠ Hardware interface not available. Running in simulation mode")
        mode = "Simulation"
    
    print(f"\n🤖 BevBot Control Center")
    print(f"Mode: {mode}")
    print("-" * 40)
    
    # Launch the application
    from bevbot_control_center import main as launch_gui
    return launch_gui()

if __name__ == "__main__":
    sys.exit(main() or 0)