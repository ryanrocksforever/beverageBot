"""BTS7960 motor driver implementation for BevBot."""

import time
import logging
from typing import Optional
import pigpio
from .pins import get_motor_pins, PWM_FREQUENCY, percent_to_pwm_value, clamp_pwm_percent

logger = logging.getLogger(__name__)

class PigpioWrapper:
    """Shared pigpio instance manager."""
    _instance: Optional[pigpio.pi] = None
    _ref_count: int = 0
    
    @classmethod
    def get_instance(cls) -> pigpio.pi:
        """Get shared pigpio instance."""
        if cls._instance is None:
            cls._instance = pigpio.pi()
            if not cls._instance.connected:
                raise RuntimeError("Cannot connect to pigpiod. Is it running? (sudo systemctl start pigpiod)")
        cls._ref_count += 1
        return cls._instance
    
    @classmethod
    def release_instance(cls) -> None:
        """Release reference to shared pigpio instance."""
        cls._ref_count -= 1
        if cls._ref_count <= 0 and cls._instance is not None:
            cls._instance.stop()
            cls._instance = None
            cls._ref_count = 0

class BTS7960:
    """BTS7960 motor driver with hardware PWM control."""
    
    def __init__(self, motor_type: str):
        """Initialize BTS7960 driver.
        
        Args:
            motor_type: "left", "right", or "actuator"
        """
        self.motor_type = motor_type
        self.r_en, self.l_en, self.rpwm, self.lpwm = get_motor_pins(motor_type)
        self._pi: Optional[pigpio.pi] = None
        self._enabled = False
        
    def _get_pi(self) -> pigpio.pi:
        """Get pigpio instance."""
        if self._pi is None:
            self._pi = PigpioWrapper.get_instance()
        return self._pi
        
    def _setup_pins(self) -> None:
        """Setup GPIO pins for motor control."""
        pi = self._get_pi()
        
        # Set enable pins as outputs (LOW = disabled)
        pi.set_mode(self.r_en, pigpio.OUTPUT)
        pi.set_mode(self.l_en, pigpio.OUTPUT)
        pi.write(self.r_en, 0)
        pi.write(self.l_en, 0)
        
        # Set PWM pins as outputs
        pi.set_mode(self.rpwm, pigpio.OUTPUT)
        pi.set_mode(self.lpwm, pigpio.OUTPUT)
        
        # Initialize PWM with 0 duty cycle
        pi.set_PWM_frequency(self.rpwm, PWM_FREQUENCY)
        pi.set_PWM_frequency(self.lpwm, PWM_FREQUENCY)
        pi.set_PWM_range(self.rpwm, 255)
        pi.set_PWM_range(self.lpwm, 255)
        pi.set_PWM_dutycycle(self.rpwm, 0)
        pi.set_PWM_dutycycle(self.lpwm, 0)
        
    def enable(self) -> None:
        """Enable the motor driver."""
        if not self._enabled:
            self._setup_pins()
            pi = self._get_pi()
            pi.write(self.r_en, 1)
            pi.write(self.l_en, 1)
            self._enabled = True
            logger.info(f"{self.motor_type} motor enabled")
            
    def disable(self) -> None:
        """Disable the motor driver and stop PWM."""
        if self._enabled:
            pi = self._get_pi()
            # Stop PWM first
            pi.set_PWM_dutycycle(self.rpwm, 0)
            pi.set_PWM_dutycycle(self.lpwm, 0)
            # Disable motor driver
            pi.write(self.r_en, 0)
            pi.write(self.l_en, 0)
            self._enabled = False
            logger.info(f"{self.motor_type} motor disabled")
            
    def brake(self) -> None:
        """Apply electrical brake (both PWMs high)."""
        if not self._enabled:
            raise RuntimeError("Motor must be enabled before braking")
            
        pi = self._get_pi()
        pi.set_PWM_dutycycle(self.rpwm, 255)
        pi.set_PWM_dutycycle(self.lpwm, 255)
        logger.debug(f"{self.motor_type} motor braking")
        
    def drive(self, percent: float) -> None:
        """Drive motor at specified power percentage.
        
        Args:
            percent: Power percentage (-100 to +100). Negative = reverse.
        """
        if not self._enabled:
            raise RuntimeError("Motor must be enabled before driving")
            
        percent = max(-100.0, min(100.0, percent))
        pi = self._get_pi()
        
        if percent == 0:
            # Coast - both PWMs off
            pi.set_PWM_dutycycle(self.rpwm, 0)
            pi.set_PWM_dutycycle(self.lpwm, 0)
        elif percent > 0:
            # Forward - RPWM active, LPWM off
            pwm_value = percent_to_pwm_value(abs(percent))
            pi.set_PWM_dutycycle(self.lpwm, 0)
            pi.set_PWM_dutycycle(self.rpwm, pwm_value)
        else:
            # Reverse - LPWM active, RPWM off
            pwm_value = percent_to_pwm_value(abs(percent))
            pi.set_PWM_dutycycle(self.rpwm, 0)
            pi.set_PWM_dutycycle(self.lpwm, pwm_value)
            
        logger.debug(f"{self.motor_type} motor drive: {percent}%")
        
    def stop(self) -> None:
        """Stop motor (coast to stop)."""
        if self._enabled:
            self.drive(0)
            logger.debug(f"{self.motor_type} motor stopped")
            
    def __enter__(self):
        """Context manager entry."""
        self.enable()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure safe shutdown."""
        try:
            self.stop()
            self.disable()
        except Exception as e:
            logger.error(f"Error during motor shutdown: {e}")
        finally:
            if self._pi is not None:
                PigpioWrapper.release_instance()
                self._pi = None