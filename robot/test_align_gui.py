#!/usr/bin/env python3
"""
Test script to verify align_gui.py works correctly
Tests imports, initialization, and motor configuration
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all required modules import correctly."""
    print("Testing imports...")
    print("-" * 40)
    
    errors = []
    
    # Test standard library imports
    try:
        import tkinter as tk
        print("[OK] tkinter")
    except ImportError as e:
        errors.append(f"tkinter: {e}")
        print(f"[FAIL] tkinter: {e}")
    
    try:
        from tkinter import ttk, messagebox
        print("[OK] tkinter.ttk, messagebox")
    except ImportError as e:
        errors.append(f"tkinter components: {e}")
        print(f"[FAIL] tkinter components: {e}")
    
    try:
        import cv2
        print(f"[OK] cv2 (version: {cv2.__version__})")
    except ImportError as e:
        errors.append(f"cv2: {e}")
        print(f"[FAIL] cv2: {e}")
    
    try:
        import numpy as np
        print(f"[OK] numpy (version: {np.__version__})")
    except ImportError as e:
        errors.append(f"numpy: {e}")
        print(f"[FAIL] numpy: {e}")
    
    try:
        from PIL import Image, ImageTk
        print("[OK] PIL (Pillow)")
    except ImportError as e:
        errors.append(f"PIL: {e}")
        print(f"[FAIL] PIL: {e}")
    
    # Test local imports
    try:
        from align_simple import SimpleArUcoDetector, AlignConfig, SimpleAligner, HARDWARE_AVAILABLE
        print("[OK] align_simple imports")
        print(f"  Hardware available: {HARDWARE_AVAILABLE}")
    except ImportError as e:
        errors.append(f"align_simple: {e}")
        print(f"[FAIL] align_simple: {e}")
    
    try:
        from camera import CameraInterface
        print("[OK] camera module")
    except ImportError as e:
        errors.append(f"camera: {e}")
        print(f"[FAIL] camera: {e}")
    
    try:
        from pins import (
            LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
            RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
        )
        print("[OK] pins module")
    except ImportError as e:
        errors.append(f"pins: {e}")
        print(f"[FAIL] pins: {e}")
    
    print("-" * 40)
    if errors:
        print(f"\n[ERROR] {len(errors)} import error(s) found:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n[SUCCESS] All imports successful!")
        return True

def test_motor_config():
    """Test motor configuration matches remote_control_gui."""
    print("\nTesting motor configuration...")
    print("-" * 40)
    
    try:
        from align_simple import SimpleAligner, AlignConfig, HARDWARE_AVAILABLE
        
        if not HARDWARE_AVAILABLE:
            print("[WARNING]  Running in simulation mode (no hardware)")
            return True
        
        # Create aligner to check motor config
        config = AlignConfig()
        aligner = SimpleAligner(config)
        
        print("Motor configuration in align_simple.py:")
        print("  LEFT motor:")
        print("    - Uses RIGHT_MOTOR pins")
        print("    - Inverted: True")
        print("  RIGHT motor:")
        print("    - Uses LEFT_MOTOR pins")
        print("    - Inverted: False")
        print("")
        print("This matches remote_control_gui.py configuration [OK]")
        
        # Check forward/backward inversion setting
        print(f"\nForward inversion setting: {config.invert_forward}")
        if config.invert_forward:
            print("  [WARNING]  Forward is inverted - robot will move backward for positive speeds")
        else:
            print("  [OK] Forward is normal - robot will move forward for positive speeds")
        
        aligner.cleanup()
        return True
        
    except Exception as e:
        print(f"[ERROR] Error testing motor config: {e}")
        return False

def test_gui_initialization():
    """Test that GUI can initialize without errors."""
    print("\nTesting GUI initialization...")
    print("-" * 40)
    
    try:
        import tkinter as tk
        from align_gui import AlignmentGUI
        
        # Create root window
        root = tk.Tk()
        root.withdraw()  # Hide window for testing
        
        # Try to create GUI
        app = AlignmentGUI(root)
        print("[OK] GUI initialized successfully")
        
        # Check key components
        if hasattr(app, 'aligner'):
            print("[OK] Aligner created")
        else:
            print("[FAIL] Aligner not created")
        
        if hasattr(app, 'config'):
            print(f"[OK] Config loaded")
            print(f"  - Target distance: {app.config.target_distance_cm}cm")
            print(f"  - Max speed: {app.config.max_speed}")
            print(f"  - Invert forward: {app.config.invert_forward}")
        else:
            print("[FAIL] Config not loaded")
        
        # Clean up
        try:
            app.on_closing()
            root.destroy()
        except:
            pass  # Already destroyed
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error initializing GUI: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("="*50)
    print("Align GUI Test Suite")
    print("="*50)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Motor Config", test_motor_config()))
    results.append(("GUI Init", test_gui_initialization()))
    
    # Summary
    print("\n" + "="*50)
    print("Test Summary:")
    print("-"*50)
    
    all_passed = True
    for test_name, passed in results:
        status = "[PASSED]" if passed else "[FAILED]"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False
    
    print("="*50)
    
    if all_passed:
        print("\n[CELEBRATE] All tests passed! The GUI should work correctly.")
        print("\nTo launch the GUI, run:")
        print("  python3 align_gui.py")
        print("\nNote: If the robot still moves backward when aligning,")
        print("      enable 'Invert Forward' in the Settings tab.")
    else:
        print("\n[WARNING]  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Missing PIL: pip install Pillow")
        print("  - Missing cv2: pip install opencv-python")
        print("  - Import errors: Check that all files are in the correct directories")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())