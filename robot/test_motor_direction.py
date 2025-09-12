#!/usr/bin/env python3
"""
Test script to verify motor directions
Helps ensure forward/backward are correct
"""

import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

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
    print("Hardware not available")
    sys.exit(1)

def test_motors():
    """Test motor directions."""
    print("Motor Direction Test")
    print("=" * 40)
    print("This will test each motor direction")
    print("Observe which way the robot moves")
    print("-" * 40)
    
    # Initialize motors as per remote_control_gui.py
    print("\nInitializing motors...")
    print("LEFT motor uses RIGHT_MOTOR pins (inverted)")
    print("RIGHT motor uses LEFT_MOTOR pins (not inverted)")
    
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
    
    try:
        # Test 1: Both motors forward
        print("\nTest 1: FORWARD (both motors +30)")
        print("Expected: Robot moves FORWARD")
        left_motor.drive(30)
        right_motor.drive(30)
        time.sleep(2)
        left_motor.stop()
        right_motor.stop()
        
        response = input("Did robot move FORWARD? (y/n): ")
        forward_correct = response.lower() == 'y'
        
        time.sleep(1)
        
        # Test 2: Both motors backward
        print("\nTest 2: BACKWARD (both motors -30)")
        print("Expected: Robot moves BACKWARD")
        left_motor.drive(-30)
        right_motor.drive(-30)
        time.sleep(2)
        left_motor.stop()
        right_motor.stop()
        
        response = input("Did robot move BACKWARD? (y/n): ")
        backward_correct = response.lower() == 'y'
        
        time.sleep(1)
        
        # Test 3: Turn left
        print("\nTest 3: TURN LEFT (left -30, right +30)")
        print("Expected: Robot turns LEFT")
        left_motor.drive(-30)
        right_motor.drive(30)
        time.sleep(2)
        left_motor.stop()
        right_motor.stop()
        
        response = input("Did robot turn LEFT? (y/n): ")
        left_correct = response.lower() == 'y'
        
        time.sleep(1)
        
        # Test 4: Turn right
        print("\nTest 4: TURN RIGHT (left +30, right -30)")
        print("Expected: Robot turns RIGHT")
        left_motor.drive(30)
        right_motor.drive(-30)
        time.sleep(2)
        left_motor.stop()
        right_motor.stop()
        
        response = input("Did robot turn RIGHT? (y/n): ")
        right_correct = response.lower() == 'y'
        
        # Results
        print("\n" + "=" * 40)
        print("Test Results:")
        print(f"  Forward:  {'✓' if forward_correct else '✗'}")
        print(f"  Backward: {'✓' if backward_correct else '✗'}")
        print(f"  Left:     {'✓' if left_correct else '✗'}")
        print(f"  Right:    {'✓' if right_correct else '✗'}")
        
        if not forward_correct or not backward_correct:
            print("\nDIRECTION ISSUE DETECTED!")
            print("Motors may need to be inverted or swapped")
            
            if not forward_correct and not backward_correct:
                print("Suggestion: Swap motor wires or invert both motors")
            elif not forward_correct:
                print("Suggestion: Forward/backward are reversed")
                print("Fix: Negate all forward/backward speeds in alignment")
        
        if not left_correct or not right_correct:
            print("\nTURNING ISSUE DETECTED!")
            print("Left/right may be swapped")
        
        if all([forward_correct, backward_correct, left_correct, right_correct]):
            print("\n✓ All motor directions are correct!")
            
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        left_motor.disable()
        right_motor.disable()
        left_motor.cleanup()
        right_motor.cleanup()
        print("\nMotors cleaned up")

if __name__ == "__main__":
    test_motors()