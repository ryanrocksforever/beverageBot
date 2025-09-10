#!/usr/bin/env python3
"""Simple program to drive BevBot forward - used to verify motor directions are correct."""

import time
import logging
import signal
import sys
from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

from .pins import (
    LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
    RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
)
from .motor_gpiozero import BTS7960Motor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use lgpio for Raspberry Pi 5 compatibility
Device.pin_factory = LGPIOFactory()

class GoForward:
    """Simple forward driving test for BevBot."""
    
    def __init__(self):
        """Initialize motors."""
        self.left_motor = None
        self.right_motor = None
        self._running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("\nShutdown signal received, stopping motors...")
        self._running = False
        
    def drive_forward(self, speed: float = 30, duration: float = 0):
        """Drive both motors forward at the same speed.
        
        Args:
            speed: Motor speed percentage (0-100)
            duration: How long to drive in seconds (0 = continuous until stopped)
        """
        try:
            logger.info("=== BevBot Go Forward Test ===")
            logger.info(f"Speed: {speed}%")
            if duration > 0:
                logger.info(f"Duration: {duration} seconds")
            else:
                logger.info("Duration: Continuous (press Ctrl+C to stop)")
            logger.info("")
            
            # Initialize motors (both inverted to swap forward/backward)
            logger.info("Initializing left motor...")
            self.left_motor = BTS7960Motor(
                r_en_pin=LEFT_MOTOR_R_EN,
                l_en_pin=LEFT_MOTOR_L_EN,
                rpwm_pin=LEFT_MOTOR_RPWM,
                lpwm_pin=LEFT_MOTOR_LPWM,
                name="left",
                invert=False  # Left motor not inverted
            )
            
            logger.info("Initializing right motor (inverted)...")
            self.right_motor = BTS7960Motor(
                r_en_pin=RIGHT_MOTOR_R_EN,
                l_en_pin=RIGHT_MOTOR_L_EN,
                rpwm_pin=RIGHT_MOTOR_RPWM,
                lpwm_pin=RIGHT_MOTOR_LPWM,
                name="right",
                invert=True  # Right motor inverted
            )
            
            # Enable motors
            self.left_motor.enable()
            self.right_motor.enable()
            logger.info("Motors enabled")
            
            # Start driving forward
            logger.info(f"Driving forward at {speed}%...")
            self.left_motor.drive(speed)
            self.right_motor.drive(speed)
            
            # Run for specified duration or until interrupted
            if duration > 0:
                # Fixed duration
                start_time = time.time()
                while self._running and (time.time() - start_time) < duration:
                    time.sleep(0.1)
            else:
                # Continuous
                while self._running:
                    time.sleep(0.1)
                    
            logger.info("Stopping motors...")
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def test_directions(self):
        """Test each motor individually, then both together."""
        try:
            logger.info("=== Motor Direction Test ===")
            logger.info("This test will help verify motor directions are correct")
            logger.info("")
            
            # Initialize motors (both inverted to swap forward/backward)
            self.left_motor = BTS7960Motor(
                r_en_pin=LEFT_MOTOR_R_EN,
                l_en_pin=LEFT_MOTOR_L_EN,
                rpwm_pin=LEFT_MOTOR_RPWM,
                lpwm_pin=LEFT_MOTOR_LPWM,
                name="left",
                invert=False  # Left motor not inverted
            )
            
            self.right_motor = BTS7960Motor(
                r_en_pin=RIGHT_MOTOR_R_EN,
                l_en_pin=RIGHT_MOTOR_L_EN,
                rpwm_pin=RIGHT_MOTOR_RPWM,
                lpwm_pin=RIGHT_MOTOR_LPWM,
                name="right",
                invert=True  # Right motor inverted
            )
            
            # Enable motors
            self.left_motor.enable()
            self.right_motor.enable()
            
            if self._running:
                logger.info("Testing LEFT motor forward (should rotate forward)...")
                self.left_motor.drive(30)
                self.right_motor.drive(0)
                time.sleep(3)
                
            if self._running:
                logger.info("Testing RIGHT motor forward (should rotate forward)...")
                self.left_motor.drive(0)
                self.right_motor.drive(30)
                time.sleep(3)
                
            if self._running:
                logger.info("Testing BOTH motors forward (robot should go straight)...")
                self.left_motor.drive(30)
                self.right_motor.drive(30)
                time.sleep(3)
                
            if self._running:
                logger.info("Testing turn LEFT (left slow, right fast)...")
                self.left_motor.drive(15)
                self.right_motor.drive(45)
                time.sleep(3)
                
            if self._running:
                logger.info("Testing turn RIGHT (left fast, right slow)...")
                self.left_motor.drive(45)
                self.right_motor.drive(15)
                time.sleep(3)
                
            if self._running:
                logger.info("Testing REVERSE (both motors backward)...")
                self.left_motor.drive(-30)
                self.right_motor.drive(-30)
                time.sleep(3)
                
            logger.info("Direction test complete!")
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up motor resources."""
        logger.info("Cleaning up...")
        
        # Stop and cleanup left motor
        if self.left_motor:
            try:
                self.left_motor.stop()
                self.left_motor.disable()
                self.left_motor.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up left motor: {e}")
                
        # Stop and cleanup right motor
        if self.right_motor:
            try:
                self.right_motor.stop()
                self.right_motor.disable()
                self.right_motor.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up right motor: {e}")
                
        logger.info("Cleanup complete")

def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Drive BevBot forward to test motor directions')
    parser.add_argument('--speed', type=float, default=30, 
                        help='Motor speed percentage (0-100, default: 30)')
    parser.add_argument('--duration', type=float, default=0,
                        help='Duration in seconds (0 = continuous, default: 0)')
    parser.add_argument('--test', action='store_true',
                        help='Run direction test sequence instead of continuous forward')
    
    args = parser.parse_args()
    
    try:
        # Check if running on Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                logger.info(f"Running on: {model.strip()}")
                if 'Raspberry Pi 5' in model:
                    logger.info("Detected Raspberry Pi 5 - using lgpio backend")
        except FileNotFoundError:
            logger.warning("Not running on Raspberry Pi - test may not work")
            
        driver = GoForward()
        
        if args.test:
            driver.test_directions()
        else:
            driver.drive_forward(speed=args.speed, duration=args.duration)
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()