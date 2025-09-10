"""BTS7960 motor driver implementation using gpiozero for Raspberry Pi 5 compatibility."""

import time
import logging
from typing import Optional, Tuple
from gpiozero import OutputDevice, PWMOutputDevice, Device
from gpiozero.pins.lgpio import LGPIOFactory

logger = logging.getLogger(__name__)

# Use lgpio for Raspberry Pi 5 compatibility
Device.pin_factory = LGPIOFactory()

class BTS7960Motor:
    """BTS7960 motor driver using gpiozero with hardware PWM support."""
    
    def __init__(self, r_en_pin: int, l_en_pin: int, rpwm_pin: int, lpwm_pin: int, name: str = "motor", invert: bool = False):
        """Initialize BTS7960 motor driver.
        
        Args:
            r_en_pin: Right enable pin number
            l_en_pin: Left enable pin number
            rpwm_pin: Right PWM pin number (forward)
            lpwm_pin: Left PWM pin number (reverse)
            name: Motor name for logging
            invert: If True, inverts the motor direction
        """
        self.name = name
        self.invert = invert
        
        # Create enable pins as regular outputs
        self.r_en = OutputDevice(r_en_pin)
        self.l_en = OutputDevice(l_en_pin)
        
        # Create PWM pins with hardware PWM support
        # Use frequency of 1000Hz for motor control
        self.rpwm = PWMOutputDevice(rpwm_pin, frequency=1000)
        self.lpwm = PWMOutputDevice(lpwm_pin, frequency=1000)
        
        # Start with motor disabled
        self._enabled = False
        self.disable()
        
    def enable(self) -> None:
        """Enable the motor driver."""
        self.r_en.on()
        self.l_en.on()
        self._enabled = True
        logger.info(f"{self.name} motor enabled")
        
    def disable(self) -> None:
        """Disable the motor driver and stop PWM."""
        # Stop PWM first
        self.rpwm.value = 0
        self.lpwm.value = 0
        
        # Disable motor driver
        self.r_en.off()
        self.l_en.off()
        self._enabled = False
        logger.info(f"{self.name} motor disabled")
        
    def brake(self) -> None:
        """Apply electrical brake (both PWMs high)."""
        if not self._enabled:
            raise RuntimeError(f"{self.name} motor must be enabled before braking")
            
        self.rpwm.value = 1.0
        self.lpwm.value = 1.0
        logger.debug(f"{self.name} motor braking")
        
    def drive(self, percent: float) -> None:
        """Drive motor at specified power percentage.
        
        Args:
            percent: Power percentage (-100 to +100). Negative = reverse.
        """
        if not self._enabled:
            raise RuntimeError(f"{self.name} motor must be enabled before driving")
            
        # Clamp to valid range
        percent = max(-100.0, min(100.0, percent))
        
        # Invert direction if needed
        if self.invert:
            percent = -percent
        
        # Convert percentage to PWM value (0.0 to 1.0)
        pwm_value = abs(percent) / 100.0
        
        if percent == 0:
            # Coast - both PWMs off
            self.rpwm.value = 0
            self.lpwm.value = 0
        elif percent > 0:
            # Forward - RPWM active, LPWM off
            self.lpwm.value = 0
            self.rpwm.value = pwm_value
        else:
            # Reverse - LPWM active, RPWM off
            self.rpwm.value = 0
            self.lpwm.value = pwm_value
            
        logger.debug(f"{self.name} motor drive: {percent}% (inverted: {self.invert})")
        
    def stop(self) -> None:
        """Stop motor (coast to stop)."""
        if self._enabled:
            self.drive(0)
            logger.debug(f"{self.name} motor stopped")
            
    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        try:
            self.stop()
            self.disable()
        except Exception as e:
            logger.error(f"Error during {self.name} motor cleanup: {e}")
        finally:
            # Close all devices
            self.rpwm.close()
            self.lpwm.close()
            self.r_en.close()
            self.l_en.close()
            
    def __enter__(self):
        """Context manager entry."""
        self.enable()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure safe shutdown."""
        self.cleanup()