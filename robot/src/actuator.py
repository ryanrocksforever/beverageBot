"""Linear actuator control using BTS7960 driver for BevBot."""

import logging
from .motor import BTS7960

logger = logging.getLogger(__name__)

class LinearActuator:
    """Linear actuator controller using BTS7960 driver."""
    
    def __init__(self):
        """Initialize linear actuator controller."""
        self._driver = BTS7960("actuator")
        
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
        self._driver.drive(percent)
        logger.debug(f"Actuator extending at {percent}%")
        
    def retract(self, percent: float = 50.0) -> None:
        """Retract the actuator at specified power.
        
        Args:
            percent: Retraction power (0-100%). Default 50%.
        """
        percent = abs(percent)  # Ensure positive
        self._driver.drive(-percent)  # Negative for reverse
        logger.debug(f"Actuator retracting at {percent}%")
        
    def stop(self) -> None:
        """Stop actuator movement (coast)."""
        self._driver.stop()
        logger.debug("Actuator stopped")
        
    def brake(self) -> None:
        """Apply electrical brake to actuator."""
        self._driver.brake()
        logger.debug("Actuator braking")
        
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
            logger.error(f"Error during actuator shutdown: {e}")