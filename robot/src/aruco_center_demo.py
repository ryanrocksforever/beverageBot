#!/usr/bin/env python3
"""ArUco marker centering demonstration with GUI for BevBot."""

import cv2
import numpy as np
import time
import logging
import threading
import signal
import sys
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from queue import Queue
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: gpiozero not available, running in simulation mode")

from .camera import CameraInterface
if HARDWARE_AVAILABLE:
    from .pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    from .motor_gpiozero import BTS7960Motor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MarkerInfo:
    """Information about detected ArUco marker."""
    id: int
    center: Tuple[float, float]
    corners: np.ndarray
    size: float
    distance: float  # Estimated distance based on marker size

class MotorController:
    """Motor control for centering behavior."""
    
    def __init__(self, simulation_mode: bool = False):
        """Initialize motor controller."""
        self.simulation_mode = simulation_mode or not HARDWARE_AVAILABLE
        self.left_motor = None
        self.right_motor = None
        self.current_left_speed = 0
        self.current_right_speed = 0
        
        if not self.simulation_mode:
            self._init_motors()
    
    def _init_motors(self):
        """Initialize physical motors."""
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
    
    def set_speeds(self, left_speed: float, right_speed: float):
        """Set motor speeds."""
        self.current_left_speed = left_speed
        self.current_right_speed = right_speed
        
        if not self.simulation_mode:
            try:
                self.left_motor.drive(left_speed)
                self.right_motor.drive(right_speed)
            except Exception as e:
                logger.error(f"Error setting motor speeds: {e}")
    
    def stop(self):
        """Stop all motors."""
        self.set_speeds(0, 0)
    
    def cleanup(self):
        """Clean up motor resources."""
        self.stop()
        if not self.simulation_mode:
            try:
                if self.left_motor:
                    self.left_motor.disable()
                    self.left_motor.cleanup()
                if self.right_motor:
                    self.right_motor.disable()
                    self.right_motor.cleanup()
            except Exception as e:
                logger.error(f"Error during motor cleanup: {e}")

class ArUcoDetector:
    """ArUco marker detection and tracking."""
    
    def __init__(self, marker_size_cm: float = 10.0):
        """Initialize ArUco detector.
        
        Args:
            marker_size_cm: Real-world marker size in centimeters
        """
        self.marker_size_cm = marker_size_cm
        
        # Use 4x4 ArUco dictionary (smaller markers, easier to print)
        self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters_create()
        
        # Camera calibration placeholder (would need actual calibration)
        # Using approximate values for Raspberry Pi camera
        self.camera_matrix = np.array([
            [600, 0, 320],
            [0, 600, 240],
            [0, 0, 1]
        ], dtype=float)
        
        self.dist_coeffs = np.zeros((4, 1))
    
    def detect_markers(self, frame: np.ndarray) -> Dict[int, MarkerInfo]:
        """Detect ArUco markers in frame.
        
        Returns:
            Dictionary of marker ID to MarkerInfo
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )
        
        markers = {}
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                marker_corners = corners[i][0]
                
                # Calculate center
                center_x = np.mean(marker_corners[:, 0])
                center_y = np.mean(marker_corners[:, 1])
                
                # Calculate size (average of width and height)
                width = np.linalg.norm(marker_corners[0] - marker_corners[1])
                height = np.linalg.norm(marker_corners[1] - marker_corners[2])
                size = (width + height) / 2
                
                # Estimate distance (rough approximation)
                # Assuming 10cm marker appears as ~100 pixels at 50cm distance
                focal_length = 500  # Approximate focal length in pixels
                distance = (self.marker_size_cm * focal_length) / size
                
                markers[marker_id] = MarkerInfo(
                    id=marker_id,
                    center=(center_x, center_y),
                    corners=marker_corners,
                    size=size,
                    distance=distance
                )
        
        return markers
    
    def draw_markers(self, frame: np.ndarray, markers: Dict[int, MarkerInfo]) -> np.ndarray:
        """Draw detected markers on frame."""
        annotated = frame.copy()
        
        for marker_id, info in markers.items():
            # Draw marker outline
            corners_int = info.corners.astype(int)
            cv2.polylines(annotated, [corners_int], True, (0, 255, 0), 2)
            
            # Draw center
            center_int = tuple(map(int, info.center))
            cv2.circle(annotated, center_int, 5, (0, 0, 255), -1)
            
            # Draw ID and distance
            text = f"ID:{marker_id} D:{info.distance:.1f}cm"
            cv2.putText(annotated, text, 
                       (corners_int[0][0], corners_int[0][1] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw center line
        h, w = frame.shape[:2]
        cv2.line(annotated, (w//2, 0), (w//2, h), (255, 0, 0), 1)
        
        return annotated

class CenteringController:
    """PID-based centering controller."""
    
    def __init__(self, target_distance_cm: float = 30.0):
        """Initialize centering controller.
        
        Args:
            target_distance_cm: Target distance to maintain from marker
        """
        self.target_distance = target_distance_cm
        
        # PID gains (tunable)
        self.kp_heading = 0.15  # Proportional gain for heading
        self.kp_distance = 0.8   # Proportional gain for distance
        self.ki_heading = 0.01  # Integral gain for heading
        self.ki_distance = 0.05  # Integral gain for distance
        
        # Integral terms
        self.heading_integral = 0
        self.distance_integral = 0
        
        # Deadband thresholds
        self.heading_deadband = 20  # pixels
        self.distance_deadband = 5  # cm
        
        # Speed limits
        self.max_speed = 40
        self.min_speed = 15
    
    def compute_control(self, marker: MarkerInfo, frame_width: int) -> Tuple[float, float]:
        """Compute motor speeds to center on marker.
        
        Returns:
            Tuple of (left_speed, right_speed) in range -100 to 100
        """
        if marker is None:
            return 0, 0
        
        # Calculate errors
        center_x = frame_width / 2
        heading_error = marker.center[0] - center_x
        distance_error = self.target_distance - marker.distance
        
        # Update integral terms
        self.heading_integral += heading_error * 0.1  # dt ~ 0.1s
        self.distance_integral += distance_error * 0.1
        
        # Clamp integral terms
        self.heading_integral = np.clip(self.heading_integral, -100, 100)
        self.distance_integral = np.clip(self.distance_integral, -50, 50)
        
        # Apply deadband
        if abs(heading_error) < self.heading_deadband:
            heading_error = 0
            self.heading_integral *= 0.9  # Decay integral
        
        if abs(distance_error) < self.distance_deadband:
            distance_error = 0
            self.distance_integral *= 0.9  # Decay integral
        
        # Calculate control signals
        turn_control = (self.kp_heading * heading_error + 
                       self.ki_heading * self.heading_integral)
        
        forward_control = (self.kp_distance * distance_error + 
                          self.ki_distance * self.distance_integral)
        
        # Convert to motor speeds
        left_speed = forward_control + turn_control
        right_speed = forward_control - turn_control
        
        # Clamp speeds
        left_speed = np.clip(left_speed, -self.max_speed, self.max_speed)
        right_speed = np.clip(right_speed, -self.max_speed, self.max_speed)
        
        # Apply minimum speed threshold
        if abs(left_speed) < self.min_speed and left_speed != 0:
            left_speed = self.min_speed if left_speed > 0 else -self.min_speed
        if abs(right_speed) < self.min_speed and right_speed != 0:
            right_speed = self.min_speed if right_speed > 0 else -self.min_speed
        
        return left_speed, right_speed

class ArUcoCenterGUI:
    """GUI for ArUco centering demonstration."""
    
    def __init__(self, root: tk.Tk):
        """Initialize GUI."""
        self.root = root
        self.root.title("BevBot ArUco Centering Demo")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Components
        self.camera = None
        self.detector = ArUcoDetector()
        self.controller = CenteringController()
        self.motors = MotorController()
        
        # State
        self.running = False
        self.tracking_enabled = False
        self.target_marker_id = None
        self.current_frame = None
        self.frame_queue = Queue(maxsize=2)
        
        # Setup GUI
        self._setup_gui()
        
        # Start camera
        self._init_camera()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        # Start GUI update
        self._update_gui()
    
    def _setup_gui(self):
        """Setup GUI components."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Video display
        self.video_label = ttk.Label(main_frame)
        self.video_label.grid(row=0, column=0, columnspan=2, pady=5)
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Start/Stop button
        self.start_button = ttk.Button(control_frame, text="Start Tracking", 
                                      command=self.toggle_tracking)
        self.start_button.grid(row=0, column=0, padx=5)
        
        # Stop motors button
        self.stop_button = ttk.Button(control_frame, text="Stop Motors", 
                                     command=self.stop_motors)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        # Target marker selection
        ttk.Label(control_frame, text="Target Marker ID:").grid(row=0, column=2, padx=5)
        self.marker_var = tk.StringVar(value="Any")
        self.marker_combo = ttk.Combobox(control_frame, textvariable=self.marker_var, 
                                        width=10, state="readonly")
        self.marker_combo['values'] = ["Any"] + [str(i) for i in range(10)]
        self.marker_combo.grid(row=0, column=3, padx=5)
        self.marker_combo.bind("<<ComboboxSelected>>", self.on_marker_selected)
        
        # Status panel
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Status labels
        self.status_labels = {}
        status_items = [
            ("Camera", "camera_status"),
            ("Marker", "marker_status"),
            ("Distance", "distance_status"),
            ("Motors", "motor_status"),
            ("Mode", "mode_status")
        ]
        
        for i, (label, key) in enumerate(status_items):
            ttk.Label(status_frame, text=f"{label}:").grid(row=i//2, column=(i%2)*2, 
                                                           sticky=tk.W, padx=5, pady=2)
            self.status_labels[key] = ttk.Label(status_frame, text="--", 
                                               foreground="gray")
            self.status_labels[key].grid(row=i//2, column=(i%2)*2+1, 
                                        sticky=tk.W, padx=5, pady=2)
        
        # Motor speed display
        speed_frame = ttk.LabelFrame(main_frame, text="Motor Speeds", padding="10")
        speed_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # Speed bars
        ttk.Label(speed_frame, text="Left:").grid(row=0, column=0, sticky=tk.W)
        self.left_speed_var = tk.DoubleVar()
        self.left_speed_bar = ttk.Progressbar(speed_frame, variable=self.left_speed_var,
                                             maximum=100, length=200)
        self.left_speed_bar.grid(row=0, column=1, padx=5)
        self.left_speed_label = ttk.Label(speed_frame, text="0%")
        self.left_speed_label.grid(row=0, column=2)
        
        ttk.Label(speed_frame, text="Right:").grid(row=1, column=0, sticky=tk.W)
        self.right_speed_var = tk.DoubleVar()
        self.right_speed_bar = ttk.Progressbar(speed_frame, variable=self.right_speed_var,
                                              maximum=100, length=200)
        self.right_speed_bar.grid(row=1, column=1, padx=5)
        self.right_speed_label = ttk.Label(speed_frame, text="0%")
        self.right_speed_label.grid(row=1, column=2)
    
    def _init_camera(self):
        """Initialize camera."""
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                self.running = True
                self.status_labels["camera_status"].config(text="Ready", foreground="green")
            else:
                self.status_labels["camera_status"].config(text="Not found", foreground="red")
                logger.error("Camera not available")
        except Exception as e:
            self.status_labels["camera_status"].config(text="Error", foreground="red")
            logger.error(f"Failed to initialize camera: {e}")
    
    def _processing_loop(self):
        """Main processing loop (runs in separate thread)."""
        while True:
            if self.running and self.camera:
                try:
                    # Capture frame
                    frame, _ = self.camera.capture_frame()
                    
                    # Detect markers
                    markers = self.detector.detect_markers(frame)
                    
                    # Select target marker
                    target_marker = None
                    if markers:
                        if self.target_marker_id is None:
                            # Use closest marker
                            target_marker = min(markers.values(), 
                                              key=lambda m: m.distance)
                        elif self.target_marker_id in markers:
                            target_marker = markers[self.target_marker_id]
                    
                    # Compute control
                    if self.tracking_enabled and target_marker:
                        left_speed, right_speed = self.controller.compute_control(
                            target_marker, frame.shape[1]
                        )
                        self.motors.set_speeds(left_speed, right_speed)
                    else:
                        self.motors.stop()
                    
                    # Annotate frame
                    annotated_frame = self.detector.draw_markers(frame, markers)
                    
                    # Add tracking indicator
                    if self.tracking_enabled and target_marker:
                        cv2.putText(annotated_frame, "TRACKING", (10, 30),
                                  cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    
                    # Queue frame for display
                    if not self.frame_queue.full():
                        self.frame_queue.put((annotated_frame, markers, target_marker))
                    
                except Exception as e:
                    logger.error(f"Processing error: {e}")
            
            time.sleep(0.05)  # ~20 FPS
    
    def _update_gui(self):
        """Update GUI with latest frame and status."""
        try:
            if not self.frame_queue.empty():
                frame, markers, target_marker = self.frame_queue.get_nowait()
                
                # Convert frame to PhotoImage
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (640, 480))
                img = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image=img)
                
                # Update video display
                self.video_label.config(image=photo)
                self.video_label.image = photo  # Keep reference
                
                # Update status
                if target_marker:
                    self.status_labels["marker_status"].config(
                        text=f"ID {target_marker.id}", foreground="green"
                    )
                    self.status_labels["distance_status"].config(
                        text=f"{target_marker.distance:.1f} cm", foreground="blue"
                    )
                else:
                    self.status_labels["marker_status"].config(
                        text="Not found", foreground="orange"
                    )
                    self.status_labels["distance_status"].config(
                        text="--", foreground="gray"
                    )
                
                # Update motor status
                if self.tracking_enabled:
                    self.status_labels["motor_status"].config(
                        text="Active", foreground="green"
                    )
                else:
                    self.status_labels["motor_status"].config(
                        text="Stopped", foreground="gray"
                    )
                
                # Update mode
                if self.motors.simulation_mode:
                    self.status_labels["mode_status"].config(
                        text="Simulation", foreground="orange"
                    )
                else:
                    self.status_labels["mode_status"].config(
                        text="Hardware", foreground="green"
                    )
                
                # Update speed displays
                self.left_speed_var.set(abs(self.motors.current_left_speed))
                self.right_speed_var.set(abs(self.motors.current_right_speed))
                self.left_speed_label.config(text=f"{self.motors.current_left_speed:.0f}%")
                self.right_speed_label.config(text=f"{self.motors.current_right_speed:.0f}%")
        
        except Exception as e:
            logger.debug(f"GUI update error: {e}")
        
        # Schedule next update
        self.root.after(50, self._update_gui)
    
    def toggle_tracking(self):
        """Toggle tracking mode."""
        self.tracking_enabled = not self.tracking_enabled
        if self.tracking_enabled:
            self.start_button.config(text="Stop Tracking")
            logger.info("Tracking enabled")
        else:
            self.start_button.config(text="Start Tracking")
            self.motors.stop()
            logger.info("Tracking disabled")
    
    def stop_motors(self):
        """Emergency stop."""
        self.tracking_enabled = False
        self.motors.stop()
        self.start_button.config(text="Start Tracking")
        logger.info("Emergency stop")
    
    def on_marker_selected(self, event=None):
        """Handle marker selection."""
        selection = self.marker_var.get()
        if selection == "Any":
            self.target_marker_id = None
        else:
            self.target_marker_id = int(selection)
        logger.info(f"Target marker: {selection}")
    
    def on_closing(self):
        """Handle window closing."""
        logger.info("Shutting down...")
        self.running = False
        self.tracking_enabled = False
        self.motors.cleanup()
        if self.camera:
            self.camera.stop()
        self.root.destroy()

def main():
    """Main entry point."""
    # Setup signal handler
    def signal_handler(sig, frame):
        logger.info("Interrupt received, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run GUI
    root = tk.Tk()
    app = ArUcoCenterGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        app.on_closing()

if __name__ == "__main__":
    main()