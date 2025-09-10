#!/usr/bin/env python3
"""Hardware IO test for BevBot using gpiozero - tests motors, actuator, camera, and GPIO."""

import time
import logging
import signal
import sys
from typing import Optional
from gpiozero import Button, LED, Device
from gpiozero.pins.lgpio import LGPIOFactory

from .pins import (
    BUTTON_PIN, LED_BUZZER_PIN,
    LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
    RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
)
from .motor_gpiozero import BTS7960Motor
from .actuator_gpiozero import LinearActuator
from .camera import CameraInterface

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use lgpio for Raspberry Pi 5 compatibility
Device.pin_factory = LGPIOFactory()

class IOTest:
    """Hardware IO test suite for BevBot using gpiozero."""
    
    def __init__(self):
        """Initialize test hardware."""
        self.button: Optional[Button] = None
        self.led_buzzer: Optional[LED] = None
        self.left_motor: Optional[BTS7960Motor] = None
        self.right_motor: Optional[BTS7960Motor] = None
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
        """Setup GPIO pins for button and LED/buzzer using gpiozero."""
        try:
            # Setup button with internal pull-up resistor
            # Button is active low, so we use pull_up=True
            self.button = Button(BUTTON_PIN, pull_up=True, bounce_time=0.1)
            
            # Setup LED/buzzer as output
            self.led_buzzer = LED(LED_BUZZER_PIN)
            self.led_buzzer.off()  # Start with LED/buzzer off
            
            logger.info("GPIO setup complete using gpiozero")
            
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            raise
        
    def is_button_pressed(self) -> bool:
        """Check if button is pressed (active low)."""
        if self.button:
            return self.button.is_pressed
        return False
        
    def set_led_buzzer(self, state: bool) -> None:
        """Set LED/buzzer state."""
        if self.led_buzzer:
            if state:
                self.led_buzzer.on()
            else:
                self.led_buzzer.off()
        
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
        
    def test_button(self) -> None:
        """Test button input."""
        logger.info("Testing button - press the button within 5 seconds")
        start_time = time.time()
        button_pressed = False
        
        while time.time() - start_time < 5.0 and self._running:
            if self.is_button_pressed():
                button_pressed = True
                logger.info("Button press detected!")
                # Flash LED to confirm button press
                for _ in range(3):
                    self.set_led_buzzer(True)
                    time.sleep(0.1)
                    self.set_led_buzzer(False)
                    time.sleep(0.1)
                break
            time.sleep(0.1)
            
        if not button_pressed:
            logger.info("No button press detected during test period")
        logger.info("Button test complete")
        
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
                
    def test_motor(self, motor: BTS7960Motor, name: str) -> None:
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
            logger.info("=== BevBot Hardware IO Test Starting (gpiozero) ===")
            logger.info("Using lgpio pin factory for Raspberry Pi 5 compatibility")
            
            # Setup GPIO
            self.setup_gpio()
            
            # Test button
            self.test_button()
            
            # Test LED/buzzer
            self.test_led_buzzer()
            
            if not self._running:
                return
                
            # Test camera
            self.test_camera_warmup()
            
            if not self._running:
                return
                
            # Test motors
            logger.info("Initializing left motor (inverted)...")
            self.left_motor = BTS7960Motor(
                r_en_pin=LEFT_MOTOR_R_EN,
                l_en_pin=LEFT_MOTOR_L_EN,
                rpwm_pin=LEFT_MOTOR_RPWM,
                lpwm_pin=LEFT_MOTOR_LPWM,
                name="left",
                invert=True  # Left motor needs direction inverted
            )
            self.test_motor(self.left_motor, "left")
            
            if self._running:
                time.sleep(1.0)  # Brief pause between tests
                logger.info("Initializing right motor...")
                self.right_motor = BTS7960Motor(
                    r_en_pin=RIGHT_MOTOR_R_EN,
                    l_en_pin=RIGHT_MOTOR_L_EN,
                    rpwm_pin=RIGHT_MOTOR_RPWM,
                    lpwm_pin=RIGHT_MOTOR_LPWM,
                    name="right",
                    invert=False  # Right motor direction is correct
                )
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
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def cleanup(self) -> None:
        """Ensure all hardware is safely stopped and GPIO resources are released."""
        logger.info("Cleaning up hardware...")
        
        try:
            # Turn off LED/buzzer
            if self.led_buzzer:
                self.led_buzzer.off()
                self.led_buzzer.close()
                
            # Close button
            if self.button:
                self.button.close()
                
            # Stop and cleanup all motors
            for motor in [self.left_motor, self.right_motor]:
                if motor:
                    try:
                        motor.cleanup()
                    except Exception as e:
                        logger.error(f"Error cleaning up motor: {e}")
                        
            # Stop and cleanup actuator
            if self.actuator:
                try:
                    self.actuator.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up actuator: {e}")
                    
            # Stop camera
            if self.camera:
                try:
                    self.camera.stop()
                except Exception as e:
                    logger.error(f"Error stopping camera: {e}")
                    
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
        logger.info("Cleanup complete")

def main():
    """Main test function."""
    try:
        # Check if running on Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                logger.info(f"Running on: {model.strip()}")
                if 'Raspberry Pi 5' in model:
                    logger.info("Detected Raspberry Pi 5 - using lgpio backend")
        except FileNotFoundError:
            logger.warning("Not running on Raspberry Pi - some tests may not work")
            
        test = IOTest()
        test.run_all_tests()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()