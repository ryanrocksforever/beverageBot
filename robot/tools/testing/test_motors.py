#!/usr/bin/env python3
"""
Motor Testing Tool
Tests motor functionality and calibration
"""

import sys
import os
import time
import argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    from motor_gpiozero import BTS7960Motor
    from pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Hardware not available - simulation mode only")

def test_motor(motor, name, duration=2):
    """Test a single motor."""
    print(f"\nTesting {name} motor:")
    
    # Forward test
    print(f"  Forward at 50% for {duration}s...")
    motor.drive(50)
    time.sleep(duration)
    motor.stop()
    time.sleep(0.5)
    
    # Backward test
    print(f"  Backward at 50% for {duration}s...")
    motor.drive(-50)
    time.sleep(duration)
    motor.stop()
    time.sleep(0.5)
    
    # Speed ramp test
    print("  Speed ramp test...")
    for speed in range(0, 101, 10):
        motor.drive(speed)
        time.sleep(0.2)
    for speed in range(100, -1, -10):
        motor.drive(speed)
        time.sleep(0.2)
    motor.stop()
    
    print(f"  {name} motor test complete")

def test_both_motors(left_motor, right_motor):
    """Test both motors together."""
    print("\nTesting both motors together:")
    
    # Forward
    print("  Both forward...")
    left_motor.drive(50)
    right_motor.drive(50)
    time.sleep(2)
    
    # Backward
    print("  Both backward...")
    left_motor.drive(-50)
    right_motor.drive(-50)
    time.sleep(2)
    
    # Turn left
    print("  Turn left...")
    left_motor.drive(-30)
    right_motor.drive(30)
    time.sleep(2)
    
    # Turn right
    print("  Turn right...")
    left_motor.drive(30)
    right_motor.drive(-30)
    time.sleep(2)
    
    # Stop
    left_motor.stop()
    right_motor.stop()
    print("  Both motors test complete")

def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description='Motor Testing Tool')
    parser.add_argument('--left', action='store_true', help='Test left motor only')
    parser.add_argument('--right', action='store_true', help='Test right motor only')
    parser.add_argument('--both', action='store_true', help='Test both motors')
    parser.add_argument('--duration', type=float, default=2.0, help='Test duration in seconds')
    parser.add_argument('--interactive', action='store_true', help='Interactive control mode')
    
    args = parser.parse_args()
    
    if not HARDWARE_AVAILABLE:
        print("Hardware not available. Cannot run motor tests.")
        return 1
    
    # Initialize motors
    try:
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
        
        left_motor.enable()
        right_motor.enable()
        
        print("Motors initialized successfully")
        
    except Exception as e:
        print(f"Failed to initialize motors: {e}")
        return 1
    
    try:
        if args.interactive:
            print("\nInteractive Motor Control")
            print("Commands: w/s = forward/backward, a/d = left/right, q = quit")
            print("Speed: 1-9 = 10%-90%, 0 = stop")
            
            current_speed = 30
            
            while True:
                cmd = input("> ").lower()
                
                if cmd == 'q':
                    break
                elif cmd == 'w':
                    left_motor.drive(current_speed)
                    right_motor.drive(current_speed)
                elif cmd == 's':
                    left_motor.drive(-current_speed)
                    right_motor.drive(-current_speed)
                elif cmd == 'a':
                    left_motor.drive(-current_speed)
                    right_motor.drive(current_speed)
                elif cmd == 'd':
                    left_motor.drive(current_speed)
                    right_motor.drive(-current_speed)
                elif cmd == '0':
                    left_motor.stop()
                    right_motor.stop()
                elif cmd.isdigit() and 1 <= int(cmd) <= 9:
                    current_speed = int(cmd) * 10
                    print(f"Speed set to {current_speed}%")
                else:
                    print("Unknown command")
                    
        else:
            # Run tests based on arguments
            if args.left or not (args.right or args.both):
                test_motor(left_motor, "Left", args.duration)
            
            if args.right or not (args.left or args.both):
                test_motor(right_motor, "Right", args.duration)
            
            if args.both or not (args.left or args.right):
                test_both_motors(left_motor, right_motor)
        
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        # Cleanup
        left_motor.stop()
        right_motor.stop()
        left_motor.disable()
        right_motor.disable()
        left_motor.cleanup()
        right_motor.cleanup()
        print("Motors cleaned up")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())