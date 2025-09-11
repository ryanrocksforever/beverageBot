#!/usr/bin/env python3
"""Standalone robot controller without GUI dependencies."""

import logging
import numpy as np

# Setup logging
logger = logging.getLogger(__name__)

# Try to import hardware dependencies
HARDWARE_AVAILABLE = False
try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    from .pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    from .motor_gpiozero import BTS7960Motor
    from .actuator_gpiozero import LinearActuator
    
    # Use lgpio for Raspberry Pi 5 compatibility
    Device.pin_factory = LGPIOFactory()
    HARDWARE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Hardware libraries not available (running in simulation): {e}")
except Exception as e:
    logger.warning(f"Hardware initialization failed: {e}")

class RobotController:
    """Complete robot control interface without GUI dependencies."""
    
    def __init__(self, simulation_mode: bool = False):
        """Initialize robot controller.
        
        Args:
            simulation_mode: If True, run in simulation mode without hardware
        """
        self.simulation_mode = simulation_mode or not HARDWARE_AVAILABLE
        self.left_motor = None
        self.right_motor = None
        self.actuator = None
        
        # Current state
        self.left_speed = 0
        self.right_speed = 0
        self.actuator_state = "stopped"  # 'extending', 'retracting', 'stopped'
        
        if not self.simulation_mode:
            self._init_hardware()
    
    def _init_hardware(self):
        """Initialize hardware components."""
        if not HARDWARE_AVAILABLE:
            logger.warning("Hardware libraries not available, running in simulation mode")
            self.simulation_mode = True
            return
            
        try:
            # Initialize motors (swapped L/R pins to fix turning)
            self.left_motor = BTS7960Motor(
                r_en_pin=RIGHT_MOTOR_R_EN,
                l_en_pin=RIGHT_MOTOR_L_EN,
                rpwm_pin=RIGHT_MOTOR_RPWM,
                lpwm_pin=RIGHT_MOTOR_LPWM,
                name="left",
                invert=True  # Inverted for correct forward/backward
            )
            
            self.right_motor = BTS7960Motor(
                r_en_pin=LEFT_MOTOR_R_EN,
                l_en_pin=LEFT_MOTOR_L_EN,
                rpwm_pin=LEFT_MOTOR_RPWM,
                lpwm_pin=LEFT_MOTOR_LPWM,
                name="right",
                invert=False  # Not inverted for correct forward/backward
            )
            
            # Initialize actuator
            self.actuator = LinearActuator()
            
            # Enable all
            self.left_motor.enable()
            self.right_motor.enable()
            self.actuator.enable()
            
            logger.info("Hardware initialized")
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            self.simulation_mode = True
    
    def set_motor_speeds(self, left: float, right: float):
        """Set motor speeds.
        
        Args:
            left: Left motor speed (-100 to 100)
            right: Right motor speed (-100 to 100)
        """
        self.left_speed = np.clip(left, -100, 100)
        self.right_speed = np.clip(right, -100, 100)
        
        if not self.simulation_mode:
            try:
                self.left_motor.drive(self.left_speed)
                self.right_motor.drive(self.right_speed)
            except Exception as e:
                logger.error(f"Error setting motor speeds: {e}")
    
    def move_forward(self, speed: float = 30):
        """Move forward at given speed.
        
        Args:
            speed: Forward speed (0-100)
        """
        self.set_motor_speeds(speed, speed)
    
    def move_backward(self, speed: float = 30):
        """Move backward at given speed.
        
        Args:
            speed: Backward speed (0-100)
        """
        self.set_motor_speeds(-speed, -speed)
    
    def turn_left(self, speed: float = 30):
        """Turn left in place.
        
        Args:
            speed: Turn speed (0-100)
        """
        self.set_motor_speeds(-speed, speed)
    
    def turn_right(self, speed: float = 30):
        """Turn right in place.
        
        Args:
            speed: Turn speed (0-100)
        """
        self.set_motor_speeds(speed, -speed)
    
    def stop_motors(self):
        """Stop all motors."""
        self.set_motor_speeds(0, 0)
    
    def extend_actuator(self, speed: float = 50):
        """Extend actuator.
        
        Args:
            speed: Extension speed (0-100)
        """
        self.actuator_state = "extending"
        if not self.simulation_mode and self.actuator:
            self.actuator.extend(speed)
    
    def retract_actuator(self, speed: float = 50):
        """Retract actuator.
        
        Args:
            speed: Retraction speed (0-100)
        """
        self.actuator_state = "retracting"
        if not self.simulation_mode and self.actuator:
            self.actuator.retract(speed)
    
    def stop_actuator(self):
        """Stop actuator."""
        self.actuator_state = "stopped"
        if not self.simulation_mode and self.actuator:
            self.actuator.stop()
    
    def get_status(self):
        """Get current robot status.
        
        Returns:
            Dictionary with current speeds and states
        """
        return {
            'left_speed': self.left_speed,
            'right_speed': self.right_speed,
            'actuator_state': self.actuator_state,
            'simulation_mode': self.simulation_mode
        }
    
    def cleanup(self):
        """Clean up hardware resources."""
        self.stop_motors()
        self.stop_actuator()
        
        if not self.simulation_mode:
            try:
                if self.left_motor:
                    self.left_motor.disable()
                    self.left_motor.cleanup()
                if self.right_motor:
                    self.right_motor.disable()
                    self.right_motor.cleanup()
                if self.actuator:
                    self.actuator.disable()
                    self.actuator.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        logger.info("Robot controller cleaned up")