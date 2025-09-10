#!/usr/bin/env python3
"""Test program for right motor only - runs continuously until stopped."""

import time
import logging
import signal
import sys
from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

from .pins import RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
from .motor_gpiozero import BTS7960Motor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use lgpio for Raspberry Pi 5 compatibility
Device.pin_factory = LGPIOFactory()

class RightMotorTest:
    """Continuous test for right motor only."""
    
    def __init__(self):
        """Initialize right motor test."""
        self.motor = None
        self._running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("\nShutdown signal received, stopping motor...")
        self._running = False
        
    def run_continuous_test(self):
        """Run continuous motor test with varying speeds."""
        try:
            logger.info("=== Right Motor Continuous Test ===")
            logger.info("Press Ctrl+C to stop")
            
            # Initialize right motor
            self.motor = BTS7960Motor(
                r_en_pin=RIGHT_MOTOR_R_EN,
                l_en_pin=RIGHT_MOTOR_L_EN,
                rpwm_pin=RIGHT_MOTOR_RPWM,
                lpwm_pin=RIGHT_MOTOR_LPWM,
                name="right",
                invert=True  # Right motor inverted
            )
            
            # Enable motor
            self.motor.enable()
            logger.info("Right motor enabled")
            
            while self._running:
                # Forward slow
                logger.info("Forward 25% speed")
                self.motor.drive(25)
                time.sleep(3)
                if not self._running:
                    break
                    
                # Forward medium
                logger.info("Forward 50% speed")
                self.motor.drive(50)
                time.sleep(3)
                if not self._running:
                    break
                    
                # Forward fast
                logger.info("Forward 75% speed")
                self.motor.drive(75)
                time.sleep(3)
                if not self._running:
                    break
                    
                # Brake
                logger.info("Braking")
                self.motor.brake()
                time.sleep(2)
                if not self._running:
                    break
                    
                # Reverse slow
                logger.info("Reverse 25% speed")
                self.motor.drive(-25)
                time.sleep(3)
                if not self._running:
                    break
                    
                # Reverse medium
                logger.info("Reverse 50% speed")
                self.motor.drive(-50)
                time.sleep(3)
                if not self._running:
                    break
                    
                # Stop (coast)
                logger.info("Stopping (coast)")
                self.motor.stop()
                time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def run_simple_test(self, speed: float = 30, direction: str = "forward"):
        """Run simple continuous test at fixed speed.
        
        Args:
            speed: Motor speed percentage (0-100)
            direction: "forward" or "reverse"
        """
        try:
            logger.info(f"=== Right Motor Simple Test ===")
            logger.info(f"Running at {speed}% speed in {direction} direction")
            logger.info("Press Ctrl+C to stop")
            
            # Initialize right motor
            self.motor = BTS7960Motor(
                r_en_pin=RIGHT_MOTOR_R_EN,
                l_en_pin=RIGHT_MOTOR_L_EN,
                rpwm_pin=RIGHT_MOTOR_RPWM,
                lpwm_pin=RIGHT_MOTOR_LPWM,
                name="right",
                invert=True  # Right motor inverted
            )
            
            # Enable motor
            self.motor.enable()
            logger.info("Right motor enabled")
            
            # Set motor speed
            if direction.lower() == "reverse":
                speed = -abs(speed)
            else:
                speed = abs(speed)
                
            self.motor.drive(speed)
            logger.info(f"Motor running at {speed}%")
            
            # Run until interrupted
            while self._running:
                time.sleep(0.1)
                
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
        if self.motor:
            try:
                self.motor.stop()
                self.motor.disable()
                self.motor.cleanup()
                logger.info("Motor stopped and cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test right motor continuously')
    parser.add_argument('--speed', type=float, default=30, 
                        help='Motor speed percentage (0-100, default: 30)')
    parser.add_argument('--direction', choices=['forward', 'reverse'], 
                        default='forward', help='Motor direction (default: forward)')
    parser.add_argument('--mode', choices=['simple', 'cycle'], 
                        default='simple', help='Test mode: simple (fixed speed) or cycle (varying speeds)')
    
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
            
        test = RightMotorTest()
        
        if args.mode == 'cycle':
            test.run_continuous_test()
        else:
            test.run_simple_test(speed=args.speed, direction=args.direction)
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()