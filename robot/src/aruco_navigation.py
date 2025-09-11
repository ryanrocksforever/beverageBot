#!/usr/bin/env python3
"""ArUco marker navigation system with precise alignment and position saving."""

import cv2
import numpy as np
import time
import logging
import json
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import threading

try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: gpiozero not available, running in simulation mode")

from .camera import CameraInterface
from .aruco_center_demo import MarkerInfo, ArUcoDetector
from .camera_config import (
    CAMERA_MATRIX, DISTORTION_COEFFS, MARKER_SIZE_CM,
    DEFAULT_TARGET_DISTANCE_CM, TOLERANCE_X_PIXELS, 
    TOLERANCE_Y_PIXELS, TOLERANCE_SIZE_PIXELS
)

if HARDWARE_AVAILABLE:
    from .pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    from .motor_gpiozero import BTS7960Motor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NavigationState(Enum):
    """Navigation state machine states."""
    IDLE = "idle"
    SEARCHING = "searching"
    APPROACHING = "approaching"
    ALIGNING = "aligning"
    ALIGNED = "aligned"
    ERROR = "error"

@dataclass
class MarkerPosition:
    """Saved position for a specific ArUco marker."""
    marker_id: int
    name: str
    target_x: float  # Target X position in frame (pixels)
    target_y: float  # Target Y position in frame (pixels)
    target_size: float  # Target apparent size (pixels)
    target_distance: float  # Target distance (cm)
    tolerance_x: float  # X position tolerance (pixels)
    tolerance_y: float  # Y position tolerance (pixels)
    tolerance_size: float  # Size tolerance (pixels)
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class PrecisionAlignmentController:
    """High precision alignment controller for close-in marker positioning."""
    
    def __init__(self):
        """Initialize precision alignment controller."""
        # Fine control PID gains
        self.kp_x = 0.08  # Proportional gain for X alignment
        self.ki_x = 0.005  # Integral gain for X alignment
        self.kd_x = 0.02  # Derivative gain for X alignment
        
        self.kp_y = 0.05  # Proportional gain for Y alignment (distance)
        self.ki_y = 0.003  # Integral gain for Y alignment
        self.kd_y = 0.01  # Derivative gain for Y alignment
        
        self.kp_rot = 0.1  # Proportional gain for rotation alignment
        
        # State variables
        self.x_integral = 0
        self.y_integral = 0
        self.last_x_error = 0
        self.last_y_error = 0
        
        # Speed limits for precision mode
        self.max_linear_speed = 20  # Maximum forward/backward speed
        self.max_turn_speed = 15  # Maximum turning speed
        self.min_speed = 8  # Minimum speed threshold
        
    def reset(self):
        """Reset controller state."""
        self.x_integral = 0
        self.y_integral = 0
        self.last_x_error = 0
        self.last_y_error = 0
    
    def compute_alignment(self, current: MarkerInfo, target: MarkerPosition) -> Tuple[float, float, bool]:
        """Compute motor speeds for precise alignment.
        
        Returns:
            Tuple of (left_speed, right_speed, is_aligned)
        """
        # Calculate errors
        x_error = target.target_x - current.center[0]
        y_error = target.target_y - current.center[1]
        size_error = target.target_size - current.size
        
        # Check if aligned within tolerance
        is_aligned = (
            abs(x_error) <= target.tolerance_x and
            abs(y_error) <= target.tolerance_y and
            abs(size_error) <= target.tolerance_size
        )
        
        if is_aligned:
            return 0, 0, True
        
        # Update integral terms
        self.x_integral += x_error * 0.05  # dt ~ 0.05s
        self.y_integral += y_error * 0.05
        
        # Clamp integrals to prevent windup
        self.x_integral = np.clip(self.x_integral, -50, 50)
        self.y_integral = np.clip(self.y_integral, -50, 50)
        
        # Calculate derivatives
        x_derivative = (x_error - self.last_x_error) / 0.05
        y_derivative = (y_error - self.last_y_error) / 0.05
        
        self.last_x_error = x_error
        self.last_y_error = y_error
        
        # PID control
        turn_control = (
            self.kp_x * x_error +
            self.ki_x * self.x_integral +
            self.kd_x * x_derivative
        )
        
        # Use size error as proxy for distance
        forward_control = (
            self.kp_y * size_error +
            self.ki_y * self.y_integral +
            self.kd_y * y_derivative
        )
        
        # Convert to motor speeds
        left_speed = forward_control - turn_control
        right_speed = forward_control + turn_control
        
        # Apply speed limits
        left_speed = np.clip(left_speed, -self.max_linear_speed, self.max_linear_speed)
        right_speed = np.clip(right_speed, -self.max_linear_speed, self.max_linear_speed)
        
        # Apply minimum speed threshold for movement
        if abs(left_speed) < self.min_speed and left_speed != 0:
            left_speed = self.min_speed if left_speed > 0 else -self.min_speed
        if abs(right_speed) < self.min_speed and right_speed != 0:
            right_speed = self.min_speed if right_speed > 0 else -self.min_speed
        
        return left_speed, right_speed, False

class ArUcoNavigator:
    """Main navigation system for moving between ArUco markers."""
    
    def __init__(self, simulation_mode: bool = False):
        """Initialize navigator."""
        self.simulation_mode = simulation_mode or not HARDWARE_AVAILABLE
        
        # Components
        self.camera = None
        self.detector = ArUcoDetector(marker_size_cm=MARKER_SIZE_CM)  # Use 100mm markers
        self.precision_controller = PrecisionAlignmentController()
        
        # Motors
        self.left_motor = None
        self.right_motor = None
        
        # State
        self.state = NavigationState.IDLE
        self.current_target = None
        self.saved_positions: Dict[int, MarkerPosition] = {}
        self.positions_file = "marker_positions.json"
        
        # Navigation thread
        self.nav_thread = None
        self.nav_running = False
        
        if not self.simulation_mode:
            self._init_hardware()
        
        # Load saved positions
        self.load_positions()
    
    def _init_hardware(self):
        """Initialize hardware components."""
        try:
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
            
            self.left_motor.enable()
            self.right_motor.enable()
            
            logger.info("Motors initialized")
        except Exception as e:
            logger.error(f"Failed to initialize motors: {e}")
            self.simulation_mode = True
    
    def init_camera(self):
        """Initialize camera."""
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                logger.info("Camera initialized")
                return True
            else:
                logger.error("Camera not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            return False
    
    def save_current_position(self, marker_id: int, name: str = None,
                            tolerance_x: float = 10, tolerance_y: float = 10,
                            tolerance_size: float = 5) -> bool:
        """Save the current position of a visible marker as the target position.
        
        This is the calibration step where you position the robot exactly where
        it should be relative to the marker, then save that position.
        
        Args:
            marker_id: ID of the marker to save
            name: Optional name for this position
            tolerance_x: X position tolerance in pixels
            tolerance_y: Y position tolerance in pixels
            tolerance_size: Size tolerance in pixels
            
        Returns:
            True if position was saved successfully
        """
        if not self.camera:
            logger.error("Camera not initialized")
            return False
        
        # Capture current frame
        frame, _ = self.camera.capture_frame()
        markers = self.detector.detect_markers(frame)
        
        if marker_id not in markers:
            logger.error(f"Marker {marker_id} not visible")
            return False
        
        marker = markers[marker_id]
        
        # Save position
        position = MarkerPosition(
            marker_id=marker_id,
            name=name or f"Position_{marker_id}",
            target_x=marker.center[0],
            target_y=marker.center[1],
            target_size=marker.size,
            target_distance=marker.distance,
            tolerance_x=tolerance_x,
            tolerance_y=tolerance_y,
            tolerance_size=tolerance_size
        )
        
        self.saved_positions[marker_id] = position
        self.save_positions()
        
        logger.info(f"Saved position for marker {marker_id}:")
        logger.info(f"  Position: ({position.target_x:.1f}, {position.target_y:.1f})")
        logger.info(f"  Size: {position.target_size:.1f} pixels")
        logger.info(f"  Distance: {position.target_distance:.1f} cm")
        
        return True
    
    def save_positions(self):
        """Save all positions to file."""
        data = {
            'positions': [pos.to_dict() for pos in self.saved_positions.values()],
            'updated': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(self.positions_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(self.saved_positions)} positions to {self.positions_file}")
    
    def load_positions(self):
        """Load saved positions from file."""
        if not os.path.exists(self.positions_file):
            logger.info("No saved positions file found")
            return
        
        try:
            with open(self.positions_file, 'r') as f:
                data = json.load(f)
            
            self.saved_positions = {}
            for pos_data in data['positions']:
                pos = MarkerPosition.from_dict(pos_data)
                self.saved_positions[pos.marker_id] = pos
            
            logger.info(f"Loaded {len(self.saved_positions)} saved positions")
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
    
    def navigate_to_marker(self, marker_id: int, timeout: float = 30) -> bool:
        """Navigate to a specific marker position.
        
        Args:
            marker_id: ID of the marker to navigate to
            timeout: Maximum time to attempt navigation
            
        Returns:
            True if successfully aligned with marker
        """
        if marker_id not in self.saved_positions:
            logger.error(f"No saved position for marker {marker_id}")
            return False
        
        self.current_target = self.saved_positions[marker_id]
        self.state = NavigationState.SEARCHING
        
        logger.info(f"Starting navigation to marker {marker_id} ({self.current_target.name})")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Get current frame
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if self.state == NavigationState.SEARCHING:
                if marker_id in markers:
                    logger.info(f"Found marker {marker_id}, approaching...")
                    self.state = NavigationState.APPROACHING
                    self.precision_controller.reset()
                else:
                    # Slow rotation to search for marker
                    self._set_motor_speeds(-15, 15)  # Turn in place
                    time.sleep(0.1)
                    continue
            
            elif self.state == NavigationState.APPROACHING:
                if marker_id not in markers:
                    logger.warning("Lost marker, searching again...")
                    self.state = NavigationState.SEARCHING
                    continue
                
                marker = markers[marker_id]
                
                # Check if close enough for precision alignment
                size_ratio = marker.size / self.current_target.target_size
                if size_ratio > 0.7:  # Within 70% of target size
                    logger.info("Close enough, switching to precision alignment")
                    self.state = NavigationState.ALIGNING
                    self.precision_controller.reset()
                else:
                    # Simple approach control
                    center_x = frame.shape[1] / 2
                    x_error = marker.center[0] - center_x
                    
                    # Basic proportional control
                    turn = x_error * 0.05
                    forward = 25  # Fixed approach speed
                    
                    left = forward - turn
                    right = forward + turn
                    
                    self._set_motor_speeds(left, right)
                    time.sleep(0.05)
            
            elif self.state == NavigationState.ALIGNING:
                if marker_id not in markers:
                    logger.warning("Lost marker during alignment, searching...")
                    self.state = NavigationState.SEARCHING
                    continue
                
                marker = markers[marker_id]
                
                # Use precision controller
                left, right, aligned = self.precision_controller.compute_alignment(
                    marker, self.current_target
                )
                
                if aligned:
                    logger.info(f"Successfully aligned with marker {marker_id}!")
                    self.state = NavigationState.ALIGNED
                    self._stop_motors()
                    return True
                
                self._set_motor_speeds(left, right)
                time.sleep(0.05)
        
        # Timeout reached
        logger.error(f"Navigation timeout reached for marker {marker_id}")
        self._stop_motors()
        self.state = NavigationState.ERROR
        return False
    
    def navigate_sequence(self, marker_ids: List[int], pause_time: float = 2.0):
        """Navigate through a sequence of markers.
        
        Args:
            marker_ids: List of marker IDs to visit in order
            pause_time: Time to pause at each marker
        """
        logger.info(f"Starting navigation sequence: {marker_ids}")
        
        for i, marker_id in enumerate(marker_ids):
            logger.info(f"Step {i+1}/{len(marker_ids)}: Navigating to marker {marker_id}")
            
            success = self.navigate_to_marker(marker_id)
            
            if success:
                logger.info(f"Reached marker {marker_id}, pausing for {pause_time}s")
                time.sleep(pause_time)
            else:
                logger.error(f"Failed to reach marker {marker_id}, aborting sequence")
                break
        
        logger.info("Navigation sequence completed")
        self._stop_motors()
    
    def _set_motor_speeds(self, left: float, right: float):
        """Set motor speeds."""
        if not self.simulation_mode:
            self.left_motor.drive(left)
            self.right_motor.drive(right)
    
    def _stop_motors(self):
        """Stop all motors."""
        self._set_motor_speeds(0, 0)
    
    def cleanup(self):
        """Clean up resources."""
        self._stop_motors()
        
        if self.camera:
            self.camera.stop()
        
        if not self.simulation_mode:
            if self.left_motor:
                self.left_motor.disable()
                self.left_motor.cleanup()
            if self.right_motor:
                self.right_motor.disable()
                self.right_motor.cleanup()

class CalibrationMode:
    """Interactive calibration mode for saving marker positions."""
    
    def __init__(self, navigator: ArUcoNavigator):
        """Initialize calibration mode."""
        self.navigator = navigator
    
    def run_interactive(self):
        """Run interactive calibration session."""
        print("\n=== ArUco Marker Position Calibration ===")
        print("Position the robot exactly where it should be relative to each marker,")
        print("then save that position. The robot will later navigate to reproduce")
        print("these exact positions.\n")
        
        while True:
            print("\nOptions:")
            print("1. Save current position for visible marker")
            print("2. List saved positions")
            print("3. Test navigation to saved position")
            print("4. Delete saved position")
            print("5. Exit calibration")
            
            choice = input("\nChoice: ").strip()
            
            if choice == '1':
                self.save_position_interactive()
            elif choice == '2':
                self.list_positions()
            elif choice == '3':
                self.test_navigation()
            elif choice == '4':
                self.delete_position()
            elif choice == '5':
                break
            else:
                print("Invalid choice")
    
    def save_position_interactive(self):
        """Interactively save current position."""
        # Detect visible markers
        frame, _ = self.navigator.camera.capture_frame()
        markers = self.navigator.detector.detect_markers(frame)
        
        if not markers:
            print("No markers visible!")
            return
        
        print(f"\nVisible markers: {list(markers.keys())}")
        
        try:
            marker_id = int(input("Enter marker ID to save: "))
            if marker_id not in markers:
                print(f"Marker {marker_id} not visible!")
                return
            
            name = input(f"Enter name for this position (default: Position_{marker_id}): ").strip()
            if not name:
                name = f"Position_{marker_id}"
            
            tol_x = float(input("X tolerance in pixels (default: 10): ") or "10")
            tol_y = float(input("Y tolerance in pixels (default: 10): ") or "10")
            tol_size = float(input("Size tolerance in pixels (default: 5): ") or "5")
            
            success = self.navigator.save_current_position(
                marker_id, name, tol_x, tol_y, tol_size
            )
            
            if success:
                print(f"✓ Position saved for marker {marker_id}")
            else:
                print(f"✗ Failed to save position")
                
        except ValueError:
            print("Invalid input")
    
    def list_positions(self):
        """List all saved positions."""
        if not self.navigator.saved_positions:
            print("\nNo saved positions")
            return
        
        print("\nSaved Positions:")
        print("-" * 60)
        for marker_id, pos in self.navigator.saved_positions.items():
            print(f"Marker {marker_id}: {pos.name}")
            print(f"  Position: ({pos.target_x:.1f}, {pos.target_y:.1f})")
            print(f"  Size: {pos.target_size:.1f} px, Distance: {pos.target_distance:.1f} cm")
            print(f"  Tolerances: X=±{pos.tolerance_x}, Y=±{pos.tolerance_y}, Size=±{pos.tolerance_size}")
            print()
    
    def test_navigation(self):
        """Test navigation to a saved position."""
        if not self.navigator.saved_positions:
            print("\nNo saved positions")
            return
        
        print(f"\nSaved markers: {list(self.navigator.saved_positions.keys())}")
        
        try:
            marker_id = int(input("Enter marker ID to navigate to: "))
            if marker_id not in self.navigator.saved_positions:
                print(f"No saved position for marker {marker_id}")
                return
            
            print(f"Navigating to marker {marker_id}...")
            success = self.navigator.navigate_to_marker(marker_id)
            
            if success:
                print("✓ Successfully aligned with marker!")
            else:
                print("✗ Failed to align with marker")
                
        except ValueError:
            print("Invalid input")
    
    def delete_position(self):
        """Delete a saved position."""
        if not self.navigator.saved_positions:
            print("\nNo saved positions")
            return
        
        print(f"\nSaved markers: {list(self.navigator.saved_positions.keys())}")
        
        try:
            marker_id = int(input("Enter marker ID to delete: "))
            if marker_id in self.navigator.saved_positions:
                del self.navigator.saved_positions[marker_id]
                self.navigator.save_positions()
                print(f"✓ Deleted position for marker {marker_id}")
            else:
                print(f"No saved position for marker {marker_id}")
        except ValueError:
            print("Invalid input")

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ArUco marker navigation system')
    parser.add_argument('--calibrate', action='store_true',
                       help='Run calibration mode to save marker positions')
    parser.add_argument('--navigate', type=int, nargs='+',
                       help='Navigate to marker IDs in sequence')
    parser.add_argument('--save', type=int,
                       help='Save current position for specified marker ID')
    parser.add_argument('--list', action='store_true',
                       help='List all saved positions')
    
    args = parser.parse_args()
    
    # Initialize navigator
    navigator = ArUcoNavigator()
    
    if not navigator.init_camera():
        print("Failed to initialize camera")
        return 1
    
    try:
        if args.calibrate:
            # Run interactive calibration
            calibrator = CalibrationMode(navigator)
            calibrator.run_interactive()
            
        elif args.save is not None:
            # Save current position for specified marker
            success = navigator.save_current_position(args.save)
            if success:
                print(f"Saved position for marker {args.save}")
            else:
                print(f"Failed to save position for marker {args.save}")
                
        elif args.navigate:
            # Navigate to specified markers
            navigator.navigate_sequence(args.navigate)
            
        elif args.list:
            # List saved positions
            if not navigator.saved_positions:
                print("No saved positions")
            else:
                print("\nSaved Positions:")
                for marker_id, pos in navigator.saved_positions.items():
                    print(f"Marker {marker_id}: {pos.name}")
                    print(f"  Position: ({pos.target_x:.1f}, {pos.target_y:.1f})")
                    print(f"  Size: {pos.target_size:.1f} px")
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        navigator.cleanup()
    
    return 0

if __name__ == "__main__":
    exit(main())