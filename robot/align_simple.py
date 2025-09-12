#!/usr/bin/env python3
"""
Simple ArUco Alignment Script for Raspberry Pi 5
Fixed imports and updated ArUco API
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import cv2
import numpy as np
import time
import json
import argparse
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict

# Import with proper error handling
try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: Running in simulation mode")

# Import robot modules
from camera import CameraInterface
from pins import (
    LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
    RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
)

if HARDWARE_AVAILABLE:
    from motor_gpiozero import BTS7960Motor

# ArUco detector class with fixed API
class SimpleArUcoDetector:
    """Simple ArUco detector with updated OpenCV API."""
    
    def __init__(self, marker_size_cm=10.0):
        self.marker_size_cm = marker_size_cm
        
        # Updated ArUco API for OpenCV 4.x
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        
        # Camera matrix (simplified - adjust for your camera)
        self.camera_matrix = np.array([
            [800, 0, 640],
            [0, 800, 360],
            [0, 0, 1]
        ], dtype=float)
        self.dist_coeffs = np.zeros((4,1))
    
    def detect_markers(self, frame):
        """Detect ArUco markers in frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)
        
        markers = {}
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                # Calculate center
                corner = corners[i][0]
                center_x = np.mean(corner[:, 0])
                center_y = np.mean(corner[:, 1])
                
                # Calculate size (diagonal)
                size = np.linalg.norm(corner[0] - corner[2])
                
                # Estimate distance (rough approximation)
                focal_length = 800  # Approximate focal length
                real_size_pixels = self.marker_size_cm * 10  # Convert to mm
                distance = (focal_length * self.marker_size_cm) / size if size > 0 else 0
                
                markers[int(marker_id)] = {
                    'center': (center_x, center_y),
                    'size': size,
                    'distance': distance,
                    'corners': corner
                }
        
        return markers
    
    def draw_markers(self, frame, markers):
        """Draw detected markers on frame."""
        for marker_id, info in markers.items():
            # Draw marker outline
            corners = np.int32([info['corners']])
            cv2.polylines(frame, corners, True, (0, 255, 0), 2)
            
            # Draw ID
            center = tuple(map(int, info['center']))
            cv2.putText(frame, f"ID: {marker_id}", 
                       (center[0] - 20, center[1] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Draw distance
            cv2.putText(frame, f"{info['distance']:.1f}cm",
                       (center[0] - 20, center[1] + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        return frame

@dataclass
class AlignConfig:
    """Alignment configuration."""
    target_distance_cm: float = 30.0
    target_x_ratio: float = 0.5
    tolerance_x_pixels: int = 20
    tolerance_distance_cm: float = 5.0
    search_speed: int = 20
    max_speed: int = 35
    min_speed: int = 10
    kp_x: float = 0.1
    kp_distance: float = 1.2
    invert_forward: bool = True  # Set True if robot goes backward when it should go forward

class SimpleAligner:
    """Simplified aligner for Pi 5."""
    
    def __init__(self, config: AlignConfig = None):
        self.config = config or AlignConfig()
        self.camera = None
        self.detector = None
        self.left_motor = None
        self.right_motor = None
        
        self._init_hardware()
    
    def _init_hardware(self):
        """Initialize hardware."""
        # Camera
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                self.detector = SimpleArUcoDetector()
                print("[OK] Camera initialized")
            else:
                print("[ERROR] Camera not available")
                return False
        except Exception as e:
            print(f"[ERROR] Camera init failed: {e}")
            return False
        
        # Motors - matching remote_control_gui.py configuration
        if HARDWARE_AVAILABLE:
            try:
                # Note: RIGHT_MOTOR pins actually control left motor (pins are swapped)
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
                print("[OK] Motors initialized")
                
            except Exception as e:
                print(f"[ERROR] Motor init failed: {e}")
                return False
        else:
            print("[INFO] Motors in simulation mode")
        
        return True
    
    def set_motors(self, left: float, right: float):
        """Set motor speeds."""
        left = np.clip(left, -self.config.max_speed, self.config.max_speed)
        right = np.clip(right, -self.config.max_speed, self.config.max_speed)
        
        if 0 < abs(left) < self.config.min_speed:
            left = self.config.min_speed * np.sign(left)
        if 0 < abs(right) < self.config.min_speed:
            right = self.config.min_speed * np.sign(right)
        
        if HARDWARE_AVAILABLE and self.left_motor and self.right_motor:
            self.left_motor.drive(left)
            self.right_motor.drive(right)
        else:
            print(f"Motors: L={left:+.1f}% R={right:+.1f}%", end='\r')
    
    def stop(self):
        """Stop motors."""
        self.set_motors(0, 0)
    
    def search_marker(self, marker_id: int, timeout: float = 10) -> bool:
        """Search for marker."""
        print(f"Searching for marker {marker_id}...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if marker_id in markers:
                print(f"Found marker {marker_id}")
                self.stop()
                return True
            
            self.set_motors(-self.config.search_speed, self.config.search_speed)
            time.sleep(0.05)
        
        self.stop()
        print(f"Marker {marker_id} not found")
        return False
    
    def align_with_marker(self, marker_id: int) -> bool:
        """Align with marker."""
        if not self.camera or not self.detector:
            print("[ERROR] Camera not initialized")
            return False
        
        if not self.search_marker(marker_id):
            return False
        
        print(f"Aligning with marker {marker_id}")
        print(f"Target: {self.config.target_distance_cm}cm")
        
        stable_count = 0
        required_stable = 5
        
        for _ in range(300):  # Max 15 seconds
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if marker_id not in markers:
                print("Lost marker, searching...")
                if not self.search_marker(marker_id, timeout=5):
                    return False
                continue
            
            marker = markers[marker_id]
            frame_height, frame_width = frame.shape[:2]
            
            # Calculate errors
            target_x = self.config.target_x_ratio * frame_width
            x_error = target_x - marker['center'][0]  # Positive = marker is left of target
            
            # Distance error: positive when too far, negative when too close
            # We want to move forward (positive speed) when too far
            distance_error = marker['distance'] - self.config.target_distance_cm
            
            # Check if aligned
            if (abs(x_error) <= self.config.tolerance_x_pixels and
                abs(distance_error) <= self.config.tolerance_distance_cm):
                stable_count += 1
                print(f"Aligned! ({stable_count}/{required_stable})")
                
                if stable_count >= required_stable:
                    self.stop()
                    print("[SUCCESS] Alignment complete!")
                    return True
            else:
                stable_count = 0
            
            # Simple P control
            turn = self.config.kp_x * x_error
            forward = self.config.kp_distance * distance_error
            
            # Invert forward direction if needed (when robot goes backward instead of forward)
            if self.config.invert_forward:
                forward = -forward
            
            left = forward - turn
            right = forward + turn
            
            self.set_motors(left, right)
            
            print(f"X err: {x_error:+.0f}px, Dist err: {distance_error:+.1f}cm", end='\r')
            
            time.sleep(0.05)
        
        self.stop()
        print("\n[TIMEOUT] Alignment timeout")
        return False
    
    def test_camera(self):
        """Test camera and marker detection."""
        print("Camera test - press 'q' to quit")
        
        while True:
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            # Draw markers
            frame = self.detector.draw_markers(frame, markers)
            
            # Show frame
            cv2.imshow('Camera Test', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()
    
    def cleanup(self):
        """Clean up resources."""
        self.stop()
        
        if self.camera:
            self.camera.stop()
        
        if HARDWARE_AVAILABLE:
            if self.left_motor:
                self.left_motor.disable()
                self.left_motor.cleanup()
            if self.right_motor:
                self.right_motor.disable()
                self.right_motor.cleanup()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Simple ArUco Aligner for Pi 5')
    parser.add_argument('marker_id', type=int, nargs='?', help='Marker ID to align with')
    parser.add_argument('-d', '--distance', type=float, default=30.0, help='Target distance (cm)')
    parser.add_argument('-t', '--test', action='store_true', help='Test camera and detection')
    
    args = parser.parse_args()
    
    config = AlignConfig(target_distance_cm=args.distance)
    aligner = SimpleAligner(config)
    
    try:
        if args.test:
            aligner.test_camera()
        elif args.marker_id is not None:
            success = aligner.align_with_marker(args.marker_id)
            return 0 if success else 1
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n[STOPPED] User interrupt")
    finally:
        aligner.cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())