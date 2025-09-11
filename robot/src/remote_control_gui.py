#!/usr/bin/env python3
"""Remote control GUI for BevBot with camera feed and routine programming."""

import cv2
import numpy as np
import time
import logging
import threading
import signal
import sys
import json
import os
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, asdict
from queue import Queue
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
from .aruco_center_demo import ArUcoDetector, MarkerInfo

if HARDWARE_AVAILABLE:
    from .pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM,
        ACTUATOR_R_EN, ACTUATOR_L_EN, ACTUATOR_RPWM, ACTUATOR_LPWM
    )
    from .motor_gpiozero import BTS7960Motor
    from .actuator_gpiozero import LinearActuator

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class RoutineCommand:
    """Single command in a routine."""
    type: str  # 'move', 'turn', 'actuator', 'wait', 'track_marker'
    duration: float
    parameters: Dict[str, Any]
    timestamp: float = 0
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        return cls(**data)

class RobotController:
    """Complete robot control interface."""
    
    def __init__(self, simulation_mode: bool = False):
        """Initialize robot controller."""
        self.simulation_mode = simulation_mode or not HARDWARE_AVAILABLE
        self.left_motor = None
        self.right_motor = None
        self.actuator = None
        
        # Current state
        self.left_speed = 0
        self.right_speed = 0
        self.actuator_state = "stopped"  # 'extending', 'retracting', 'stopped'
        
        if not self.simulation_mode:
            self._init_hardware()
    
    def _init_hardware(self):
        """Initialize hardware components."""
        try:
            # Initialize motors (swapped L/R pins to fix turning)
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
            
            # Initialize actuator
            self.actuator = LinearActuator()
            
            # Enable all
            self.left_motor.enable()
            self.right_motor.enable()
            self.actuator.enable()
            
            logger.info("Hardware initialized")
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            self.simulation_mode = True
    
    def set_motor_speeds(self, left: float, right: float):
        """Set motor speeds."""
        self.left_speed = np.clip(left, -100, 100)
        self.right_speed = np.clip(right, -100, 100)
        
        if not self.simulation_mode:
            try:
                self.left_motor.drive(self.left_speed)
                self.right_motor.drive(self.right_speed)
            except Exception as e:
                logger.error(f"Error setting motor speeds: {e}")
    
    def move_forward(self, speed: float = 30):
        """Move forward at given speed."""
        self.set_motor_speeds(speed, speed)
    
    def move_backward(self, speed: float = 30):
        """Move backward at given speed."""
        self.set_motor_speeds(-speed, -speed)
    
    def turn_left(self, speed: float = 30):
        """Turn left in place."""
        self.set_motor_speeds(-speed, speed)
    
    def turn_right(self, speed: float = 30):
        """Turn right in place."""
        self.set_motor_speeds(speed, -speed)
    
    def stop_motors(self):
        """Stop all motors."""
        self.set_motor_speeds(0, 0)
    
    def extend_actuator(self, speed: float = 50):
        """Extend actuator."""
        self.actuator_state = "extending"
        if not self.simulation_mode:
            self.actuator.extend(speed)
    
    def retract_actuator(self, speed: float = 50):
        """Retract actuator."""
        self.actuator_state = "retracting"
        if not self.simulation_mode:
            self.actuator.retract(speed)
    
    def stop_actuator(self):
        """Stop actuator."""
        self.actuator_state = "stopped"
        if not self.simulation_mode:
            self.actuator.stop()
    
    def cleanup(self):
        """Clean up hardware resources."""
        self.stop_motors()
        self.stop_actuator()
        
        if not self.simulation_mode:
            try:
                if self.left_motor:
                    self.left_motor.disable()
                    self.left_motor.cleanup()
                if self.right_motor:
                    self.right_motor.disable()
                    self.right_motor.cleanup()
                if self.actuator:
                    self.actuator.disable()
                    self.actuator.cleanup()
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

class RoutineRecorder:
    """Record and playback robot routines."""
    
    def __init__(self):
        """Initialize routine recorder."""
        self.recording = False
        self.playing = False
        self.routine: List[RoutineCommand] = []
        self.start_time = 0
        self.playback_thread = None
        self.playback_stop_event = threading.Event()
    
    def start_recording(self):
        """Start recording a new routine."""
        self.recording = True
        self.routine = []
        self.start_time = time.time()
        logger.info("Started recording routine")
    
    def stop_recording(self):
        """Stop recording."""
        self.recording = False
        logger.info(f"Stopped recording. Routine has {len(self.routine)} commands")
    
    def add_command(self, cmd_type: str, duration: float, **parameters):
        """Add command to routine if recording."""
        if self.recording:
            timestamp = time.time() - self.start_time
            cmd = RoutineCommand(
                type=cmd_type,
                duration=duration,
                parameters=parameters,
                timestamp=timestamp
            )
            self.routine.append(cmd)
            logger.debug(f"Recorded: {cmd_type} at {timestamp:.2f}s")
    
    def save_routine(self, filename: str):
        """Save routine to JSON file."""
        data = {
            'created': datetime.now().isoformat(),
            'commands': [cmd.to_dict() for cmd in self.routine]
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved routine to {filename}")
    
    def load_routine(self, filename: str):
        """Load routine from JSON file."""
        with open(filename, 'r') as f:
            data = json.load(f)
        self.routine = [RoutineCommand.from_dict(cmd) for cmd in data['commands']]
        logger.info(f"Loaded routine with {len(self.routine)} commands")
    
    def play_routine(self, robot_controller, callback=None):
        """Play back recorded routine."""
        if self.playing:
            logger.warning("Already playing a routine")
            return
        
        self.playing = True
        self.playback_stop_event.clear()
        self.playback_thread = threading.Thread(
            target=self._playback_worker,
            args=(robot_controller, callback)
        )
        self.playback_thread.start()
    
    def stop_playback(self):
        """Stop routine playback."""
        self.playback_stop_event.set()
        if self.playback_thread:
            self.playback_thread.join(timeout=2)
        self.playing = False
        logger.info("Stopped routine playback")
    
    def _playback_worker(self, robot_controller, callback):
        """Worker thread for routine playback."""
        logger.info("Starting routine playback")
        
        for i, cmd in enumerate(self.routine):
            if self.playback_stop_event.is_set():
                break
            
            # Execute command
            if cmd.type == 'move':
                robot_controller.set_motor_speeds(
                    cmd.parameters['left_speed'],
                    cmd.parameters['right_speed']
                )
            elif cmd.type == 'actuator':
                if cmd.parameters['action'] == 'extend':
                    robot_controller.extend_actuator(cmd.parameters.get('speed', 50))
                elif cmd.parameters['action'] == 'retract':
                    robot_controller.retract_actuator(cmd.parameters.get('speed', 50))
                else:
                    robot_controller.stop_actuator()
            elif cmd.type == 'wait':
                pass  # Just wait
            
            # Update callback
            if callback:
                callback(i, len(self.routine))
            
            # Wait for duration
            wait_time = cmd.duration
            while wait_time > 0 and not self.playback_stop_event.is_set():
                time.sleep(min(0.1, wait_time))
                wait_time -= 0.1
        
        # Stop everything at end
        robot_controller.stop_motors()
        robot_controller.stop_actuator()
        
        self.playing = False
        if callback:
            callback(-1, len(self.routine))  # Signal completion
        
        logger.info("Routine playback completed")

class RemoteControlGUI:
    """Main remote control GUI application."""
    
    def __init__(self, root: tk.Tk):
        """Initialize GUI."""
        self.root = root
        self.root.title("BevBot Remote Control")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Components
        self.camera = None
        self.robot = RobotController()
        self.recorder = RoutineRecorder()
        self.detector = ArUcoDetector(marker_size_cm=10.0)  # 100mm = 10cm markers
        
        # State
        self.running = False
        self.tracking_marker = False
        self.target_marker_id = None
        self.current_frame = None
        self.frame_queue = Queue(maxsize=2)
        
        # Control state
        self.motor_speed = 30
        self.actuator_speed = 50
        self.key_controls_active = False
        
        # Setup GUI
        self._setup_gui()
        
        # Bind keyboard controls
        self._setup_keyboard_controls()
        
        # Start camera
        self._init_camera()
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        # Start GUI update
        self._update_gui()
    
    def _setup_gui(self):
        """Setup GUI components."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Manual Control
        self.control_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.control_tab, text="Manual Control")
        self._setup_control_tab()
        
        # Tab 2: Routine Programming
        self.routine_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.routine_tab, text="Routine Programming")
        self._setup_routine_tab()
        
        # Tab 3: ArUco Tracking
        self.tracking_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.tracking_tab, text="ArUco Tracking")
        self._setup_tracking_tab()
    
    def _setup_control_tab(self):
        """Setup manual control tab."""
        # Main container
        main_frame = ttk.Frame(self.control_tab, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Left side - Camera feed
        camera_frame = ttk.LabelFrame(main_frame, text="Camera Feed", padding="5")
        camera_frame.grid(row=0, column=0, rowspan=3, padx=5, pady=5, sticky='nsew')
        
        self.video_label = ttk.Label(camera_frame)
        self.video_label.pack()
        
        # Right side - Controls
        control_frame = ttk.LabelFrame(main_frame, text="Movement Controls", padding="10")
        control_frame.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        # Speed control
        ttk.Label(control_frame, text="Motor Speed:").grid(row=0, column=0, sticky='w')
        self.speed_var = tk.IntVar(value=30)
        speed_scale = ttk.Scale(control_frame, from_=0, to=100, 
                                variable=self.speed_var, orient='horizontal', length=200)
        speed_scale.grid(row=0, column=1, padx=5)
        self.speed_label = ttk.Label(control_frame, text="30%")
        self.speed_label.grid(row=0, column=2)
        speed_scale.config(command=lambda v: self._update_speed())
        
        # Direction buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=1, column=0, columnspan=3, pady=10)
        
        # Create direction pad
        self.forward_btn = ttk.Button(button_frame, text="↑\nForward", width=10)
        self.forward_btn.grid(row=0, column=1, padx=2, pady=2)
        
        self.left_btn = ttk.Button(button_frame, text="←\nLeft", width=10)
        self.left_btn.grid(row=1, column=0, padx=2, pady=2)
        
        self.stop_btn = ttk.Button(button_frame, text="STOP", width=10,
                                   command=self.emergency_stop)
        self.stop_btn.grid(row=1, column=1, padx=2, pady=2)
        
        self.right_btn = ttk.Button(button_frame, text="→\nRight", width=10)
        self.right_btn.grid(row=1, column=2, padx=2, pady=2)
        
        self.backward_btn = ttk.Button(button_frame, text="↓\nBackward", width=10)
        self.backward_btn.grid(row=2, column=1, padx=2, pady=2)
        
        # Bind button press/release events
        self._bind_movement_button(self.forward_btn, self.robot.move_forward)
        self._bind_movement_button(self.backward_btn, self.robot.move_backward)
        self._bind_movement_button(self.left_btn, self.robot.turn_left)
        self._bind_movement_button(self.right_btn, self.robot.turn_right)
        
        # Actuator controls
        actuator_frame = ttk.LabelFrame(main_frame, text="Actuator Controls", padding="10")
        actuator_frame.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(actuator_frame, text="Actuator Speed:").grid(row=0, column=0, sticky='w')
        self.actuator_speed_var = tk.IntVar(value=50)
        actuator_scale = ttk.Scale(actuator_frame, from_=0, to=100,
                                   variable=self.actuator_speed_var, 
                                   orient='horizontal', length=200)
        actuator_scale.grid(row=0, column=1, padx=5)
        self.actuator_speed_label = ttk.Label(actuator_frame, text="50%")
        self.actuator_speed_label.grid(row=0, column=2)
        actuator_scale.config(command=lambda v: self._update_actuator_speed())
        
        actuator_btn_frame = ttk.Frame(actuator_frame)
        actuator_btn_frame.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.extend_btn = ttk.Button(actuator_btn_frame, text="Extend", width=10)
        self.extend_btn.grid(row=0, column=0, padx=2)
        
        self.actuator_stop_btn = ttk.Button(actuator_btn_frame, text="Stop", width=10,
                                           command=self.robot.stop_actuator)
        self.actuator_stop_btn.grid(row=0, column=1, padx=2)
        
        self.retract_btn = ttk.Button(actuator_btn_frame, text="Retract", width=10)
        self.retract_btn.grid(row=0, column=2, padx=2)
        
        self._bind_actuator_button(self.extend_btn, self.robot.extend_actuator)
        self._bind_actuator_button(self.retract_btn, self.robot.retract_actuator)
        
        # Status panel
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=2, column=1, padx=5, pady=5, sticky='ew')
        
        self.status_text = tk.Text(status_frame, height=6, width=40, state='disabled')
        self.status_text.pack()
        
        # Keyboard control toggle
        self.keyboard_var = tk.BooleanVar(value=False)
        keyboard_check = ttk.Checkbutton(status_frame, text="Enable Keyboard Control (WASD + QE)",
                                        variable=self.keyboard_var,
                                        command=self._toggle_keyboard_control)
        keyboard_check.pack(pady=5)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=1)
    
    def _setup_routine_tab(self):
        """Setup routine programming tab."""
        main_frame = ttk.Frame(self.routine_tab, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Recording controls
        record_frame = ttk.LabelFrame(main_frame, text="Recording Controls", padding="10")
        record_frame.pack(fill='x', pady=5)
        
        self.record_btn = ttk.Button(record_frame, text="Start Recording",
                                    command=self.toggle_recording)
        self.record_btn.pack(side='left', padx=5)
        
        self.clear_btn = ttk.Button(record_frame, text="Clear Routine",
                                   command=self.clear_routine)
        self.clear_btn.pack(side='left', padx=5)
        
        ttk.Label(record_frame, text="Commands:").pack(side='left', padx=10)
        self.command_count_label = ttk.Label(record_frame, text="0")
        self.command_count_label.pack(side='left')
        
        # Routine list
        list_frame = ttk.LabelFrame(main_frame, text="Recorded Routine", padding="10")
        list_frame.pack(fill='both', expand=True, pady=5)
        
        # Create treeview for routine display
        columns = ('Time', 'Command', 'Parameters', 'Duration')
        self.routine_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=10)
        
        for col in columns:
            self.routine_tree.heading(col, text=col)
            self.routine_tree.column(col, width=120)
        
        self.routine_tree.pack(side='left', fill='both', expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.routine_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.routine_tree.config(yscrollcommand=scrollbar.set)
        
        # Playback controls
        playback_frame = ttk.LabelFrame(main_frame, text="Playback Controls", padding="10")
        playback_frame.pack(fill='x', pady=5)
        
        self.play_btn = ttk.Button(playback_frame, text="Play Routine",
                                  command=self.play_routine)
        self.play_btn.pack(side='left', padx=5)
        
        self.stop_playback_btn = ttk.Button(playback_frame, text="Stop Playback",
                                           command=self.stop_routine_playback,
                                           state='disabled')
        self.stop_playback_btn.pack(side='left', padx=5)
        
        ttk.Separator(playback_frame, orient='vertical').pack(side='left', padx=10, fill='y')
        
        self.loop_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(playback_frame, text="Loop", variable=self.loop_var).pack(side='left', padx=5)
        
        # Progress bar
        self.playback_progress = ttk.Progressbar(playback_frame, length=200, mode='determinate')
        self.playback_progress.pack(side='left', padx=10)
        
        # File operations
        file_frame = ttk.LabelFrame(main_frame, text="File Operations", padding="10")
        file_frame.pack(fill='x', pady=5)
        
        ttk.Button(file_frame, text="Save Routine",
                  command=self.save_routine).pack(side='left', padx=5)
        ttk.Button(file_frame, text="Load Routine",
                  command=self.load_routine).pack(side='left', padx=5)
    
    def _setup_tracking_tab(self):
        """Setup ArUco tracking tab."""
        main_frame = ttk.Frame(self.tracking_tab, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Tracking controls
        control_frame = ttk.LabelFrame(main_frame, text="Tracking Controls", padding="10")
        control_frame.pack(fill='x', pady=5)
        
        self.track_btn = ttk.Button(control_frame, text="Start Tracking",
                                   command=self.toggle_tracking)
        self.track_btn.pack(side='left', padx=5)
        
        ttk.Label(control_frame, text="Target Marker:").pack(side='left', padx=10)
        self.marker_var = tk.StringVar(value="Any")
        marker_combo = ttk.Combobox(control_frame, textvariable=self.marker_var,
                                   width=10, state="readonly")
        marker_combo['values'] = ["Any"] + [str(i) for i in range(20)]
        marker_combo.pack(side='left', padx=5)
        marker_combo.bind("<<ComboboxSelected>>", self.on_marker_selected)
        
        ttk.Label(control_frame, text="Target Distance (cm):").pack(side='left', padx=10)
        self.distance_var = tk.IntVar(value=30)
        distance_spin = ttk.Spinbox(control_frame, from_=10, to=100,
                                   textvariable=self.distance_var, width=10)
        distance_spin.pack(side='left', padx=5)
        
        # Detected markers list
        marker_frame = ttk.LabelFrame(main_frame, text="Detected Markers", padding="10")
        marker_frame.pack(fill='both', expand=True, pady=5)
        
        columns = ('ID', 'Distance', 'X Position', 'Y Position', 'Size')
        self.marker_tree = ttk.Treeview(marker_frame, columns=columns, show='tree headings', height=8)
        
        for col in columns:
            self.marker_tree.heading(col, text=col)
            self.marker_tree.column(col, width=100)
        
        self.marker_tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(marker_frame, orient='vertical', command=self.marker_tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.marker_tree.config(yscrollcommand=scrollbar.set)
        
        # Tracking parameters
        param_frame = ttk.LabelFrame(main_frame, text="Tracking Parameters", padding="10")
        param_frame.pack(fill='x', pady=5)
        
        # PID gains
        ttk.Label(param_frame, text="Heading P-gain:").grid(row=0, column=0, sticky='w')
        self.kp_heading_var = tk.DoubleVar(value=0.15)
        ttk.Scale(param_frame, from_=0, to=1, variable=self.kp_heading_var,
                 orient='horizontal', length=150).grid(row=0, column=1, padx=5)
        
        ttk.Label(param_frame, text="Distance P-gain:").grid(row=1, column=0, sticky='w')
        self.kp_distance_var = tk.DoubleVar(value=0.8)
        ttk.Scale(param_frame, from_=0, to=2, variable=self.kp_distance_var,
                 orient='horizontal', length=150).grid(row=1, column=1, padx=5)
        
        ttk.Label(param_frame, text="Max Speed:").grid(row=0, column=2, sticky='w', padx=(20,0))
        self.max_track_speed_var = tk.IntVar(value=40)
        ttk.Scale(param_frame, from_=10, to=100, variable=self.max_track_speed_var,
                 orient='horizontal', length=150).grid(row=0, column=3, padx=5)
    
    def _bind_movement_button(self, button, command):
        """Bind press/release events for movement button."""
        def on_press(event):
            if self.recorder.recording:
                self.recorder.add_command('move', 0,
                                        left_speed=self.robot.left_speed,
                                        right_speed=self.robot.right_speed)
            command(self.speed_var.get())
        
        def on_release(event):
            if self.recorder.recording:
                self.recorder.add_command('move', 0,
                                        left_speed=0, right_speed=0)
            self.robot.stop_motors()
        
        button.bind('<ButtonPress-1>', on_press)
        button.bind('<ButtonRelease-1>', on_release)
    
    def _bind_actuator_button(self, button, command):
        """Bind press/release events for actuator button."""
        def on_press(event):
            if self.recorder.recording:
                action = 'extend' if 'extend' in str(command) else 'retract'
                self.recorder.add_command('actuator', 0,
                                        action=action,
                                        speed=self.actuator_speed_var.get())
            command(self.actuator_speed_var.get())
        
        def on_release(event):
            if self.recorder.recording:
                self.recorder.add_command('actuator', 0,
                                        action='stop', speed=0)
            self.robot.stop_actuator()
        
        button.bind('<ButtonPress-1>', on_press)
        button.bind('<ButtonRelease-1>', on_release)
    
    def _setup_keyboard_controls(self):
        """Setup keyboard control bindings."""
        self.root.bind('<KeyPress>', self._on_key_press)
        self.root.bind('<KeyRelease>', self._on_key_release)
        self.keys_pressed = set()
    
    def _on_key_press(self, event):
        """Handle key press events."""
        if not self.key_controls_active:
            return
        
        key = event.char.lower()
        if key in self.keys_pressed:
            return
        
        self.keys_pressed.add(key)
        speed = self.speed_var.get()
        
        if key == 'w':
            self.robot.move_forward(speed)
        elif key == 's':
            self.robot.move_backward(speed)
        elif key == 'a':
            self.robot.turn_left(speed)
        elif key == 'd':
            self.robot.turn_right(speed)
        elif key == 'q':
            self.robot.extend_actuator(self.actuator_speed_var.get())
        elif key == 'e':
            self.robot.retract_actuator(self.actuator_speed_var.get())
        elif key == ' ':
            self.emergency_stop()
    
    def _on_key_release(self, event):
        """Handle key release events."""
        if not self.key_controls_active:
            return
        
        key = event.char.lower()
        self.keys_pressed.discard(key)
        
        if key in ['w', 's', 'a', 'd']:
            if not any(k in self.keys_pressed for k in ['w', 's', 'a', 'd']):
                self.robot.stop_motors()
        elif key in ['q', 'e']:
            self.robot.stop_actuator()
    
    def _toggle_keyboard_control(self):
        """Toggle keyboard control mode."""
        self.key_controls_active = self.keyboard_var.get()
        if self.key_controls_active:
            self.root.focus_set()
            logger.info("Keyboard control enabled")
        else:
            logger.info("Keyboard control disabled")
    
    def _update_speed(self):
        """Update speed display."""
        speed = self.speed_var.get()
        self.speed_label.config(text=f"{speed}%")
        self.motor_speed = speed
    
    def _update_actuator_speed(self):
        """Update actuator speed display."""
        speed = self.actuator_speed_var.get()
        self.actuator_speed_label.config(text=f"{speed}%")
        self.actuator_speed = speed
    
    def _init_camera(self):
        """Initialize camera."""
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                self.running = True
                self._update_status("Camera: Ready")
            else:
                self._update_status("Camera: Not found")
                logger.error("Camera not available")
        except Exception as e:
            self._update_status("Camera: Error")
            logger.error(f"Failed to initialize camera: {e}")
    
    def _processing_loop(self):
        """Main processing loop for camera and tracking."""
        while True:
            if self.running and self.camera:
                try:
                    # Capture frame
                    frame, _ = self.camera.capture_frame()
                    
                    # Detect markers
                    markers = self.detector.detect_markers(frame)
                    
                    # Update marker list
                    self.detected_markers = markers
                    
                    # Handle tracking if enabled
                    if self.tracking_marker and markers:
                        target_marker = None
                        if self.target_marker_id is None:
                            target_marker = min(markers.values(), key=lambda m: m.distance)
                        elif self.target_marker_id in markers:
                            target_marker = markers[self.target_marker_id]
                        
                        if target_marker:
                            self._track_marker(target_marker, frame.shape[1])
                    
                    # Annotate frame
                    annotated_frame = self.detector.draw_markers(frame, markers)
                    
                    # Queue frame for display
                    if not self.frame_queue.full():
                        self.frame_queue.put(annotated_frame)
                    
                except Exception as e:
                    logger.error(f"Processing error: {e}")
            
            time.sleep(0.05)
    
    def _track_marker(self, marker: MarkerInfo, frame_width: int):
        """Track and center on marker."""
        center_x = frame_width / 2
        heading_error = marker.center[0] - center_x
        distance_error = self.distance_var.get() - marker.distance
        
        # Simple proportional control
        kp_heading = self.kp_heading_var.get()
        kp_distance = self.kp_distance_var.get()
        max_speed = self.max_track_speed_var.get()
        
        turn_control = kp_heading * heading_error
        forward_control = kp_distance * distance_error
        
        left_speed = np.clip(forward_control + turn_control, -max_speed, max_speed)
        right_speed = np.clip(forward_control - turn_control, -max_speed, max_speed)
        
        self.robot.set_motor_speeds(left_speed, right_speed)
    
    def _update_gui(self):
        """Update GUI elements."""
        try:
            # Update camera feed
            if not self.frame_queue.empty():
                frame = self.frame_queue.get_nowait()
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (640, 480))
                img = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image=img)
                self.video_label.config(image=photo)
                self.video_label.image = photo
            
            # Update status
            status_text = f"Mode: {'Hardware' if not self.robot.simulation_mode else 'Simulation'}\n"
            status_text += f"Motors: L={self.robot.left_speed:.0f}% R={self.robot.right_speed:.0f}%\n"
            status_text += f"Actuator: {self.robot.actuator_state}\n"
            status_text += f"Recording: {'Yes' if self.recorder.recording else 'No'}\n"
            status_text += f"Tracking: {'Active' if self.tracking_marker else 'Inactive'}"
            
            self.status_text.config(state='normal')
            self.status_text.delete('1.0', tk.END)
            self.status_text.insert('1.0', status_text)
            self.status_text.config(state='disabled')
            
            # Update routine display
            self.command_count_label.config(text=str(len(self.recorder.routine)))
            
            # Update marker list
            if hasattr(self, 'detected_markers'):
                self.marker_tree.delete(*self.marker_tree.get_children())
                for marker_id, info in self.detected_markers.items():
                    self.marker_tree.insert('', 'end', values=(
                        marker_id,
                        f"{info.distance:.1f}",
                        f"{info.center[0]:.0f}",
                        f"{info.center[1]:.0f}",
                        f"{info.size:.0f}"
                    ))
        
        except Exception as e:
            logger.debug(f"GUI update error: {e}")
        
        # Schedule next update
        self.root.after(50, self._update_gui)
    
    def _update_status(self, message: str):
        """Update status message."""
        logger.info(message)
    
    def emergency_stop(self):
        """Emergency stop all motors."""
        self.robot.stop_motors()
        self.robot.stop_actuator()
        self.tracking_marker = False
        self.recorder.stop_playback()
        self._update_status("Emergency stop activated")
    
    def toggle_recording(self):
        """Toggle routine recording."""
        if self.recorder.recording:
            self.recorder.stop_recording()
            self.record_btn.config(text="Start Recording")
            self._update_routine_display()
        else:
            self.recorder.start_recording()
            self.record_btn.config(text="Stop Recording")
    
    def clear_routine(self):
        """Clear recorded routine."""
        self.recorder.routine = []
        self._update_routine_display()
        self._update_status("Routine cleared")
    
    def _update_routine_display(self):
        """Update routine treeview display."""
        self.routine_tree.delete(*self.routine_tree.get_children())
        for cmd in self.recorder.routine:
            params = ', '.join(f"{k}={v}" for k, v in cmd.parameters.items())
            self.routine_tree.insert('', 'end', values=(
                f"{cmd.timestamp:.2f}s",
                cmd.type,
                params,
                f"{cmd.duration:.2f}s"
            ))
    
    def play_routine(self):
        """Play recorded routine."""
        if not self.recorder.routine:
            messagebox.showwarning("No Routine", "No routine recorded to play")
            return
        
        self.play_btn.config(state='disabled')
        self.stop_playback_btn.config(state='normal')
        
        def playback_callback(current, total):
            if current == -1:
                self.play_btn.config(state='normal')
                self.stop_playback_btn.config(state='disabled')
                self.playback_progress['value'] = 0
                if self.loop_var.get():
                    self.root.after(1000, self.play_routine)
            else:
                self.playback_progress['maximum'] = total
                self.playback_progress['value'] = current
        
        self.recorder.play_routine(self.robot, playback_callback)
    
    def stop_routine_playback(self):
        """Stop routine playback."""
        self.recorder.stop_playback()
        self.play_btn.config(state='normal')
        self.stop_playback_btn.config(state='disabled')
        self.playback_progress['value'] = 0
    
    def save_routine(self):
        """Save routine to file."""
        if not self.recorder.routine:
            messagebox.showwarning("No Routine", "No routine to save")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.recorder.save_routine(filename)
            messagebox.showinfo("Saved", f"Routine saved to {filename}")
    
    def load_routine(self):
        """Load routine from file."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.recorder.load_routine(filename)
            self._update_routine_display()
            messagebox.showinfo("Loaded", f"Routine loaded from {filename}")
    
    def toggle_tracking(self):
        """Toggle ArUco tracking."""
        self.tracking_marker = not self.tracking_marker
        if self.tracking_marker:
            self.track_btn.config(text="Stop Tracking")
            self._update_status("ArUco tracking enabled")
        else:
            self.track_btn.config(text="Start Tracking")
            self.robot.stop_motors()
            self._update_status("ArUco tracking disabled")
    
    def on_marker_selected(self, event=None):
        """Handle marker selection."""
        selection = self.marker_var.get()
        if selection == "Any":
            self.target_marker_id = None
        else:
            self.target_marker_id = int(selection)
        self._update_status(f"Target marker: {selection}")
    
    def on_closing(self):
        """Handle window closing."""
        logger.info("Shutting down...")
        self.running = False
        self.tracking_marker = False
        self.recorder.stop_playback()
        self.robot.cleanup()
        if self.camera:
            self.camera.stop()
        self.root.destroy()

def main():
    """Main entry point."""
    def signal_handler(sig, frame):
        logger.info("Interrupt received, shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    root = tk.Tk()
    root.geometry("1200x800")
    app = RemoteControlGUI(root)
    
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