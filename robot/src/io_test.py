#!/usr/bin/env python3
"""Hardware IO test for BevBot - tests motors, actuator, camera, and GPIO."""

import time
import logging
import signal
import sys
from typing import Optional
import pigpio

from .pins import BUTTON_PIN, LED_BUZZER_PIN
from .motor import BTS7960, PigpioWrapper
from .actuator import LinearActuator
from .camera import CameraInterface

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IOTest:
    """Hardware IO test suite for BevBot."""
    
    def __init__(self):
        """Initialize test hardware."""
        self.pi: Optional[pigpio.pi] = None
        self.left_motor: Optional[BTS7960] = None
        self.right_motor: Optional[BTS7960] = None
        self.actuator: Optional[LinearActuator] = None
        self.camera: Optional[CameraInterface] = None
        self._running = True
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received, stopping safely...")
        self._running = False
        
    def setup_gpio(self) -> None:
        """Setup GPIO pins for button and LED/buzzer."""
        self.pi = PigpioWrapper.get_instance()
        
        # Setup button with pull-up
        self.pi.set_mode(BUTTON_PIN, pigpio.INPUT)
        self.pi.set_pull_up_down(BUTTON_PIN, pigpio.PUD_UP)
        
        # Setup LED/buzzer as output
        self.pi.set_mode(LED_BUZZER_PIN, pigpio.OUTPUT)
        self.pi.write(LED_BUZZER_PIN, 0)
        
        logger.info("GPIO setup complete")
        
    def is_button_pressed(self) -> bool:
        """Check if button is pressed (active low)."""
        return self.pi.read(BUTTON_PIN) == 0
        
    def set_led_buzzer(self, state: bool) -> None:
        """Set LED/buzzer state."""
        self.pi.write(LED_BUZZER_PIN, 1 if state else 0)
        
    def test_led_buzzer(self) -> None:
        """Test LED/buzzer with blinking pattern."""
        logger.info("Testing LED/Buzzer - 5 blinks")
        for i in range(5):
            if not self._running:
                return
            self.set_led_buzzer(True)
            time.sleep(0.2)
            self.set_led_buzzer(False)
            time.sleep(0.2)
        logger.info("LED/Buzzer test complete")
        
    def test_camera_warmup(self) -> None:
        """Test camera initialization and capture one frame."""
        logger.info("Testing camera warmup and frame capture")
        
        try:
            self.camera = CameraInterface()
            if not self.camera.is_available():
                logger.warning("Camera hardware not detected")
                return
                
            logger.info("Camera warming up...")
            self.camera.start()
            
            # Capture test frame
            frame, timestamp = self.camera.capture_frame()
            logger.info(f"Camera test frame captured: shape {frame.shape}, timestamp {timestamp}")
            
        except Exception as e:
            logger.error(f"Camera test failed: {e}")
        finally:
            if self.camera:
                self.camera.stop()
                
    def test_motor(self, motor: BTS7960, name: str) -> None:
        """Test a single motor with forward/reverse cycle."""
        if not self._running:
            return
            
        logger.info(f"Testing {name} motor")
        
        try:
            # Check if button is pressed (safety)
            if self.is_button_pressed():
                logger.warning(f"Button pressed - skipping {name} motor test for safety")
                return
                
            motor.enable()
            
            # Forward
            logger.info(f"{name} motor: forward 30% for 2s")
            motor.drive(30)
            time.sleep(2.0)
            
            # Brake
            if self._running:
                logger.info(f"{name} motor: braking for 0.5s")
                motor.brake()
                time.sleep(0.5)
            
            # Reverse
            if self._running:
                logger.info(f"{name} motor: reverse 30% for 2s")
                motor.drive(-30)
                time.sleep(2.0)
                
            # Stop
            motor.stop()
            logger.info(f"{name} motor test complete")
            
        except Exception as e:
            logger.error(f"{name} motor test failed: {e}")
        finally:
            try:
                motor.stop()
                motor.disable()
            except Exception as e:
                logger.error(f"Error stopping {name} motor: {e}")
                
    def test_actuator(self) -> None:
        """Test linear actuator extend/retract cycle."""
        if not self._running:
            return
            
        logger.info("Testing linear actuator")
        
        try:
            # Check if button is pressed (safety)
            if self.is_button_pressed():
                logger.warning("Button pressed - skipping actuator test for safety")
                return
                
            self.actuator = LinearActuator()
            self.actuator.enable()
            
            # Extend
            logger.info("Actuator: extending at 40% for 2s")
            self.actuator.extend(40)
            time.sleep(2.0)
            
            # Stop
            if self._running:
                logger.info("Actuator: stopping for 0.5s")
                self.actuator.stop()
                time.sleep(0.5)
            
            # Retract
            if self._running:
                logger.info("Actuator: retracting at 40% for 2s")
                self.actuator.retract(40)
                time.sleep(2.0)
                
            # Final stop
            self.actuator.stop()
            logger.info("Actuator test complete")
            
        except Exception as e:
            logger.error(f"Actuator test failed: {e}")
        finally:
            try:
                if self.actuator:
                    self.actuator.stop()
                    self.actuator.disable()
            except Exception as e:
                logger.error(f"Error stopping actuator: {e}")
                
    def run_all_tests(self) -> None:
        """Run complete hardware test suite."""
        try:
            logger.info("=== BevBot Hardware IO Test Starting ===")
            
            # Setup GPIO
            self.setup_gpio()
            
            # Test LED/buzzer
            self.test_led_buzzer()
            
            if not self._running:
                return
                
            # Test camera
            self.test_camera_warmup()
            
            if not self._running:
                return
                
            # Test motors
            self.left_motor = BTS7960("left")
            self.test_motor(self.left_motor, "left")
            
            if self._running:
                time.sleep(1.0)  # Brief pause between tests
                self.right_motor = BTS7960("right")
                self.test_motor(self.right_motor, "right")
            
            if not self._running:
                return
                
            # Test actuator
            time.sleep(1.0)  # Brief pause
            self.test_actuator()
            
            logger.info("=== All hardware tests complete ===")
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self) -> None:
        """Ensure all hardware is safely stopped."""
        logger.info("Cleaning up hardware...")
        
        try:
            # Turn off LED/buzzer
            if self.pi:
                self.pi.write(LED_BUZZER_PIN, 0)
                
            # Stop all motors
            for motor in [self.left_motor, self.right_motor]:
                if motor:
                    try:
                        motor.stop()
                        motor.disable()
                    except Exception as e:
                        logger.error(f"Error stopping motor: {e}")
                        
            # Stop actuator
            if self.actuator:
                try:
                    self.actuator.stop()
                    self.actuator.disable()
                except Exception as e:
                    logger.error(f"Error stopping actuator: {e}")
                    
            # Stop camera
            if self.camera:
                try:
                    self.camera.stop()
                except Exception as e:
                    logger.error(f"Error stopping camera: {e}")
                    
            # Release pigpio
            if self.pi:
                PigpioWrapper.release_instance()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
        logger.info("Cleanup complete")

def main():
    """Main test function."""
    try:
        test = IOTest()
        test.run_all_tests()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()