#!/usr/bin/env python3
"""
ArUco Precision Alignment Tool
A robust system for precise robot alignment with ArUco markers
Includes PID control, visual feedback, and position saving
"""

import cv2
import numpy as np
import time
import logging
import json
import os
import threading
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: gpiozero not available, running in simulation mode")

from camera import CameraInterface
from aruco_center_demo import MarkerInfo, ArUcoDetector
from camera_config import (
    CAMERA_MATRIX, DISTORTION_COEFFS, MARKER_SIZE_CM,
    DEFAULT_TARGET_DISTANCE_CM
)

if HARDWARE_AVAILABLE:
    from pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM
    )
    from motor_gpiozero import BTS7960Motor

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlignmentState(Enum):
    """States for the alignment process."""
    IDLE = "idle"
    SEARCHING = "searching"
    COARSE_ALIGNMENT = "coarse_alignment"
    FINE_ALIGNMENT = "fine_alignment"
    ALIGNED = "aligned"
    ERROR = "error"

@dataclass
class AlignmentTarget:
    """Target position for alignment."""
    marker_id: int
    name: str
    target_x_ratio: float  # Target X position as ratio of frame width (0.5 = center)
    target_y_ratio: float  # Target Y position as ratio of frame height
    target_distance_cm: float  # Target distance from marker
    tolerance_x_pixels: int = 10
    tolerance_y_pixels: int = 10
    tolerance_distance_cm: float = 2.0
    tolerance_angle_deg: float = 3.0
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class PIDController:
    """PID controller for smooth control."""
    
    def __init__(self, kp: float, ki: float, kd: float, 
                 output_limits: Tuple[float, float] = (-100, 100)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limits = output_limits
        
        self.integral = 0
        self.last_error = 0
        self.last_time = time.time()
        
    def reset(self):
        """Reset controller state."""
        self.integral = 0
        self.last_error = 0
        self.last_time = time.time()
        
    def update(self, error: float) -> float:
        """Update PID controller and return output."""
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            dt = 0.01
        
        # Proportional term
        p_term = self.kp * error
        
        # Integral term with anti-windup
        self.integral += error * dt
        self.integral = np.clip(self.integral, -50, 50)
        i_term = self.ki * self.integral
        
        # Derivative term
        d_term = self.kd * (error - self.last_error) / dt
        
        # Calculate output
        output = p_term + i_term + d_term
        
        # Apply limits
        output = np.clip(output, self.output_limits[0], self.output_limits[1])
        
        # Update state
        self.last_error = error
        self.last_time = current_time
        
        return output

class RobustAligner:
    """Robust alignment system with multiple control modes."""
    
    def __init__(self, simulation_mode: bool = False):
        self.simulation_mode = simulation_mode or not HARDWARE_AVAILABLE
        
        # Hardware
        self.left_motor = None
        self.right_motor = None
        self.camera = None
        self.detector = None
        
        # Control systems
        self.x_controller = PIDController(kp=0.15, ki=0.01, kd=0.05, output_limits=(-40, 40))
        self.distance_controller = PIDController(kp=2.0, ki=0.1, kd=0.3, output_limits=(-50, 50))
        self.angle_controller = PIDController(kp=1.0, ki=0.05, kd=0.2, output_limits=(-30, 30))
        
        # State
        self.state = AlignmentState.IDLE
        self.current_target = None
        self.last_marker_info = None
        self.alignment_history = []
        
        # Settings
        self.use_fine_control = True
        self.max_speed = 50
        self.min_speed = 8
        self.search_speed = 20
        self.coarse_threshold = 0.7  # Switch to fine control when this close
        
        # Initialize hardware
        if not self.simulation_mode:
            self._init_hardware()
            
    def _init_hardware(self):
        """Initialize hardware components."""
        try:
            # Motors
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
            
            logger.info("Motors initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            self.simulation_mode = True
            
    def init_camera(self) -> bool:
        """Initialize camera and detector."""
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                self.detector = ArUcoDetector(marker_size_cm=MARKER_SIZE_CM)
                logger.info("Camera and detector initialized")
                return True
            else:
                logger.error("Camera not available")
                return False
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            return False
            
    def set_motor_speeds(self, left: float, right: float):
        """Set motor speeds with safety limits."""
        # Apply speed limits
        left = np.clip(left, -self.max_speed, self.max_speed)
        right = np.clip(right, -self.max_speed, self.max_speed)
        
        # Apply minimum threshold
        if abs(left) < self.min_speed and left != 0:
            left = self.min_speed if left > 0 else -self.min_speed
        if abs(right) < self.min_speed and right != 0:
            right = self.min_speed if right > 0 else -self.min_speed
            
        if not self.simulation_mode and self.left_motor and self.right_motor:
            self.left_motor.drive(left)
            self.right_motor.drive(right)
            
        return left, right
        
    def stop_motors(self):
        """Stop all motors."""
        self.set_motor_speeds(0, 0)
        
    def search_for_marker(self, marker_id: int, timeout: float = 10) -> bool:
        """Search for a specific marker by rotating."""
        self.state = AlignmentState.SEARCHING
        start_time = time.time()
        search_direction = 1
        
        while time.time() - start_time < timeout:
            # Capture and detect
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if marker_id in markers:
                logger.info(f"Found marker {marker_id}")
                self.stop_motors()
                return True
                
            # Rotate to search
            self.set_motor_speeds(-self.search_speed * search_direction, 
                                 self.search_speed * search_direction)
            time.sleep(0.1)
            
            # Change direction after half timeout
            if time.time() - start_time > timeout / 2 and search_direction == 1:
                search_direction = -1
                
        self.stop_motors()
        logger.warning(f"Marker {marker_id} not found after {timeout}s")
        return False
        
    def calculate_alignment_error(self, marker: MarkerInfo, target: AlignmentTarget, 
                                 frame_shape: Tuple[int, int]) -> Dict[str, float]:
        """Calculate all alignment errors."""
        frame_height, frame_width = frame_shape
        
        # Position errors
        target_x = target.target_x_ratio * frame_width
        target_y = target.target_y_ratio * frame_height
        
        x_error = target_x - marker.center[0]  # Positive = marker is left of target
        y_error = target_y - marker.center[1]  # Positive = marker is above target
        
        # Distance error
        distance_error = target.target_distance_cm - marker.distance
        
        # Angle error (if marker corners are available)
        angle_error = 0
        if hasattr(marker, 'corners') and marker.corners is not None:
            # Calculate marker orientation
            corners = marker.corners[0]
            # Use top edge to determine rotation
            top_edge = corners[0] - corners[1]
            angle = np.degrees(np.arctan2(top_edge[1], top_edge[0]))
            angle_error = angle  # Assuming target angle is 0
            
        return {
            'x_error': x_error,
            'y_error': y_error,
            'distance_error': distance_error,
            'angle_error': angle_error,
            'x_error_ratio': x_error / frame_width,
            'y_error_ratio': y_error / frame_height
        }
        
    def is_aligned(self, errors: Dict[str, float], target: AlignmentTarget) -> bool:
        """Check if robot is aligned within tolerances."""
        return (
            abs(errors['x_error']) <= target.tolerance_x_pixels and
            abs(errors['distance_error']) <= target.tolerance_distance_cm and
            abs(errors['angle_error']) <= target.tolerance_angle_deg
        )
        
    def calculate_motor_speeds(self, errors: Dict[str, float], mode: str = 'fine') -> Tuple[float, float]:
        """Calculate motor speeds based on errors and control mode."""
        if mode == 'coarse':
            # Simple proportional control for coarse alignment
            turn_speed = errors['x_error_ratio'] * 40
            forward_speed = errors['distance_error'] * 2
            
            left = forward_speed - turn_speed
            right = forward_speed + turn_speed
            
        else:  # fine control
            # Use PID controllers
            turn_control = self.x_controller.update(errors['x_error'])
            forward_control = self.distance_controller.update(errors['distance_error'])
            
            # Combine controls
            left = forward_control - turn_control
            right = forward_control + turn_control
            
            # Add angle correction if significant
            if abs(errors['angle_error']) > 5:
                angle_control = self.angle_controller.update(errors['angle_error'])
                left -= angle_control
                right += angle_control
                
        return left, right
        
    def align_with_marker(self, target: AlignmentTarget, timeout: float = 30, 
                         callback=None) -> bool:
        """Main alignment routine."""
        if not self.camera or not self.detector:
            logger.error("Camera not initialized")
            return False
            
        logger.info(f"Starting alignment with marker {target.marker_id}")
        self.current_target = target
        start_time = time.time()
        
        # Reset PID controllers
        self.x_controller.reset()
        self.distance_controller.reset()
        self.angle_controller.reset()
        
        # Search for marker first
        if not self.search_for_marker(target.marker_id, timeout=10):
            self.state = AlignmentState.ERROR
            return False
            
        self.state = AlignmentState.COARSE_ALIGNMENT
        aligned_count = 0
        required_aligned_frames = 10  # Must be aligned for this many consecutive frames
        
        while time.time() - start_time < timeout:
            # Capture and detect
            frame, _ = self.camera.capture_frame()
            markers = self.detector.detect_markers(frame)
            
            if target.marker_id not in markers:
                logger.warning("Lost marker, searching again...")
                if not self.search_for_marker(target.marker_id, timeout=5):
                    self.state = AlignmentState.ERROR
                    return False
                continue
                
            marker = markers[target.marker_id]
            self.last_marker_info = marker
            
            # Calculate errors
            errors = self.calculate_alignment_error(marker, target, frame.shape[:2])
            
            # Record history
            self.alignment_history.append({
                'time': time.time() - start_time,
                'errors': errors,
                'state': self.state.value
            })
            
            # Check if aligned
            if self.is_aligned(errors, target):
                aligned_count += 1
                if aligned_count >= required_aligned_frames:
                    logger.info("Alignment successful!")
                    self.state = AlignmentState.ALIGNED
                    self.stop_motors()
                    return True
            else:
                aligned_count = 0
                
            # Determine control mode
            if self.state == AlignmentState.COARSE_ALIGNMENT:
                if abs(errors['distance_error']) < 10 and abs(errors['x_error_ratio']) < 0.2:
                    self.state = AlignmentState.FINE_ALIGNMENT
                    logger.info("Switching to fine alignment")
                    # Reset PID controllers for fine mode
                    self.x_controller.reset()
                    self.distance_controller.reset()
                    
            # Calculate motor speeds
            mode = 'coarse' if self.state == AlignmentState.COARSE_ALIGNMENT else 'fine'
            left, right = self.calculate_motor_speeds(errors, mode)
            
            # Apply speeds
            actual_left, actual_right = self.set_motor_speeds(left, right)
            
            # Callback for UI updates
            if callback:
                callback({
                    'state': self.state,
                    'errors': errors,
                    'motor_speeds': (actual_left, actual_right),
                    'marker': marker,
                    'aligned_count': aligned_count
                })
                
            time.sleep(0.05)  # 20 Hz control loop
            
        # Timeout
        logger.error("Alignment timeout")
        self.stop_motors()
        self.state = AlignmentState.ERROR
        return False
        
    def save_alignment_position(self, marker_id: int, name: str = None) -> AlignmentTarget:
        """Save current position as alignment target."""
        if not self.last_marker_info:
            logger.error("No marker information available")
            return None
            
        # Get current frame for dimensions
        frame, _ = self.camera.capture_frame()
        frame_height, frame_width = frame.shape[:2]
        
        # Create target from current position
        target = AlignmentTarget(
            marker_id=marker_id,
            name=name or f"Position_{marker_id}",
            target_x_ratio=self.last_marker_info.center[0] / frame_width,
            target_y_ratio=self.last_marker_info.center[1] / frame_height,
            target_distance_cm=self.last_marker_info.distance,
            tolerance_x_pixels=10,
            tolerance_y_pixels=10,
            tolerance_distance_cm=2.0,
            tolerance_angle_deg=3.0
        )
        
        # Save to file
        filename = f"alignment_targets.json"
        targets = {}
        
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                targets = {int(k): AlignmentTarget.from_dict(v) for k, v in data.items()}
                
        targets[marker_id] = target
        
        with open(filename, 'w') as f:
            json.dump({k: v.to_dict() for k, v in targets.items()}, f, indent=2)
            
        logger.info(f"Saved alignment position for marker {marker_id}")
        return target
        
    def load_alignment_target(self, marker_id: int) -> Optional[AlignmentTarget]:
        """Load saved alignment target."""
        filename = "alignment_targets.json"
        
        if not os.path.exists(filename):
            logger.warning("No saved targets found")
            return None
            
        with open(filename, 'r') as f:
            data = json.load(f)
            
        if str(marker_id) in data:
            return AlignmentTarget.from_dict(data[str(marker_id)])
        else:
            logger.warning(f"No saved target for marker {marker_id}")
            return None
            
    def cleanup(self):
        """Clean up resources."""
        self.stop_motors()
        
        if self.camera:
            self.camera.stop()
            
        if not self.simulation_mode:
            if self.left_motor:
                self.left_motor.disable()
                self.left_motor.cleanup()
            if self.right_motor:
                self.right_motor.disable()
                self.right_motor.cleanup()

class AlignmentGUI:
    """GUI for precision alignment tool."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ArUco Precision Alignment Tool")
        self.root.geometry("1000x700")
        
        self.aligner = RobustAligner()
        self.current_frame = None
        self.is_aligning = False
        self.alignment_thread = None
        
        self.setup_gui()
        
        # Initialize camera
        if self.aligner.init_camera():
            self.start_video_feed()
        else:
            messagebox.showerror("Error", "Failed to initialize camera")
            
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_gui(self):
        """Setup GUI components."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill='both', expand=True)
        
        # Left side - Video feed
        video_frame = ttk.LabelFrame(main_frame, text="Camera Feed", padding="5")
        video_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        self.video_label = ttk.Label(video_frame)
        self.video_label.pack()
        
        # Overlay for alignment visualization
        self.overlay_canvas = tk.Canvas(video_frame, width=640, height=480, 
                                       highlightthickness=0)
        self.overlay_canvas.place(x=0, y=0)
        
        # Right side - Controls
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)
        
        # Target selection
        target_frame = ttk.LabelFrame(control_frame, text="Alignment Target", padding="10")
        target_frame.pack(fill='x', pady=5)
        
        ttk.Label(target_frame, text="Marker ID:").grid(row=0, column=0, sticky='w')
        self.marker_id_var = tk.IntVar(value=0)
        ttk.Spinbox(target_frame, from_=0, to=100, textvariable=self.marker_id_var,
                   width=10).grid(row=0, column=1, padx=5)
        
        ttk.Label(target_frame, text="Distance (cm):").grid(row=1, column=0, sticky='w')
        self.distance_var = tk.DoubleVar(value=30.0)
        ttk.Spinbox(target_frame, from_=10, to=200, increment=5,
                   textvariable=self.distance_var, width=10).grid(row=1, column=1, padx=5)
        
        ttk.Label(target_frame, text="X Position:").grid(row=2, column=0, sticky='w')
        self.x_position_var = tk.DoubleVar(value=0.5)
        ttk.Scale(target_frame, from_=0, to=1, variable=self.x_position_var,
                 orient='horizontal', length=150).grid(row=2, column=1, padx=5)
        
        # Control buttons
        button_frame = ttk.LabelFrame(control_frame, text="Controls", padding="10")
        button_frame.pack(fill='x', pady=5)
        
        self.align_btn = ttk.Button(button_frame, text="Start Alignment",
                                   command=self.toggle_alignment)
        self.align_btn.pack(fill='x', pady=2)
        
        ttk.Button(button_frame, text="Save Position",
                  command=self.save_position).pack(fill='x', pady=2)
        
        ttk.Button(button_frame, text="Load Position",
                  command=self.load_position).pack(fill='x', pady=2)
        
        ttk.Button(button_frame, text="Emergency Stop",
                  command=self.emergency_stop).pack(fill='x', pady=10)
        
        # Status display
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding="10")
        status_frame.pack(fill='both', expand=True, pady=5)
        
        self.status_text = tk.Text(status_frame, height=10, width=40)
        self.status_text.pack(fill='both', expand=True)
        
        # Error displays
        error_frame = ttk.LabelFrame(control_frame, text="Alignment Errors", padding="10")
        error_frame.pack(fill='x', pady=5)
        
        self.x_error_label = ttk.Label(error_frame, text="X Error: ---")
        self.x_error_label.pack(anchor='w')
        
        self.distance_error_label = ttk.Label(error_frame, text="Distance Error: ---")
        self.distance_error_label.pack(anchor='w')
        
        self.angle_error_label = ttk.Label(error_frame, text="Angle Error: ---")
        self.angle_error_label.pack(anchor='w')
        
        # Progress bar
        self.progress = ttk.Progressbar(control_frame, mode='determinate', maximum=10)
        self.progress.pack(fill='x', pady=5)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
    def start_video_feed(self):
        """Start video feed update loop."""
        def update_feed():
            if self.aligner.camera:
                frame, _ = self.aligner.camera.capture_frame()
                
                # Detect markers
                if self.aligner.detector:
                    markers = self.aligner.detector.detect_markers(frame)
                    frame = self.aligner.detector.draw_markers(frame, markers)
                    
                    # Draw alignment target
                    self.draw_alignment_target(frame)
                    
                # Convert and display
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (640, 480))
                img = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image=img)
                self.video_label.config(image=photo)
                self.video_label.image = photo
                
            self.root.after(50, update_feed)
            
        update_feed()
        
    def draw_alignment_target(self, frame):
        """Draw alignment target on frame."""
        height, width = frame.shape[:2]
        target_x = int(self.x_position_var.get() * width)
        target_y = int(height / 2)
        
        # Draw target crosshair
        cv2.drawMarker(frame, (target_x, target_y), (0, 255, 0), 
                      cv2.MARKER_CROSS, 20, 2)
        
        # Draw target zone
        tolerance = 20
        cv2.rectangle(frame, (target_x - tolerance, target_y - tolerance),
                     (target_x + tolerance, target_y + tolerance),
                     (0, 255, 0), 1)
                     
    def toggle_alignment(self):
        """Start or stop alignment."""
        if self.is_aligning:
            self.stop_alignment()
        else:
            self.start_alignment()
            
    def start_alignment(self):
        """Start alignment process."""
        self.is_aligning = True
        self.align_btn.config(text="Stop Alignment")
        
        # Create target
        target = AlignmentTarget(
            marker_id=self.marker_id_var.get(),
            name=f"Target_{self.marker_id_var.get()}",
            target_x_ratio=self.x_position_var.get(),
            target_y_ratio=0.5,
            target_distance_cm=self.distance_var.get()
        )
        
        # Start alignment in thread
        self.alignment_thread = threading.Thread(
            target=self.aligner.align_with_marker,
            args=(target, 60, self.alignment_callback)
        )
        self.alignment_thread.start()
        
    def stop_alignment(self):
        """Stop alignment process."""
        self.is_aligning = False
        self.align_btn.config(text="Start Alignment")
        self.aligner.stop_motors()
        self.aligner.state = AlignmentState.IDLE
        
    def alignment_callback(self, data):
        """Callback for alignment updates."""
        # Update status
        self.root.after(0, self.update_status, data)
        
    def update_status(self, data):
        """Update status displays."""
        # Update error labels
        errors = data['errors']
        self.x_error_label.config(text=f"X Error: {errors['x_error']:.1f} px")
        self.distance_error_label.config(text=f"Distance Error: {errors['distance_error']:.1f} cm")
        self.angle_error_label.config(text=f"Angle Error: {errors['angle_error']:.1f}°")
        
        # Update progress
        self.progress['value'] = data['aligned_count']
        
        # Update status text
        status = f"State: {data['state'].value}\n"
        status += f"Motor L: {data['motor_speeds'][0]:.1f}%\n"
        status += f"Motor R: {data['motor_speeds'][1]:.1f}%\n"
        status += f"Marker Distance: {data['marker'].distance:.1f} cm\n"
        
        self.status_text.delete('1.0', tk.END)
        self.status_text.insert('1.0', status)
        
    def save_position(self):
        """Save current position."""
        marker_id = self.marker_id_var.get()
        name = f"Position_{marker_id}"
        
        target = self.aligner.save_alignment_position(marker_id, name)
        if target:
            messagebox.showinfo("Success", f"Saved position for marker {marker_id}")
        else:
            messagebox.showerror("Error", "No marker visible to save position")
            
    def load_position(self):
        """Load saved position."""
        marker_id = self.marker_id_var.get()
        target = self.aligner.load_alignment_target(marker_id)
        
        if target:
            self.distance_var.set(target.target_distance_cm)
            self.x_position_var.set(target.target_x_ratio)
            messagebox.showinfo("Success", f"Loaded position for marker {marker_id}")
        else:
            messagebox.showwarning("Not Found", f"No saved position for marker {marker_id}")
            
    def emergency_stop(self):
        """Emergency stop."""
        self.stop_alignment()
        self.aligner.stop_motors()
        messagebox.showwarning("Stopped", "Emergency stop activated")
        
    def on_closing(self):
        """Handle window closing."""
        self.stop_alignment()
        self.aligner.cleanup()
        self.root.destroy()

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='ArUco Precision Alignment Tool')
    parser.add_argument('--gui', action='store_true', help='Launch GUI mode')
    parser.add_argument('--align', type=int, help='Align with specific marker ID')
    parser.add_argument('--distance', type=float, default=30.0, 
                       help='Target distance in cm')
    parser.add_argument('--save', type=int, help='Save current position for marker')
    parser.add_argument('--simulation', action='store_true', 
                       help='Run in simulation mode')
    
    args = parser.parse_args()
    
    if args.gui:
        # Launch GUI
        root = tk.Tk()
        app = AlignmentGUI(root)
        root.mainloop()
    else:
        # Command line mode
        aligner = RobustAligner(simulation_mode=args.simulation)
        
        if not aligner.init_camera():
            logger.error("Failed to initialize camera")
            return 1
            
        try:
            if args.save is not None:
                # Save current position
                target = aligner.save_alignment_position(args.save)
                if target:
                    print(f"Saved position for marker {args.save}")
                    
            elif args.align is not None:
                # Align with marker
                target = aligner.load_alignment_target(args.align)
                if not target:
                    # Create default target
                    target = AlignmentTarget(
                        marker_id=args.align,
                        name=f"Target_{args.align}",
                        target_x_ratio=0.5,
                        target_y_ratio=0.5,
                        target_distance_cm=args.distance
                    )
                    
                print(f"Aligning with marker {args.align} at {args.distance}cm...")
                success = aligner.align_with_marker(target)
                
                if success:
                    print("Alignment successful!")
                else:
                    print("Alignment failed")
                    
            else:
                parser.print_help()
                
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            aligner.cleanup()
            
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())