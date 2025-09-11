#!/usr/bin/env python3
"""Navigator integration for routine system with ArUco marker goals."""

import time
import logging
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .routine_system import MarkerGoal, MarkerApproach
from .aruco_navigation import NavigationState, ArUcoNavigator
from .aruco_center_demo import MarkerInfo

logger = logging.getLogger(__name__)

class RoutineNavigator:
    """Extended navigator for routine system integration."""
    
    def __init__(self, robot, camera, detector):
        """Initialize routine navigator.
        
        Args:
            robot: Robot controller
            camera: Camera interface
            detector: ArUco detector
        """
        self.base_navigator = ArUCoNavigator(robot, camera, detector)
        self.robot = robot
        self.camera = camera
        self.detector = detector
    
    def navigate_to_marker_goal(self, goal: MarkerGoal, timeout: float = 30) -> bool:
        """Navigate to achieve a specific marker goal.
        
        Args:
            goal: MarkerGoal specification
            timeout: Maximum time to achieve goal
            
        Returns:
            True if goal achieved, False otherwise
        """
        logger.info(f"Navigating to marker {goal.marker_id} with approach {goal.approach.value}")
        
        start_time = time.time()
        
        # First, find the marker
        if not self._search_for_marker(goal.marker_id, timeout=min(10, timeout/3)):
            logger.error(f"Failed to find marker {goal.marker_id}")
            return False
        
        # Calculate target position based on approach
        target_distance, target_angle = self._calculate_approach_target(goal)
        
        # Navigate to target position
        while time.time() - start_time < timeout:
            # Get current marker position
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if goal.marker_id not in markers:
                # Lost marker, try to find it again
                if not self._search_for_marker(goal.marker_id, timeout=5):
                    logger.error("Lost marker during navigation")
                    return False
                continue
            
            marker = markers[goal.marker_id]
            current_distance = marker.distance
            current_angle = self._calculate_marker_angle(marker)
            
            # Check if we've reached the goal
            distance_error = abs(current_distance - target_distance)
            angle_error = abs(current_angle - target_angle)
            
            if (distance_error <= goal.tolerance_cm and 
                angle_error <= goal.tolerance_degrees):
                logger.info(f"Reached goal: distance={current_distance:.1f}cm, angle={current_angle:.1f}°")
                
                # Apply final orientation if needed
                if goal.maintain_orientation:
                    self._align_to_marker(marker, target_angle)
                
                self.robot.stop_motors()
                return True
            
            # Navigate towards target
            self._navigate_step(
                current_distance, current_angle,
                target_distance, target_angle,
                marker
            )
            
            time.sleep(0.1)
        
        logger.error("Navigation timeout")
        self.robot.stop_motors()
        return False
    
    def _search_for_marker(self, marker_id: int, timeout: float = 10) -> bool:
        """Search for a specific marker by rotating.
        
        Args:
            marker_id: ID of marker to find
            timeout: Maximum search time
            
        Returns:
            True if marker found, False otherwise
        """
        logger.info(f"Searching for marker {marker_id}")
        
        start_time = time.time()
        search_speed = 20  # Slow rotation speed
        
        # Start rotating
        self.robot.set_motor_speeds(-search_speed, search_speed)
        
        while time.time() - start_time < timeout:
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if marker_id in markers:
                # Found it! Center on marker
                marker = markers[marker_id]
                self.robot.stop_motors()
                
                # Quick center adjustment
                center_x = marker.center[0]
                frame_center = frame.shape[1] / 2
                error = center_x - frame_center
                
                if abs(error) > 50:  # pixels
                    turn_duration = min(abs(error) / 200, 0.5)  # seconds
                    if error > 0:
                        self.robot.set_motor_speeds(15, -15)
                    else:
                        self.robot.set_motor_speeds(-15, 15)
                    time.sleep(turn_duration)
                    self.robot.stop_motors()
                
                logger.info(f"Found marker {marker_id}")
                return True
            
            time.sleep(0.1)
        
        self.robot.stop_motors()
        logger.warning(f"Marker {marker_id} not found")
        return False
    
    def _calculate_approach_target(self, goal: MarkerGoal) -> Tuple[float, float]:
        """Calculate target distance and angle for approach.
        
        Args:
            goal: MarkerGoal specification
            
        Returns:
            Tuple of (target_distance_cm, target_angle_degrees)
        """
        base_distance = goal.distance_cm
        base_angle = 0
        
        if goal.approach == MarkerApproach.FRONT:
            # Default front approach
            pass
        elif goal.approach == MarkerApproach.BACK:
            # Approach from behind (need to go around)
            base_angle = 180
        elif goal.approach == MarkerApproach.LEFT:
            # Approach from left side
            base_angle = 90
        elif goal.approach == MarkerApproach.RIGHT:
            # Approach from right side  
            base_angle = -90
        elif goal.approach == MarkerApproach.CUSTOM:
            # Use specified angle
            base_angle = goal.angle_degrees
        
        # Apply lateral offset if specified
        if goal.offset_x_cm != 0:
            # Calculate adjusted position with offset
            # This would need trigonometry based on current position
            pass
        
        return base_distance, base_angle
    
    def _calculate_marker_angle(self, marker: MarkerInfo) -> float:
        """Calculate angle to marker from robot's perspective.
        
        Args:
            marker: Detected marker info
            
        Returns:
            Angle in degrees (positive = marker to right)
        """
        # Use marker center position in frame
        center_x = marker.center[0]
        frame_width = 640  # Assuming 640x480 resolution
        frame_center = frame_width / 2
        
        # Calculate angle based on position in frame
        # This is approximate - could use camera calibration for accuracy
        fov_horizontal = 130  # degrees for wide angle camera
        pixel_offset = center_x - frame_center
        angle = (pixel_offset / frame_center) * (fov_horizontal / 2)
        
        return angle
    
    def _navigate_step(self, current_distance: float, current_angle: float,
                      target_distance: float, target_angle: float,
                      marker: MarkerInfo):
        """Execute one navigation step towards target.
        
        Args:
            current_distance: Current distance to marker (cm)
            current_angle: Current angle to marker (degrees)
            target_distance: Target distance (cm)
            target_angle: Target angle (degrees)
            marker: Current marker info
        """
        # Calculate errors
        distance_error = target_distance - current_distance
        angle_error = target_angle - current_angle
        
        # Determine motor speeds based on errors
        base_speed = 30
        
        # Distance control
        if abs(distance_error) > 5:  # cm
            if distance_error > 0:  # Too close, back up
                forward_speed = -base_speed
            else:  # Too far, move forward
                forward_speed = base_speed
        else:
            forward_speed = 0
        
        # Angle control with proportional response
        turn_gain = 0.5
        turn_speed = turn_gain * angle_error
        turn_speed = np.clip(turn_speed, -20, 20)
        
        # Combine forward and turn speeds
        left_speed = forward_speed - turn_speed
        right_speed = forward_speed + turn_speed
        
        # Clip to valid range
        left_speed = np.clip(left_speed, -50, 50)
        right_speed = np.clip(right_speed, -50, 50)
        
        # Apply motor commands
        self.robot.set_motor_speeds(left_speed, right_speed)
    
    def _align_to_marker(self, marker: MarkerInfo, target_angle: float):
        """Final alignment to maintain specified orientation.
        
        Args:
            marker: Current marker info
            target_angle: Desired final angle to marker
        """
        logger.info(f"Final alignment to {target_angle}°")
        
        for _ in range(10):  # Max 10 adjustment iterations
            current_angle = self._calculate_marker_angle(marker)
            angle_error = target_angle - current_angle
            
            if abs(angle_error) < 3:  # degrees
                break
            
            # Small rotation to adjust
            turn_speed = np.clip(angle_error * 0.5, -15, 15)
            self.robot.set_motor_speeds(-turn_speed, turn_speed)
            time.sleep(0.2)
            
            # Re-detect marker
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            if marker.id in markers:
                marker = markers[marker.id]
        
        self.robot.stop_motors()
    
    def navigate_to_saved_position(self, marker_id: int, position_name: str,
                                  timeout: float = 30) -> bool:
        """Navigate to a previously saved position relative to a marker.
        
        Args:
            marker_id: Target marker ID
            position_name: Name of saved position
            timeout: Maximum navigation time
            
        Returns:
            True if position reached, False otherwise
        """
        # Delegate to base navigator for saved positions
        return self.base_navigator.navigate_to_saved_position(
            marker_id, position_name, timeout
        )
    
    def get_current_marker_info(self, marker_id: int) -> Optional[MarkerInfo]:
        """Get current information about a specific marker.
        
        Args:
            marker_id: Marker to get info for
            
        Returns:
            MarkerInfo if visible, None otherwise
        """
        frame, _ = self.camera.capture_frame()
        markers = self.detector.detect_markers(frame)
        return markers.get(marker_id)