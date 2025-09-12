#!/usr/bin/env python3
"""
Launch script for BevBot Remote Control GUI
Uses the original working remote control interface
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("BevBot Remote Control Launcher")
print("-" * 40)

# Check dependencies
try:
    import cv2
    print("[OK] OpenCV available")
except ImportError:
    print("[WARNING] OpenCV not available - camera features disabled")

try:
    import numpy
    print("[OK] NumPy available")
except ImportError:
    print("[ERROR] NumPy required. Please install: pip install numpy")
    sys.exit(1)

try:
    from PIL import Image
    print("[OK] PIL available")
except ImportError:
    print("[ERROR] PIL required. Please install: pip install pillow")
    sys.exit(1)

try:
    import tkinter
    print("[OK] Tkinter available")
except ImportError:
    print("[ERROR] Tkinter required. Please install python3-tk")
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
print("Starting Remote Control GUI...\n")

# Launch the remote control GUI
from remote_control_gui import main

if __name__ == "__main__":
    main()