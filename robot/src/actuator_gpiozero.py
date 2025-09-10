"""Linear actuator control using BTS7960 driver with gpiozero for Raspberry Pi 5 compatibility.

The actuator has a 2-inch stroke length with a full cycle time of ~25 seconds at 50% speed 
(12.5 seconds to extend, 12.5 seconds to retract).
"""

import logging
from .motor_gpiozero import BTS7960Motor
from .pins import ACTUATOR_R_EN, ACTUATOR_L_EN, ACTUATOR_RPWM, ACTUATOR_LPWM

logger = logging.getLogger(__name__)

class LinearActuator:
    """Linear actuator controller using BTS7960 driver with gpiozero."""
    
    def __init__(self):
        """Initialize linear actuator controller."""
        self._driver = BTS7960Motor(
            r_en_pin=ACTUATOR_R_EN,
            l_en_pin=ACTUATOR_L_EN,
            rpwm_pin=ACTUATOR_RPWM,
            lpwm_pin=ACTUATOR_LPWM,
            name="actuator"
        )
        
    def enable(self) -> None:
        """Enable the actuator driver."""
        self._driver.enable()
        logger.info("Linear actuator enabled")
        
    def disable(self) -> None:
        """Disable the actuator driver."""
        self._driver.disable()
        logger.info("Linear actuator disabled")
        
    def extend(self, percent: float = 50.0) -> None:
        """Extend the actuator at specified power.
        
        Args:
            percent: Extension power (0-100%). Default 50%.
        """
        percent = abs(percent)  # Ensure positive
        self._driver.drive(-percent)  # Negative for extend (directions were swapped)
        logger.debug(f"Actuator extending at {percent}%")
        
    def retract(self, percent: float = 50.0) -> None:
        """Retract the actuator at specified power.
        
        Args:
            percent: Retraction power (0-100%). Default 50%.
        """
        percent = abs(percent)  # Ensure positive
        self._driver.drive(percent)  # Positive for retract (directions were swapped)
        logger.debug(f"Actuator retracting at {percent}%")
        
    def stop(self) -> None:
        """Stop actuator movement (coast)."""
        self._driver.stop()
        logger.debug("Actuator stopped")
        
    def brake(self) -> None:
        """Apply electrical brake to actuator."""
        self._driver.brake()
        logger.debug("Actuator braking")
        
    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        try:
            self.stop()
            self.disable()
            self._driver.cleanup()
        except Exception as e:
            logger.error(f"Error during actuator cleanup: {e}")
        
    def __enter__(self):
        """Context manager entry."""
        self.enable()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure safe shutdown."""
        self.cleanup()