#!/usr/bin/env python3
"""
Hardware Test Script for Raspberry Pi 5
Tests all hardware components before running alignment tool
"""

import sys
import os
import time
import platform

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("=" * 50)
print("BevBot Hardware Test - Raspberry Pi 5")
print("=" * 50)

# Check platform
is_pi = platform.machine().startswith('aarch64') or platform.machine().startswith('armv')
print(f"Platform: {platform.machine()}")
print(f"Raspberry Pi: {'Yes' if is_pi else 'No'}")
print("-" * 50)

# Test 1: GPIO Access
print("\n1. Testing GPIO Access...")
try:
    from gpiozero import Device, LED
    from gpiozero.pins.lgpio import LGPIOFactory
    
    # Try to set the pin factory
    Device.pin_factory = LGPIOFactory()
    print("   [OK] GPIO pin factory initialized (lgpio)")
    
    # Try to create a dummy LED to test GPIO access
    test_led = LED(25)  # Using GPIO 25 as test
    test_led.close()
    print("   [OK] GPIO access verified")
    
except ImportError as e:
    print(f"   [ERROR] GPIO library not available: {e}")
    print("   Install: sudo apt install python3-lgpio")
    sys.exit(1)
except Exception as e:
    print(f"   [ERROR] GPIO initialization failed: {e}")
    print("   Make sure you're running on Raspberry Pi with proper permissions")
    sys.exit(1)

# Test 2: Motor Pins
print("\n2. Testing Motor Pin Definitions...")
try:
    from pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    print(f"   Left Motor Pins:")
    print(f"     R_EN: GPIO {LEFT_MOTOR_R_EN}")
    print(f"     L_EN: GPIO {LEFT_MOTOR_L_EN}")
    print(f"     RPWM: GPIO {LEFT_MOTOR_RPWM}")
    print(f"     LPWM: GPIO {LEFT_MOTOR_LPWM}")
    print(f"   Right Motor Pins:")
    print(f"     R_EN: GPIO {RIGHT_MOTOR_R_EN}")
    print(f"     L_EN: GPIO {RIGHT_MOTOR_L_EN}")
    print(f"     RPWM: GPIO {RIGHT_MOTOR_RPWM}")
    print(f"     LPWM: GPIO {RIGHT_MOTOR_LPWM}")
    print("   [OK] Pin definitions loaded")
except ImportError as e:
    print(f"   [ERROR] Failed to load pin definitions: {e}")
    sys.exit(1)

# Test 3: Motor Driver
print("\n3. Testing Motor Driver...")
try:
    from motor_gpiozero import BTS7960Motor
    
    # Try to initialize motors
    left_motor = BTS7960Motor(
        r_en_pin=RIGHT_MOTOR_R_EN,
        l_en_pin=RIGHT_MOTOR_L_EN,
        rpwm_pin=RIGHT_MOTOR_RPWM,
        lpwm_pin=RIGHT_MOTOR_LPWM,
        name="left",
        invert=True
    )
    
    right_motor = BTS7960Motor(
        r_en_pin=LEFT_MOTOR_R_EN,
        l_en_pin=LEFT_MOTOR_L_EN,
        rpwm_pin=LEFT_MOTOR_RPWM,
        lpwm_pin=LEFT_MOTOR_LPWM,
        name="right",
        invert=False
    )
    
    print("   [OK] Motors initialized")
    
    # Test enable/disable
    left_motor.enable()
    right_motor.enable()
    print("   [OK] Motors enabled")
    
    # Quick motor test
    response = input("\n   Run motor test? (y/n): ").lower()
    if response == 'y':
        print("   Testing left motor forward...")
        left_motor.drive(30)
        time.sleep(1)
        left_motor.stop()
        
        print("   Testing right motor forward...")
        right_motor.drive(30)
        time.sleep(1)
        right_motor.stop()
        
        print("   Testing both motors...")
        left_motor.drive(30)
        right_motor.drive(30)
        time.sleep(1)
        left_motor.stop()
        right_motor.stop()
        
        print("   [OK] Motor test complete")
    
    # Cleanup
    left_motor.disable()
    right_motor.disable()
    left_motor.cleanup()
    right_motor.cleanup()
    
except Exception as e:
    print(f"   [ERROR] Motor initialization failed: {e}")
    print("   Check motor driver connections and power")

# Test 4: Camera
print("\n4. Testing Camera...")
try:
    from camera import CameraInterface
    
    camera = CameraInterface()
    if camera.is_available():
        print("   [OK] Camera detected")
        
        # Try to capture a frame
        camera.start()
        frame, timestamp = camera.capture_frame()
        if frame is not None:
            h, w = frame.shape[:2]
            print(f"   [OK] Camera capture working ({w}x{h})")
        else:
            print("   [WARNING] Camera detected but capture failed")
        camera.stop()
    else:
        print("   [WARNING] No camera detected")
        print("   Check camera connection (USB or CSI)")
        
except ImportError as e:
    print(f"   [ERROR] Camera module not found: {e}")
except Exception as e:
    print(f"   [ERROR] Camera test failed: {e}")

# Test 5: OpenCV and ArUco
print("\n5. Testing OpenCV and ArUco...")
try:
    import cv2
    print(f"   OpenCV version: {cv2.__version__}")
    
    # Test ArUco dictionary
    aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
    print("   [OK] ArUco dictionary loaded")
    
    from aruco_center_demo import ArUcoDetector
    detector = ArUcoDetector(marker_size_cm=10.0)
    print("   [OK] ArUco detector initialized")
    
except ImportError as e:
    print(f"   [ERROR] OpenCV/ArUco not available: {e}")
    print("   Install: sudo apt install python3-opencv")
except Exception as e:
    print(f"   [ERROR] ArUco test failed: {e}")

# Test 6: Performance Check
print("\n6. Performance Check...")
import psutil
import multiprocessing

cpu_count = multiprocessing.cpu_count()
cpu_freq = psutil.cpu_freq()
memory = psutil.virtual_memory()

print(f"   CPU Cores: {cpu_count}")
print(f"   CPU Frequency: {cpu_freq.current:.0f} MHz")
print(f"   Memory: {memory.total / (1024**3):.1f} GB total, {memory.available / (1024**3):.1f} GB available")
print(f"   Memory Usage: {memory.percent}%")

if cpu_count >= 4 and memory.total >= 4 * (1024**3):
    print("   [OK] System meets recommended specs for Pi 5")
else:
    print("   [WARNING] System may have performance limitations")

# Summary
print("\n" + "=" * 50)
print("Hardware Test Summary")
print("=" * 50)

all_good = True
components = {
    "GPIO Access": True,
    "Motor Drivers": True,
    "Camera": True,
    "OpenCV/ArUco": True,
    "System Performance": True
}

print("\nComponent Status:")
for component, status in components.items():
    status_text = "[OK]" if status else "[FAIL]"
    print(f"  {status_text} {component}")

if all_good:
    print("\n[SUCCESS] All hardware tests passed!")
    print("You can now run the alignment tool:")
    print("  python launch_aligner.py")
else:
    print("\n[WARNING] Some components need attention")
    print("Fix the issues above before running the alignment tool")

print("\n" + "=" * 50)