#!/usr/bin/env python3
"""
Simplified ArUco Marker Alignment Tool
Optimized for Raspberry Pi 5 performance
Focus on reliable, precise alignment without GUI overhead
"""

import cv2
import numpy as np
import time
import json
import os
import sys
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, asdict

# Hardware detection
try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    from motor_gpiozero import BTS7960Motor
    from pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: Running in simulation mode")

from camera import CameraInterface
from aruco_center_demo import ArUcoDetector

@dataclass
class AlignmentConfig:
    """Configuration for alignment behavior."""
    # Target settings
    target_distance_cm: float = 30.0
    target_x_ratio: float = 0.5  # 0.5 = center
    
    # Tolerances
    tolerance_x_pixels: int = 15
    tolerance_distance_cm: float = 3.0
    
    # Control parameters
    search_speed: int = 20
    max_speed: int = 40
    min_speed: int = 10
    
    # PID gains - tuned for Pi 5
    kp_x: float = 0.12      # Proportional gain for X alignment
    ki_x: float = 0.005     # Integral gain for X
    kd_x: float = 0.02      # Derivative gain for X
    
    kp_distance: float = 1.5  # Proportional gain for distance
    ki_distance: float = 0.05  # Integral gain for distance
    kd_distance: float = 0.1   # Derivative gain for distance
    
    # Alignment verification
    required_stable_frames: int = 5  # Frames to hold position
    max_alignment_time: float = 30.0  # Maximum time to attempt alignment
    
    def save(self, filename: str = "alignment_config.json"):
        """Save configuration to file."""
        with open(filename, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, filename: str = "alignment_config.json"):
        """Load configuration from file."""
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return cls(**json.load(f))
        return cls()

class SimpleAligner:
    """Simplified alignment system optimized for Pi 5."""
    
    def __init__(self, config: AlignmentConfig = None):
        self.config = config or AlignmentConfig()
        self.camera = None
        self.detector = None
        self.left_motor = None
        self.right_motor = None
        
        # PID state
        self.x_integral = 0
        self.x_last_error = 0
        self.distance_integral = 0
        self.distance_last_error = 0
        self.last_update_time = time.time()
        
        # Initialize hardware
        self._init_hardware()
        
    def _init_hardware(self):
        """Initialize hardware components."""
        # Camera
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                self.detector = ArUcoDetector(marker_size_cm=10.0)
                print("[OK] Camera initialized")
            else:
                print("[ERROR] Camera not available")
                return False
        except Exception as e:
            print(f"[ERROR] Camera init failed: {e}")
            return False
        
        # Motors
        if HARDWARE_AVAILABLE:
            try:
                self.left_motor = BTS7960Motor(
                    r_en_pin=RIGHT_MOTOR_R_EN,
                    l_en_pin=RIGHT_MOTOR_L_EN,
                    rpwm_pin=RIGHT_MOTOR_RPWM,
                    lpwm_pin=RIGHT_MOTOR_LPWM,
                    name="left",
                    invert=True
                )
                
                self.right_motor = BTS7960Motor(
                    r_en_pin=LEFT_MOTOR_R_EN,
                    l_en_pin=LEFT_MOTOR_L_EN,
                    rpwm_pin=LEFT_MOTOR_RPWM,
                    lpwm_pin=LEFT_MOTOR_LPWM,
                    name="right",
                    invert=False
                )
                
                self.left_motor.enable()
                self.right_motor.enable()
                print("[OK] Motors initialized")
                
            except Exception as e:
                print(f"[ERROR] Motor init failed: {e}")
                return False
        
        return True
    
    def set_motors(self, left: float, right: float):
        """Set motor speeds with limits."""
        # Apply limits
        left = np.clip(left, -self.config.max_speed, self.config.max_speed)
        right = np.clip(right, -self.config.max_speed, self.config.max_speed)
        
        # Apply minimum threshold
        if 0 < abs(left) < self.config.min_speed:
            left = self.config.min_speed * np.sign(left)
        if 0 < abs(right) < self.config.min_speed:
            right = self.config.min_speed * np.sign(right)
        
        if HARDWARE_AVAILABLE and self.left_motor and self.right_motor:
            self.left_motor.drive(left)
            self.right_motor.drive(right)
        else:
            # Simulation output
            print(f"Motors: L={left:+.1f}% R={right:+.1f}%", end='\r')
    
    def stop(self):
        """Stop all motors."""
        self.set_motors(0, 0)
    
    def search_marker(self, marker_id: int, timeout: float = 10) -> bool:
        """Search for marker by rotating."""
        print(f"Searching for marker {marker_id}...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if marker_id in markers:
                print(f"Found marker {marker_id}")
                self.stop()
                return True
            
            # Rotate slowly
            self.set_motors(-self.config.search_speed, self.config.search_speed)
            time.sleep(0.05)
        
        self.stop()
        print(f"Marker {marker_id} not found")
        return False
    
    def calculate_control(self, x_error: float, distance_error: float, dt: float) -> Tuple[float, float]:
        """Calculate PID control for motors."""
        # X-axis PID
        self.x_integral += x_error * dt
        self.x_integral = np.clip(self.x_integral, -100, 100)  # Anti-windup
        
        x_derivative = (x_error - self.x_last_error) / dt if dt > 0 else 0
        self.x_last_error = x_error
        
        x_control = (
            self.config.kp_x * x_error +
            self.config.ki_x * self.x_integral +
            self.config.kd_x * x_derivative
        )
        
        # Distance PID
        self.distance_integral += distance_error * dt
        self.distance_integral = np.clip(self.distance_integral, -100, 100)
        
        distance_derivative = (distance_error - self.distance_last_error) / dt if dt > 0 else 0
        self.distance_last_error = distance_error
        
        distance_control = (
            self.config.kp_distance * distance_error +
            self.config.ki_distance * self.distance_integral +
            self.config.kd_distance * distance_derivative
        )
        
        # Combine controls
        left = distance_control - x_control
        right = distance_control + x_control
        
        return left, right
    
    def align_with_marker(self, marker_id: int, verbose: bool = True) -> bool:
        """Main alignment routine."""
        if not self.camera or not self.detector:
            print("[ERROR] Camera not initialized")
            return False
        
        # Reset PID state
        self.x_integral = 0
        self.x_last_error = 0
        self.distance_integral = 0
        self.distance_last_error = 0
        self.last_update_time = time.time()
        
        # Search for marker
        if not self.search_marker(marker_id):
            return False
        
        print(f"Aligning with marker {marker_id}")
        print(f"Target: {self.config.target_distance_cm}cm, X={self.config.target_x_ratio:.2f}")
        
        start_time = time.time()
        stable_count = 0
        
        while time.time() - start_time < self.config.max_alignment_time:
            # Capture and detect
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
            x_error = target_x - marker.center[0]
            distance_error = self.config.target_distance_cm - marker.distance
            
            # Check if aligned
            if (abs(x_error) <= self.config.tolerance_x_pixels and
                abs(distance_error) <= self.config.tolerance_distance_cm):
                stable_count += 1
                if verbose:
                    print(f"Aligned! Holding... ({stable_count}/{self.config.required_stable_frames})")
                
                if stable_count >= self.config.required_stable_frames:
                    self.stop()
                    print("[SUCCESS] Alignment complete!")
                    return True
            else:
                stable_count = 0
            
            # Calculate control
            current_time = time.time()
            dt = current_time - self.last_update_time
            self.last_update_time = current_time
            
            left, right = self.calculate_control(x_error, distance_error, dt)
            self.set_motors(left, right)
            
            if verbose:
                print(f"X err: {x_error:+.0f}px, Dist err: {distance_error:+.1f}cm, "
                      f"Motors: L={left:+.0f}% R={right:+.0f}%", end='\r')
            
            time.sleep(0.05)  # 20Hz control loop
        
        self.stop()
        print("[TIMEOUT] Alignment timeout")
        return False
    
    def save_position(self, marker_id: int, name: str = None) -> bool:
        """Save current position relative to visible marker."""
        frame, _ = self.camera.capture_frame()
        markers = self.detector.detect_markers(frame)
        
        if marker_id not in markers:
            print(f"Marker {marker_id} not visible")
            return False
        
        marker = markers[marker_id]
        frame_height, frame_width = frame.shape[:2]
        
        position = {
            'marker_id': marker_id,
            'name': name or f"Position_{marker_id}",
            'x_ratio': marker.center[0] / frame_width,
            'distance_cm': marker.distance,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Load existing positions
        positions_file = 'saved_positions.json'
        positions = {}
        if os.path.exists(positions_file):
            with open(positions_file, 'r') as f:
                positions = json.load(f)
        
        positions[str(marker_id)] = position
        
        with open(positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
        
        print(f"Saved position for marker {marker_id}")
        print(f"  X ratio: {position['x_ratio']:.3f}")
        print(f"  Distance: {position['distance_cm']:.1f} cm")
        
        return True
    
    def load_position(self, marker_id: int) -> bool:
        """Load saved position for marker."""
        positions_file = 'saved_positions.json'
        
        if not os.path.exists(positions_file):
            print("No saved positions found")
            return False
        
        with open(positions_file, 'r') as f:
            positions = json.load(f)
        
        if str(marker_id) not in positions:
            print(f"No saved position for marker {marker_id}")
            return False
        
        pos = positions[str(marker_id)]
        self.config.target_x_ratio = pos['x_ratio']
        self.config.target_distance_cm = pos['distance_cm']
        
        print(f"Loaded position for marker {marker_id}: {pos['name']}")
        print(f"  X ratio: {pos['x_ratio']:.3f}")
        print(f"  Distance: {pos['distance_cm']:.1f} cm")
        
        return True
    
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
    """Command line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple ArUco Alignment Tool')
    parser.add_argument('marker_id', type=int, help='Marker ID to align with')
    parser.add_argument('-d', '--distance', type=float, default=30.0,
                       help='Target distance in cm (default: 30)')
    parser.add_argument('-x', '--x-position', type=float, default=0.5,
                       help='X position ratio 0-1 (default: 0.5 = center)')
    parser.add_argument('-s', '--save', action='store_true',
                       help='Save current position')
    parser.add_argument('-l', '--load', action='store_true',
                       help='Load saved position')
    parser.add_argument('-c', '--config', type=str,
                       help='Load config file')
    parser.add_argument('--tune', action='store_true',
                       help='Show PID tuning interface')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        config = AlignmentConfig.load(args.config)
    else:
        config = AlignmentConfig()
    
    # Override with command line args
    if not args.load:
        config.target_distance_cm = args.distance
        config.target_x_ratio = args.x_position
    
    # Create aligner
    aligner = SimpleAligner(config)
    
    try:
        if args.save:
            # Save current position
            success = aligner.save_position(args.marker_id)
            
        elif args.load:
            # Load and align to saved position
            if aligner.load_position(args.marker_id):
                success = aligner.align_with_marker(args.marker_id)
            else:
                success = False
                
        elif args.tune:
            # Interactive tuning mode
            print("PID Tuning Mode")
            print("Current gains:")
            print(f"  X-axis: P={config.kp_x} I={config.ki_x} D={config.kd_x}")
            print(f"  Distance: P={config.kp_distance} I={config.ki_distance} D={config.kd_distance}")
            print("\nAdjust gains and test alignment")
            
            while True:
                cmd = input("\nCommand (align/set/save/quit): ").lower()
                
                if cmd == 'quit':
                    break
                elif cmd == 'align':
                    aligner.align_with_marker(args.marker_id)
                elif cmd == 'set':
                    param = input("Parameter (kp_x/ki_x/kd_x/kp_d/ki_d/kd_d): ")
                    value = float(input("Value: "))
                    
                    if param == 'kp_x':
                        config.kp_x = value
                    elif param == 'ki_x':
                        config.ki_x = value
                    elif param == 'kd_x':
                        config.kd_x = value
                    elif param == 'kp_d':
                        config.kp_distance = value
                    elif param == 'ki_d':
                        config.ki_distance = value
                    elif param == 'kd_d':
                        config.kd_distance = value
                    
                    aligner.config = config
                    print(f"Set {param} = {value}")
                    
                elif cmd == 'save':
                    config.save()
                    print("Configuration saved")
                    
        else:
            # Normal alignment
            success = aligner.align_with_marker(args.marker_id)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n[STOPPED] User interrupt")
        return 1
        
    finally:
        aligner.cleanup()

if __name__ == "__main__":
    sys.exit(main())