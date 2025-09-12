#!/usr/bin/env python3
"""
Quick test script to verify the GUI launches
"""

import sys
from pathlib import Path

# Setup paths
root_dir = Path(__file__).parent.parent.absolute()
src_dir = root_dir / 'src'
gui_dir = Path(__file__).parent / 'gui'

sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(gui_dir))

print("Testing BevBot Control Center...")
print(f"Source path: {src_dir}")
print(f"GUI path: {gui_dir}")

# Test imports
try:
    print("\nTesting module imports:")
    
    # Test hardware detection
    try:
        from gpiozero import Device
        print("  [OK] Hardware modules available")
        hardware_mode = True
    except ImportError:
        print("  [INFO] Hardware modules not available - will run in simulation")
        hardware_mode = False
    
    # Test vision modules
    try:
        from camera import CameraInterface
        print("  [OK] Camera module available")
        vision_available = True
    except ImportError:
        print("  [INFO] Camera module not available")
        vision_available = False
    
    # Test GUI
    import tkinter as tk
    from bevbot_control_center import BevBotControlCenter
    print("  [OK] GUI modules loaded")
    
    print(f"\nSystem Configuration:")
    print(f"  Hardware Mode: {hardware_mode}")
    print(f"  Vision Available: {vision_available}")
    print(f"  Mode: {'Hardware' if hardware_mode else 'Simulation'}")
    
    print("\nGUI is ready to launch!")
    print("Use 'python production/launch.py' to start the full application")
    
except Exception as e:
    print(f"\n[ERROR] Failed to load modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)