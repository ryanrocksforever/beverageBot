#!/usr/bin/env python3
"""Test program for linear actuator - extends to both ends and allows manual control."""

import time
import logging
import signal
import sys
from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

from .actuator_gpiozero import LinearActuator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use lgpio for Raspberry Pi 5 compatibility
Device.pin_factory = LGPIOFactory()

class ActuatorTest:
    """Test program for linear actuator."""
    
    def __init__(self):
        """Initialize actuator test."""
        self.actuator = None
        self._running = True
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("\nShutdown signal received, stopping actuator...")
        self._running = False
        
    def full_extension_test(self, speed: float = 50, extend_time: float = 12.5, retract_time: float = 12.5):
        """Test full extension and retraction of actuator (2 inch stroke).
        
        Args:
            speed: Actuator speed percentage (0-100)
            extend_time: Time to extend in seconds (default 12.5s for 2" stroke)
            retract_time: Time to retract in seconds (default 12.5s for 2" stroke)
        """
        try:
            logger.info("=== Actuator Full Extension Test (2 inch stroke) ===")
            logger.info(f"Speed: {speed}%")
            logger.info(f"Extension time: {extend_time}s")
            logger.info(f"Retraction time: {retract_time}s")
            logger.info(f"Full cycle: ~{extend_time + retract_time}s")
            logger.info("Press Ctrl+C to stop at any time")
            logger.info("")
            
            # Initialize actuator
            logger.info("Initializing actuator...")
            self.actuator = LinearActuator()
            
            # Enable actuator
            self.actuator.enable()
            logger.info("Actuator enabled")
            
            # Extend fully
            if self._running:
                logger.info(f"Extending actuator at {speed}% for {extend_time}s...")
                self.actuator.extend(speed)
                
                start_time = time.time()
                while self._running and (time.time() - start_time) < extend_time:
                    remaining = extend_time - (time.time() - start_time)
                    if int(remaining) % 2 == 0:
                        logger.info(f"  Extending... {remaining:.1f}s remaining")
                    time.sleep(0.5)
                
                logger.info("Stopping actuator...")
                self.actuator.stop()
                time.sleep(1)
            
            # Retract fully
            if self._running:
                logger.info(f"Retracting actuator at {speed}% for {retract_time}s...")
                self.actuator.retract(speed)
                
                start_time = time.time()
                while self._running and (time.time() - start_time) < retract_time:
                    remaining = retract_time - (time.time() - start_time)
                    if int(remaining) % 2 == 0:
                        logger.info(f"  Retracting... {remaining:.1f}s remaining")
                    time.sleep(0.5)
                
                logger.info("Stopping actuator...")
                self.actuator.stop()
            
            logger.info("Full extension test complete!")
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def manual_control(self):
        """Manual control mode for actuator."""
        try:
            logger.info("=== Actuator Manual Control ===")
            logger.info("Commands:")
            logger.info("  e/extend [speed]  - Extend actuator (default 50%)")
            logger.info("  r/retract [speed] - Retract actuator (default 50%)")
            logger.info("  s/stop            - Stop actuator")
            logger.info("  b/brake           - Apply brake")
            logger.info("  q/quit            - Exit program")
            logger.info("")
            
            # Initialize actuator
            logger.info("Initializing actuator...")
            self.actuator = LinearActuator()
            self.actuator.enable()
            logger.info("Actuator enabled and ready")
            logger.info("")
            
            while self._running:
                try:
                    cmd = input("Command> ").strip().lower().split()
                    if not cmd:
                        continue
                    
                    action = cmd[0]
                    
                    if action in ['q', 'quit']:
                        logger.info("Exiting...")
                        break
                    elif action in ['e', 'extend']:
                        speed = float(cmd[1]) if len(cmd) > 1 else 50
                        logger.info(f"Extending at {speed}%")
                        self.actuator.extend(speed)
                    elif action in ['r', 'retract']:
                        speed = float(cmd[1]) if len(cmd) > 1 else 50
                        logger.info(f"Retracting at {speed}%")
                        self.actuator.retract(speed)
                    elif action in ['s', 'stop']:
                        logger.info("Stopping")
                        self.actuator.stop()
                    elif action in ['b', 'brake']:
                        logger.info("Applying brake")
                        self.actuator.brake()
                    else:
                        logger.warning(f"Unknown command: {action}")
                        
                except ValueError as e:
                    logger.error(f"Invalid input: {e}")
                except EOFError:
                    # Handle Ctrl+D
                    logger.info("\nExiting...")
                    break
                    
        except KeyboardInterrupt:
            logger.info("\nTest interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def cycle_test(self, speed: float = 40, cycles: int = 3):
        """Cycle the actuator multiple times.
        
        Args:
            speed: Actuator speed percentage (0-100)
            cycles: Number of extend/retract cycles
        """
        try:
            logger.info("=== Actuator Cycle Test ===")
            logger.info(f"Speed: {speed}%")
            logger.info(f"Cycles: {cycles}")
            logger.info("Press Ctrl+C to stop")
            logger.info("")
            
            # Initialize actuator
            logger.info("Initializing actuator...")
            self.actuator = LinearActuator()
            self.actuator.enable()
            logger.info("Actuator enabled")
            
            for cycle in range(1, cycles + 1):
                if not self._running:
                    break
                    
                logger.info(f"\n--- Cycle {cycle}/{cycles} ---")
                
                # Extend
                if self._running:
                    logger.info(f"Extending at {speed}%...")
                    self.actuator.extend(speed)
                    time.sleep(8)  # Increased for 2" stroke
                    
                # Stop briefly
                if self._running:
                    logger.info("Stopping...")
                    self.actuator.stop()
                    time.sleep(1)
                    
                # Retract
                if self._running:
                    logger.info(f"Retracting at {speed}%...")
                    self.actuator.retract(speed)
                    time.sleep(8)  # Increased for 2" stroke
                    
                # Stop briefly
                if self._running:
                    logger.info("Stopping...")
                    self.actuator.stop()
                    time.sleep(1)
                    
            logger.info("\nCycle test complete!")
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up actuator resources."""
        logger.info("Cleaning up...")
        if self.actuator:
            try:
                self.actuator.stop()
                self.actuator.disable()
                self.actuator.cleanup()
                logger.info("Actuator stopped and cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

def main():
    """Main function with command line argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test linear actuator')
    parser.add_argument('--mode', choices=['full', 'cycle', 'manual'], 
                        default='full', help='Test mode (default: full)')
    parser.add_argument('--speed', type=float, default=50, 
                        help='Actuator speed percentage (0-100, default: 50)')
    parser.add_argument('--extend-time', type=float, default=12.5,
                        help='Extension time in seconds for full test (default: 12.5s, ~25s full cycle)')
    parser.add_argument('--retract-time', type=float, default=12.5,
                        help='Retraction time in seconds for full test (default: 12.5s, ~25s full cycle)')
    parser.add_argument('--cycles', type=int, default=3,
                        help='Number of cycles for cycle test (default: 3)')
    
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
            
        test = ActuatorTest()
        
        if args.mode == 'full':
            test.full_extension_test(
                speed=args.speed,
                extend_time=args.extend_time,
                retract_time=args.retract_time
            )
        elif args.mode == 'cycle':
            test.cycle_test(speed=args.speed, cycles=args.cycles)
        elif args.mode == 'manual':
            test.manual_control()
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()