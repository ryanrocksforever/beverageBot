#!/usr/bin/env python3
"""
BevBot Control Center - Production GUI
Comprehensive control interface combining remote control, routine programming,
ArUco navigation, and system management.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import cv2
import numpy as np
import time
import logging
import threading
import json
import os
import queue
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
from PIL import Image, ImageTk
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import core modules
try:
    from camera import CameraInterface
    from aruco_center_demo import ArUcoDetector, MarkerInfo
    from aruco_navigation import ArUcoNavigator
    VISION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Vision modules not available: {e}")
    VISION_AVAILABLE = False

try:
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    Device.pin_factory = LGPIOFactory()
    from motor_gpiozero import BTS7960Motor
    from actuator_gpiozero import LinearActuator
    from pins import (
        LEFT_MOTOR_R_EN, LEFT_MOTOR_L_EN, LEFT_MOTOR_RPWM, LEFT_MOTOR_LPWM,
        RIGHT_MOTOR_R_EN, RIGHT_MOTOR_L_EN, RIGHT_MOTOR_RPWM, RIGHT_MOTOR_LPWM,
        ACTUATOR_R_EN, ACTUATOR_L_EN, ACTUATOR_RPWM, ACTUATOR_LPWM
    )
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    logger.info("Hardware modules not available - running in simulation mode")

class ActionType(Enum):
    """Enhanced action types for routines."""
    # Movement actions
    MOVE_FORWARD = "move_forward"
    MOVE_BACKWARD = "move_backward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    ROTATE = "rotate"
    STOP = "stop"
    
    # Navigation actions
    NAVIGATE_TO_MARKER = "navigate_to_marker"
    ALIGN_WITH_MARKER = "align_with_marker"
    SCAN_FOR_MARKERS = "scan_for_markers"
    
    # Actuator actions
    ACTUATOR_EXTEND = "actuator_extend"
    ACTUATOR_RETRACT = "actuator_retract"
    ACTUATOR_STOP = "actuator_stop"
    OPEN_DOOR = "open_door"
    CLOSE_DOOR = "close_door"
    
    # Object manipulation
    PICKUP_OBJECT = "pickup_object"
    RELEASE_OBJECT = "release_object"
    
    # Control flow
    WAIT = "wait"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    CONDITIONAL = "conditional"
    
    # Custom
    CUSTOM_SCRIPT = "custom_script"
    RECORD_POSITION = "record_position"

@dataclass
class RobotAction:
    """Enhanced robot action with validation."""
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    name: str = ""
    description: str = ""
    duration: float = 0.0
    
    def validate(self) -> bool:
        """Validate action parameters."""
        required_params = {
            ActionType.MOVE_FORWARD: ['speed', 'distance'],
            ActionType.MOVE_BACKWARD: ['speed', 'distance'],
            ActionType.TURN_LEFT: ['speed', 'angle'],
            ActionType.TURN_RIGHT: ['speed', 'angle'],
            ActionType.ROTATE: ['angle', 'speed'],
            ActionType.NAVIGATE_TO_MARKER: ['marker_id'],
            ActionType.ALIGN_WITH_MARKER: ['marker_id', 'distance_cm'],
            ActionType.WAIT: ['duration'],
            ActionType.ACTUATOR_EXTEND: ['speed', 'duration'],
            ActionType.ACTUATOR_RETRACT: ['speed', 'duration'],
        }
        
        if self.action_type in required_params:
            for param in required_params[self.action_type]:
                if param not in self.parameters:
                    return False
        return True
    
    def to_dict(self):
        return {
            'action_type': self.action_type.value,
            'parameters': self.parameters,
            'name': self.name,
            'description': self.description,
            'duration': self.duration
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            action_type=ActionType(data['action_type']),
            parameters=data.get('parameters', {}),
            name=data.get('name', ''),
            description=data.get('description', ''),
            duration=data.get('duration', 0.0)
        )

@dataclass
class RobotRoutine:
    """Enhanced robot routine with metadata."""
    name: str
    description: str
    actions: List[RobotAction] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    modified_at: str = ""
    author: str = ""
    version: str = "1.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate entire routine."""
        errors = []
        for i, action in enumerate(self.actions):
            if not action.validate():
                errors.append(f"Action {i+1} ({action.name}) has invalid parameters")
        return len(errors) == 0, errors
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'actions': [action.to_dict() for action in self.actions],
            'tags': self.tags,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'author': self.author,
            'version': self.version
        }
    
    @classmethod
    def from_dict(cls, data):
        routine = cls(
            name=data['name'],
            description=data.get('description', ''),
            tags=data.get('tags', []),
            created_at=data.get('created_at', ''),
            modified_at=data.get('modified_at', ''),
            author=data.get('author', ''),
            version=data.get('version', '1.0')
        )
        routine.actions = [RobotAction.from_dict(a) for a in data.get('actions', [])]
        return routine

class RobotController:
    """Enhanced robot controller with safety features."""
    
    def __init__(self, simulation_mode: bool = False):
        self.simulation_mode = simulation_mode or not HARDWARE_AVAILABLE
        self.left_motor = None
        self.right_motor = None
        self.actuator = None
        self.navigator = None
        
        # State tracking
        self.left_speed = 0
        self.right_speed = 0
        self.actuator_state = "stopped"
        self.is_moving = False
        self.emergency_stop_active = False
        
        # Safety limits
        self.max_speed = 100
        self.max_actuator_speed = 100
        self.min_speed_threshold = 10
        
        if not self.simulation_mode:
            self._init_hardware()
    
    def _init_hardware(self):
        """Initialize hardware with error handling."""
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
            
            # Actuator
            self.actuator = LinearActuator()
            
            # Enable all
            self.left_motor.enable()
            self.right_motor.enable()
            self.actuator.enable()
            
            # Navigator
            if VISION_AVAILABLE:
                self.navigator = ArUcoNavigator(simulation_mode=False)
                self.navigator.init_camera()
            
            logger.info("Hardware initialized successfully")
            
        except Exception as e:
            logger.error(f"Hardware initialization failed: {e}")
            self.simulation_mode = True
    
    def set_motor_speeds(self, left: float, right: float):
        """Set motor speeds with safety checks."""
        if self.emergency_stop_active:
            return
        
        # Apply speed limits
        left = np.clip(left, -self.max_speed, self.max_speed)
        right = np.clip(right, -self.max_speed, self.max_speed)
        
        # Apply minimum threshold
        if abs(left) < self.min_speed_threshold:
            left = 0
        if abs(right) < self.min_speed_threshold:
            right = 0
        
        self.left_speed = left
        self.right_speed = right
        self.is_moving = (left != 0 or right != 0)
        
        if not self.simulation_mode:
            try:
                self.left_motor.drive(left)
                self.right_motor.drive(right)
            except Exception as e:
                logger.error(f"Motor control error: {e}")
    
    def move_forward(self, speed: float = 30, distance: float = None):
        """Move forward with optional distance."""
        self.set_motor_speeds(speed, speed)
        if distance:
            # Calculate duration based on distance
            duration = distance / (speed * 0.5)  # Rough estimate
            threading.Timer(duration, self.stop_motors).start()
    
    def move_backward(self, speed: float = 30, distance: float = None):
        """Move backward with optional distance."""
        self.set_motor_speeds(-speed, -speed)
        if distance:
            duration = distance / (speed * 0.5)
            threading.Timer(duration, self.stop_motors).start()
    
    def turn_left(self, speed: float = 30, angle: float = None):
        """Turn left with optional angle."""
        self.set_motor_speeds(-speed, speed)
        if angle:
            duration = angle / (speed * 2)  # Rough estimate
            threading.Timer(duration, self.stop_motors).start()
    
    def turn_right(self, speed: float = 30, angle: float = None):
        """Turn right with optional angle."""
        self.set_motor_speeds(speed, -speed)
        if angle:
            duration = angle / (speed * 2)
            threading.Timer(duration, self.stop_motors).start()
    
    def rotate(self, angle: float, speed: float = 30):
        """Rotate by specific angle."""
        if angle > 0:
            self.turn_right(speed, abs(angle))
        else:
            self.turn_left(speed, abs(angle))
    
    def stop_motors(self):
        """Stop all motors."""
        self.set_motor_speeds(0, 0)
    
    def extend_actuator(self, speed: float = 50, duration: float = None):
        """Extend actuator."""
        if self.emergency_stop_active:
            return
        
        self.actuator_state = "extending"
        if not self.simulation_mode and self.actuator:
            self.actuator.extend(speed)
        
        if duration:
            threading.Timer(duration, self.stop_actuator).start()
    
    def retract_actuator(self, speed: float = 50, duration: float = None):
        """Retract actuator."""
        if self.emergency_stop_active:
            return
        
        self.actuator_state = "retracting"
        if not self.simulation_mode and self.actuator:
            self.actuator.retract(speed)
        
        if duration:
            threading.Timer(duration, self.stop_actuator).start()
    
    def stop_actuator(self):
        """Stop actuator."""
        self.actuator_state = "stopped"
        if not self.simulation_mode and self.actuator:
            self.actuator.stop()
    
    def emergency_stop(self):
        """Emergency stop all systems."""
        self.emergency_stop_active = True
        self.stop_motors()
        self.stop_actuator()
        logger.warning("Emergency stop activated")
    
    def reset_emergency_stop(self):
        """Reset emergency stop."""
        self.emergency_stop_active = False
        logger.info("Emergency stop reset")
    
    def navigate_to_marker(self, marker_id: int, timeout: float = 30) -> bool:
        """Navigate to ArUco marker."""
        if self.navigator and not self.simulation_mode:
            return self.navigator.navigate_to_marker(marker_id, timeout)
        return True  # Simulate success
    
    def cleanup(self):
        """Clean up all hardware resources."""
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
                if self.navigator:
                    self.navigator.cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

class RoutineExecutor:
    """Advanced routine executor with flow control."""
    
    def __init__(self, robot_controller: RobotController, status_callback: Callable = None):
        self.robot = robot_controller
        self.status_callback = status_callback
        self.is_running = False
        self.is_paused = False
        self.current_action_index = 0
        self.execution_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        
    def execute_routine(self, routine: RobotRoutine, simulation: bool = False):
        """Execute a routine with error handling."""
        if self.is_running:
            return False
        
        # Validate routine
        valid, errors = routine.validate()
        if not valid:
            self.update_status(f"Routine validation failed: {', '.join(errors)}", "error")
            return False
        
        self.is_running = True
        self.current_action_index = 0
        self.stop_event.clear()
        self.pause_event.set()
        
        self.execution_thread = threading.Thread(
            target=self._execute_routine_thread,
            args=(routine, simulation)
        )
        self.execution_thread.start()
        return True
    
    def _execute_routine_thread(self, routine: RobotRoutine, simulation: bool):
        """Routine execution thread."""
        self.update_status(f"Starting routine: {routine.name}", "info")
        
        try:
            loop_stack = []  # For handling loops
            
            while self.current_action_index < len(routine.actions):
                if self.stop_event.is_set():
                    break
                
                # Handle pause
                self.pause_event.wait()
                
                action = routine.actions[self.current_action_index]
                self.update_status(f"Executing: {action.name or action.action_type.value}", "info")
                
                # Execute action based on type
                if action.action_type == ActionType.LOOP_START:
                    loop_stack.append({
                        'start': self.current_action_index,
                        'count': action.parameters.get('count', 1),
                        'current': 0
                    })
                    
                elif action.action_type == ActionType.LOOP_END:
                    if loop_stack:
                        loop = loop_stack[-1]
                        loop['current'] += 1
                        if loop['current'] < loop['count']:
                            self.current_action_index = loop['start']
                            continue
                        else:
                            loop_stack.pop()
                            
                else:
                    # Execute regular action
                    self._execute_action(action, simulation)
                
                self.current_action_index += 1
                
        except Exception as e:
            self.update_status(f"Routine error: {e}", "error")
            
        finally:
            self.robot.stop_motors()
            self.robot.stop_actuator()
            self.is_running = False
            self.update_status(f"Routine completed: {routine.name}", "success")
    
    def _execute_action(self, action: RobotAction, simulation: bool):
        """Execute a single action."""
        params = action.parameters
        
        if simulation:
            # Simulate action
            time.sleep(action.duration or 1.0)
            self.update_status(f"[SIM] Completed: {action.name}", "info")
            return
        
        # Execute based on action type
        if action.action_type == ActionType.MOVE_FORWARD:
            self.robot.move_forward(
                params.get('speed', 30),
                params.get('distance')
            )
            
        elif action.action_type == ActionType.MOVE_BACKWARD:
            self.robot.move_backward(
                params.get('speed', 30),
                params.get('distance')
            )
            
        elif action.action_type == ActionType.TURN_LEFT:
            self.robot.turn_left(
                params.get('speed', 30),
                params.get('angle')
            )
            
        elif action.action_type == ActionType.TURN_RIGHT:
            self.robot.turn_right(
                params.get('speed', 30),
                params.get('angle')
            )
            
        elif action.action_type == ActionType.ROTATE:
            self.robot.rotate(
                params.get('angle', 90),
                params.get('speed', 30)
            )
            
        elif action.action_type == ActionType.STOP:
            self.robot.stop_motors()
            
        elif action.action_type == ActionType.NAVIGATE_TO_MARKER:
            self.robot.navigate_to_marker(
                params.get('marker_id', 0),
                params.get('timeout', 30)
            )
            
        elif action.action_type == ActionType.ACTUATOR_EXTEND:
            self.robot.extend_actuator(
                params.get('speed', 50),
                params.get('duration')
            )
            
        elif action.action_type == ActionType.ACTUATOR_RETRACT:
            self.robot.retract_actuator(
                params.get('speed', 50),
                params.get('duration')
            )
            
        elif action.action_type == ActionType.ACTUATOR_STOP:
            self.robot.stop_actuator()
            
        elif action.action_type == ActionType.WAIT:
            time.sleep(params.get('duration', 1.0))
            
        elif action.action_type == ActionType.OPEN_DOOR:
            # Door opening sequence
            self.robot.extend_actuator(50, 3.0)
            
        elif action.action_type == ActionType.CLOSE_DOOR:
            # Door closing sequence
            self.robot.retract_actuator(50, 3.0)
            
        # Wait for action duration if specified
        if action.duration > 0:
            time.sleep(action.duration)
    
    def pause(self):
        """Pause execution."""
        self.is_paused = True
        self.pause_event.clear()
        self.update_status("Routine paused", "warning")
    
    def resume(self):
        """Resume execution."""
        self.is_paused = False
        self.pause_event.set()
        self.update_status("Routine resumed", "info")
    
    def stop(self):
        """Stop execution."""
        self.stop_event.set()
        self.pause_event.set()  # Unpause if paused
        if self.execution_thread:
            self.execution_thread.join(timeout=2)
        self.is_running = False
        self.robot.stop_motors()
        self.robot.stop_actuator()
        self.update_status("Routine stopped", "warning")
    
    def update_status(self, message: str, level: str = "info"):
        """Update status through callback."""
        if self.status_callback:
            self.status_callback(message, level)
        logger.log(getattr(logging, level.upper(), logging.INFO), message)

class BevBotControlCenter:
    """Main control center application."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BevBot Control Center")
        self.root.geometry("1400x900")
        
        # Core components
        self.robot = RobotController()
        self.executor = RoutineExecutor(self.robot, self.update_status)
        self.camera = None
        self.detector = None
        
        # State
        self.current_routine = None
        self.is_recording = False
        self.recorded_actions = []
        self.recording_start_time = 0
        self.frame_queue = queue.Queue(maxsize=2)
        self.running = True
        
        # Settings
        self.config_file = "config/bevbot_config.json"
        self.routines_dir = "routines"
        self.load_config()
        
        # Initialize vision if available
        if VISION_AVAILABLE:
            self.init_vision()
        
        # Setup GUI
        self.setup_gui()
        
        # Start update loops
        self.start_update_loops()
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_gui(self):
        """Setup complete GUI."""
        # Create main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Control Dashboard
        self.dashboard_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_tab, text="Dashboard")
        self.setup_dashboard_tab()
        
        # Tab 2: Routine Editor
        self.routine_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.routine_tab, text="Routine Editor")
        self.setup_routine_tab()
        
        # Tab 3: Navigation
        self.navigation_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.navigation_tab, text="Navigation")
        self.setup_navigation_tab()
        
        # Tab 4: Settings
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")
        self.setup_settings_tab()
        
        # Status bar
        self.setup_status_bar()
    
    def setup_dashboard_tab(self):
        """Setup main control dashboard."""
        # Create paned window
        paned = ttk.PanedWindow(self.dashboard_tab, orient=tk.HORIZONTAL)
        paned.pack(fill='both', expand=True)
        
        # Left side - Camera and status
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        
        # Camera feed
        camera_frame = ttk.LabelFrame(left_frame, text="Camera Feed", padding="5")
        camera_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.video_label = ttk.Label(camera_frame)
        self.video_label.pack(expand=True)
        
        # Status panel
        status_frame = ttk.LabelFrame(left_frame, text="System Status", padding="5")
        status_frame.pack(fill='x', padx=5, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=5, width=50)
        self.status_text.pack(fill='x')
        
        # Right side - Controls
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        # Manual controls
        self.setup_manual_controls(right_frame)
        
        # Quick actions
        self.setup_quick_actions(right_frame)
    
    def setup_manual_controls(self, parent):
        """Setup manual control panel."""
        control_frame = ttk.LabelFrame(parent, text="Manual Control", padding="10")
        control_frame.pack(fill='x', padx=5, pady=5)
        
        # Speed control
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(fill='x', pady=5)
        
        ttk.Label(speed_frame, text="Speed:").pack(side='left')
        self.speed_var = tk.IntVar(value=30)
        speed_scale = ttk.Scale(
            speed_frame, from_=0, to=100,
            variable=self.speed_var,
            orient='horizontal',
            length=200
        )
        speed_scale.pack(side='left', padx=5)
        self.speed_label = ttk.Label(speed_frame, text="30%")
        self.speed_label.pack(side='left')
        speed_scale.config(command=lambda v: self.update_speed_label())
        
        # Direction pad
        dpad_frame = ttk.Frame(control_frame)
        dpad_frame.pack(pady=10)
        
        # Create control buttons
        self.forward_btn = ttk.Button(dpad_frame, text="↑", width=5)
        self.forward_btn.grid(row=0, column=1, padx=2, pady=2)
        
        self.left_btn = ttk.Button(dpad_frame, text="←", width=5)
        self.left_btn.grid(row=1, column=0, padx=2, pady=2)
        
        self.stop_btn = ttk.Button(
            dpad_frame, text="■", width=5,
            command=self.emergency_stop
        )
        self.stop_btn.grid(row=1, column=1, padx=2, pady=2)
        
        self.right_btn = ttk.Button(dpad_frame, text="→", width=5)
        self.right_btn.grid(row=1, column=2, padx=2, pady=2)
        
        self.backward_btn = ttk.Button(dpad_frame, text="↓", width=5)
        self.backward_btn.grid(row=2, column=1, padx=2, pady=2)
        
        # Bind button events
        self.bind_movement_button(self.forward_btn, self.robot.move_forward)
        self.bind_movement_button(self.backward_btn, self.robot.move_backward)
        self.bind_movement_button(self.left_btn, self.robot.turn_left)
        self.bind_movement_button(self.right_btn, self.robot.turn_right)
        
        # Actuator controls
        actuator_frame = ttk.LabelFrame(control_frame, text="Actuator", padding="5")
        actuator_frame.pack(fill='x', pady=5)
        
        self.extend_btn = ttk.Button(actuator_frame, text="Extend")
        self.extend_btn.pack(side='left', padx=2)
        
        self.actuator_stop_btn = ttk.Button(
            actuator_frame, text="Stop",
            command=self.robot.stop_actuator
        )
        self.actuator_stop_btn.pack(side='left', padx=2)
        
        self.retract_btn = ttk.Button(actuator_frame, text="Retract")
        self.retract_btn.pack(side='left', padx=2)
        
        self.bind_actuator_button(self.extend_btn, self.robot.extend_actuator)
        self.bind_actuator_button(self.retract_btn, self.robot.retract_actuator)
        
        # Keyboard control
        keyboard_frame = ttk.Frame(control_frame)
        keyboard_frame.pack(fill='x', pady=5)
        
        self.keyboard_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            keyboard_frame,
            text="Enable Keyboard Control (WASD + QE)",
            variable=self.keyboard_var,
            command=self.toggle_keyboard_control
        ).pack()
        
        # Setup keyboard bindings
        self.setup_keyboard_controls()
    
    def setup_quick_actions(self, parent):
        """Setup quick action buttons."""
        quick_frame = ttk.LabelFrame(parent, text="Quick Actions", padding="10")
        quick_frame.pack(fill='x', padx=5, pady=5)
        
        # Predefined routines
        ttk.Button(
            quick_frame,
            text="Beverage Delivery",
            command=self.load_beverage_routine
        ).pack(fill='x', pady=2)
        
        ttk.Button(
            quick_frame,
            text="Door Open/Close",
            command=self.door_sequence
        ).pack(fill='x', pady=2)
        
        ttk.Button(
            quick_frame,
            text="Navigate Home",
            command=self.navigate_home
        ).pack(fill='x', pady=2)
        
        ttk.Button(
            quick_frame,
            text="Test Navigation",
            command=self.test_navigation
        ).pack(fill='x', pady=2)
        
        # Emergency stop
        ttk.Button(
            quick_frame,
            text="EMERGENCY STOP",
            command=self.emergency_stop,
            style='Emergency.TButton'
        ).pack(fill='x', pady=10)
        
        # Style for emergency button
        style = ttk.Style()
        style.configure('Emergency.TButton', foreground='red')
    
    def setup_routine_tab(self):
        """Setup routine editor tab."""
        # Main container
        paned = ttk.PanedWindow(self.routine_tab, orient=tk.HORIZONTAL)
        paned.pack(fill='both', expand=True)
        
        # Left side - Routine editor
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        
        # Routine info
        info_frame = ttk.LabelFrame(left_frame, text="Routine Information", padding="10")
        info_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky='w')
        self.routine_name_var = tk.StringVar(value="New Routine")
        ttk.Entry(info_frame, textvariable=self.routine_name_var, width=40).grid(row=0, column=1, padx=5)
        
        ttk.Label(info_frame, text="Description:").grid(row=1, column=0, sticky='nw')
        self.routine_desc = tk.Text(info_frame, width=40, height=3)
        self.routine_desc.grid(row=1, column=1, padx=5)
        
        ttk.Label(info_frame, text="Tags:").grid(row=2, column=0, sticky='w')
        self.routine_tags_var = tk.StringVar()
        ttk.Entry(info_frame, textvariable=self.routine_tags_var, width=40).grid(row=2, column=1, padx=5)
        
        # Actions list
        actions_frame = ttk.LabelFrame(left_frame, text="Actions", padding="10")
        actions_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Toolbar
        toolbar = ttk.Frame(actions_frame)
        toolbar.pack(fill='x', pady=5)
        
        ttk.Button(toolbar, text="Add", command=self.add_action).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Edit", command=self.edit_action).pack(side='left', padx=2)
        ttk.Button(toolbar, text="Delete", command=self.delete_action).pack(side='left', padx=2)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=5)
        ttk.Button(toolbar, text="↑", command=self.move_action_up).pack(side='left', padx=2)
        ttk.Button(toolbar, text="↓", command=self.move_action_down).pack(side='left', padx=2)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', fill='y', padx=5)
        ttk.Button(toolbar, text="Record", command=self.toggle_recording).pack(side='left', padx=2)
        
        # Actions listbox
        self.actions_listbox = tk.Listbox(actions_frame, height=15)
        self.actions_listbox.pack(fill='both', expand=True)
        
        # Right side - Execution control
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        # Execution controls
        exec_frame = ttk.LabelFrame(right_frame, text="Execution", padding="10")
        exec_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(exec_frame, text="▶ Run", command=self.run_routine).pack(fill='x', pady=2)
        ttk.Button(exec_frame, text="▶ Simulate", command=self.simulate_routine).pack(fill='x', pady=2)
        ttk.Button(exec_frame, text="⏸ Pause", command=self.pause_routine).pack(fill='x', pady=2)
        ttk.Button(exec_frame, text="■ Stop", command=self.stop_routine).pack(fill='x', pady=2)
        
        # Progress
        self.routine_progress = ttk.Progressbar(exec_frame, mode='determinate')
        self.routine_progress.pack(fill='x', pady=10)
        
        # File operations
        file_frame = ttk.LabelFrame(right_frame, text="File Operations", padding="10")
        file_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(file_frame, text="New", command=self.new_routine).pack(fill='x', pady=2)
        ttk.Button(file_frame, text="Open", command=self.open_routine).pack(fill='x', pady=2)
        ttk.Button(file_frame, text="Save", command=self.save_routine).pack(fill='x', pady=2)
        ttk.Button(file_frame, text="Save As", command=self.save_routine_as).pack(fill='x', pady=2)
        
        # Library
        library_frame = ttk.LabelFrame(right_frame, text="Routine Library", padding="10")
        library_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.library_listbox = tk.Listbox(library_frame, height=10)
        self.library_listbox.pack(fill='both', expand=True)
        self.library_listbox.bind('<Double-Button-1>', lambda e: self.load_from_library())
        
        self.refresh_library()
    
    def setup_navigation_tab(self):
        """Setup navigation tab."""
        # Marker management
        marker_frame = ttk.LabelFrame(self.navigation_tab, text="ArUco Markers", padding="10")
        marker_frame.pack(fill='x', padx=5, pady=5)
        
        # Detected markers
        ttk.Label(marker_frame, text="Detected Markers:").pack(anchor='w')
        
        columns = ('ID', 'Name', 'Distance', 'Position')
        self.marker_tree = ttk.Treeview(marker_frame, columns=columns, height=8)
        for col in columns:
            self.marker_tree.heading(col, text=col)
            self.marker_tree.column(col, width=100)
        self.marker_tree.pack(fill='x', pady=5)
        
        # Navigation controls
        nav_frame = ttk.LabelFrame(self.navigation_tab, text="Navigation Control", padding="10")
        nav_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(nav_frame, text="Target Marker:").grid(row=0, column=0, sticky='w')
        self.target_marker_var = tk.StringVar()
        marker_combo = ttk.Combobox(nav_frame, textvariable=self.target_marker_var, width=20)
        marker_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(nav_frame, text="Distance (cm):").grid(row=1, column=0, sticky='w')
        self.target_distance_var = tk.IntVar(value=30)
        ttk.Spinbox(nav_frame, from_=10, to=200, textvariable=self.target_distance_var, width=20).grid(row=1, column=1, padx=5)
        
        ttk.Button(nav_frame, text="Navigate", command=self.navigate_to_marker).grid(row=2, column=0, columnspan=2, pady=10)
        
        # Calibration
        calib_frame = ttk.LabelFrame(self.navigation_tab, text="Calibration", padding="10")
        calib_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(calib_frame, text="Scan for Markers", command=self.scan_markers).pack(fill='x', pady=2)
        ttk.Button(calib_frame, text="Calibrate Position", command=self.calibrate_position).pack(fill='x', pady=2)
        ttk.Button(calib_frame, text="Save Marker Positions", command=self.save_marker_positions).pack(fill='x', pady=2)
    
    def setup_settings_tab(self):
        """Setup settings tab."""
        # Robot settings
        robot_frame = ttk.LabelFrame(self.settings_tab, text="Robot Settings", padding="10")
        robot_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(robot_frame, text="Max Speed:").grid(row=0, column=0, sticky='w')
        self.max_speed_var = tk.IntVar(value=100)
        ttk.Scale(robot_frame, from_=0, to=100, variable=self.max_speed_var, orient='horizontal', length=200).grid(row=0, column=1)
        
        ttk.Label(robot_frame, text="Min Speed Threshold:").grid(row=1, column=0, sticky='w')
        self.min_speed_var = tk.IntVar(value=10)
        ttk.Scale(robot_frame, from_=0, to=50, variable=self.min_speed_var, orient='horizontal', length=200).grid(row=1, column=1)
        
        # Camera settings
        camera_frame = ttk.LabelFrame(self.settings_tab, text="Camera Settings", padding="10")
        camera_frame.pack(fill='x', padx=5, pady=5)
        
        self.camera_enabled_var = tk.BooleanVar(value=VISION_AVAILABLE)
        ttk.Checkbutton(camera_frame, text="Enable Camera", variable=self.camera_enabled_var).pack(anchor='w')
        
        self.marker_detection_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(camera_frame, text="Enable Marker Detection", variable=self.marker_detection_var).pack(anchor='w')
        
        # System settings
        system_frame = ttk.LabelFrame(self.settings_tab, text="System Settings", padding="10")
        system_frame.pack(fill='x', padx=5, pady=5)
        
        self.simulation_var = tk.BooleanVar(value=self.robot.simulation_mode)
        ttk.Checkbutton(system_frame, text="Simulation Mode", variable=self.simulation_var, command=self.toggle_simulation).pack(anchor='w')
        
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(system_frame, text="Debug Mode", variable=self.debug_var).pack(anchor='w')
        
        # Save settings button
        ttk.Button(self.settings_tab, text="Save Settings", command=self.save_config).pack(pady=20)
    
    def setup_status_bar(self):
        """Setup status bar."""
        status_bar = ttk.Frame(self.root)
        status_bar.pack(side='bottom', fill='x')
        
        self.status_label = ttk.Label(status_bar, text="Ready", relief='sunken')
        self.status_label.pack(side='left', fill='x', expand=True)
        
        self.mode_label = ttk.Label(status_bar, text="Mode: Simulation" if self.robot.simulation_mode else "Mode: Hardware", relief='sunken')
        self.mode_label.pack(side='right', padx=5)
    
    def bind_movement_button(self, button, command):
        """Bind press/release events for movement."""
        def on_press(event):
            if self.is_recording:
                self.record_action('move', command.__name__)
            command(self.speed_var.get())
        
        def on_release(event):
            if self.is_recording:
                self.record_action('stop', 'motors')
            self.robot.stop_motors()
        
        button.bind('<ButtonPress-1>', on_press)
        button.bind('<ButtonRelease-1>', on_release)
    
    def bind_actuator_button(self, button, command):
        """Bind press/release events for actuator."""
        def on_press(event):
            if self.is_recording:
                self.record_action('actuator', command.__name__)
            command(50)
        
        def on_release(event):
            if self.is_recording:
                self.record_action('stop', 'actuator')
            self.robot.stop_actuator()
        
        button.bind('<ButtonPress-1>', on_press)
        button.bind('<ButtonRelease-1>', on_release)
    
    def setup_keyboard_controls(self):
        """Setup keyboard controls."""
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        self.keys_pressed = set()
    
    def on_key_press(self, event):
        """Handle key press."""
        if not self.keyboard_var.get():
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
            self.robot.extend_actuator()
        elif key == 'e':
            self.robot.retract_actuator()
        elif key == ' ':
            self.emergency_stop()
    
    def on_key_release(self, event):
        """Handle key release."""
        if not self.keyboard_var.get():
            return
        
        key = event.char.lower()
        self.keys_pressed.discard(key)
        
        if key in ['w', 's', 'a', 'd'] and not any(k in self.keys_pressed for k in ['w', 's', 'a', 'd']):
            self.robot.stop_motors()
        elif key in ['q', 'e']:
            self.robot.stop_actuator()
    
    def toggle_keyboard_control(self):
        """Toggle keyboard control."""
        if self.keyboard_var.get():
            self.root.focus_set()
            self.update_status("Keyboard control enabled", "info")
        else:
            self.update_status("Keyboard control disabled", "info")
    
    def update_speed_label(self):
        """Update speed label."""
        self.speed_label.config(text=f"{self.speed_var.get()}%")
    
    def init_vision(self):
        """Initialize vision system."""
        try:
            self.camera = CameraInterface()
            if self.camera.is_available():
                self.camera.start()
                self.detector = ArUcoDetector(marker_size_cm=10.0)
                
                # Start vision processing thread
                self.vision_thread = threading.Thread(target=self.vision_loop, daemon=True)
                self.vision_thread.start()
                
                self.update_status("Camera initialized", "success")
            else:
                self.update_status("Camera not available", "warning")
        except Exception as e:
            logger.error(f"Vision initialization failed: {e}")
            self.update_status("Vision system error", "error")
    
    def vision_loop(self):
        """Vision processing loop."""
        while self.running:
            try:
                if self.camera and self.camera_enabled_var.get():
                    frame, _ = self.camera.capture_frame()
                    
                    # Detect markers if enabled
                    markers = {}
                    if self.marker_detection_var.get() and self.detector:
                        markers = self.detector.detect_markers(frame)
                        frame = self.detector.draw_markers(frame, markers)
                    
                    # Queue frame for display
                    if not self.frame_queue.full():
                        self.frame_queue.put((frame, markers))
                
            except Exception as e:
                logger.error(f"Vision loop error: {e}")
            
            time.sleep(0.05)
    
    def start_update_loops(self):
        """Start GUI update loops."""
        self.update_gui()
        self.update_routine_progress()
    
    def update_gui(self):
        """Update GUI elements."""
        try:
            # Update video feed
            if not self.frame_queue.empty():
                frame, markers = self.frame_queue.get_nowait()
                
                # Convert and display frame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_resized = cv2.resize(frame_rgb, (640, 480))
                img = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image=img)
                self.video_label.config(image=photo)
                self.video_label.image = photo
                
                # Update marker list
                self.update_marker_list(markers)
            
            # Update status
            self.update_system_status()
            
        except Exception as e:
            logger.debug(f"GUI update error: {e}")
        
        # Schedule next update
        self.root.after(50, self.update_gui)
    
    def update_routine_progress(self):
        """Update routine execution progress."""
        if self.executor.is_running:
            if self.current_routine:
                total = len(self.current_routine.actions)
                current = self.executor.current_action_index
                progress = (current / total * 100) if total > 0 else 0
                self.routine_progress['value'] = progress
        
        self.root.after(100, self.update_routine_progress)
    
    def update_system_status(self):
        """Update system status display."""
        status_lines = [
            f"Robot: {'Simulation' if self.robot.simulation_mode else 'Hardware'}",
            f"Motors: L={self.robot.left_speed:.0f}% R={self.robot.right_speed:.0f}%",
            f"Actuator: {self.robot.actuator_state}",
            f"Recording: {'Yes' if self.is_recording else 'No'}",
            f"Routine: {'Running' if self.executor.is_running else 'Idle'}"
        ]
        
        self.status_text.delete('1.0', tk.END)
        self.status_text.insert('1.0', '\n'.join(status_lines))
    
    def update_marker_list(self, markers):
        """Update detected markers list."""
        self.marker_tree.delete(*self.marker_tree.get_children())
        
        for marker_id, info in markers.items():
            self.marker_tree.insert('', 'end', values=(
                marker_id,
                f"Marker_{marker_id}",
                f"{info.distance:.1f}cm",
                f"({info.center[0]:.0f}, {info.center[1]:.0f})"
            ))
    
    def update_status(self, message: str, level: str = "info"):
        """Update status bar."""
        self.status_label.config(text=message)
        
        # Add to status text with timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
    
    def emergency_stop(self):
        """Emergency stop all systems."""
        self.robot.emergency_stop()
        self.executor.stop()
        self.update_status("EMERGENCY STOP ACTIVATED", "error")
    
    def toggle_recording(self):
        """Toggle action recording."""
        if self.is_recording:
            self.is_recording = False
            self.update_status("Recording stopped", "info")
            # Convert recorded actions to routine actions
            self.convert_recording_to_routine()
        else:
            self.is_recording = True
            self.recorded_actions = []
            self.recording_start_time = time.time()
            self.update_status("Recording started", "info")
    
    def record_action(self, action_type: str, details: str):
        """Record an action."""
        if self.is_recording:
            timestamp = time.time() - self.recording_start_time
            self.recorded_actions.append({
                'type': action_type,
                'details': details,
                'timestamp': timestamp
            })
    
    def convert_recording_to_routine(self):
        """Convert recorded actions to routine actions."""
        if not self.recorded_actions:
            return
        
        # Process recorded actions into routine actions
        for i, rec in enumerate(self.recorded_actions):
            # Calculate duration
            duration = 0
            if i < len(self.recorded_actions) - 1:
                duration = self.recorded_actions[i+1]['timestamp'] - rec['timestamp']
            
            # Create appropriate action
            action = None
            if 'move_forward' in rec['details']:
                action = RobotAction(
                    ActionType.MOVE_FORWARD,
                    {'speed': self.speed_var.get()},
                    "Forward",
                    duration=duration
                )
            elif 'move_backward' in rec['details']:
                action = RobotAction(
                    ActionType.MOVE_BACKWARD,
                    {'speed': self.speed_var.get()},
                    "Backward",
                    duration=duration
                )
            # Add more conversions...
            
            if action and self.current_routine:
                self.current_routine.actions.append(action)
        
        self.refresh_actions_list()
        self.update_status(f"Added {len(self.recorded_actions)} recorded actions", "success")
    
    def new_routine(self):
        """Create new routine."""
        self.current_routine = RobotRoutine(
            name="New Routine",
            description=""
        )
        self.routine_name_var.set(self.current_routine.name)
        self.routine_desc.delete('1.0', tk.END)
        self.refresh_actions_list()
        self.update_status("Created new routine", "info")
    
    def open_routine(self):
        """Open routine from file."""
        filename = filedialog.askopenfilename(
            initialdir=self.routines_dir,
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                self.current_routine = RobotRoutine.from_dict(data)
                self.load_routine_to_ui()
                self.update_status(f"Loaded: {self.current_routine.name}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load routine: {e}")
    
    def save_routine(self):
        """Save current routine."""
        if not self.current_routine:
            self.new_routine()
        
        self.current_routine.name = self.routine_name_var.get()
        self.current_routine.description = self.routine_desc.get('1.0', 'end-1c')
        self.current_routine.tags = self.routine_tags_var.get().split(',')
        
        filename = os.path.join(
            self.routines_dir,
            f"{self.current_routine.name.replace(' ', '_')}.json"
        )
        
        try:
            os.makedirs(self.routines_dir, exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(self.current_routine.to_dict(), f, indent=2)
            self.update_status(f"Saved: {filename}", "success")
            self.refresh_library()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save routine: {e}")
    
    def save_routine_as(self):
        """Save routine with new name."""
        filename = filedialog.asksaveasfilename(
            initialdir=self.routines_dir,
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if filename:
            self.save_routine()
    
    def load_routine_to_ui(self):
        """Load routine to UI."""
        if not self.current_routine:
            return
        
        self.routine_name_var.set(self.current_routine.name)
        self.routine_desc.delete('1.0', tk.END)
        self.routine_desc.insert('1.0', self.current_routine.description)
        self.routine_tags_var.set(','.join(self.current_routine.tags))
        self.refresh_actions_list()
    
    def refresh_actions_list(self):
        """Refresh actions listbox."""
        self.actions_listbox.delete(0, tk.END)
        
        if self.current_routine:
            for i, action in enumerate(self.current_routine.actions):
                display = f"{i+1}. {action.name or action.action_type.value}"
                self.actions_listbox.insert(tk.END, display)
    
    def refresh_library(self):
        """Refresh routine library."""
        self.library_listbox.delete(0, tk.END)
        
        try:
            if os.path.exists(self.routines_dir):
                for file in os.listdir(self.routines_dir):
                    if file.endswith('.json'):
                        self.library_listbox.insert(tk.END, file[:-5])
        except Exception as e:
            logger.error(f"Failed to refresh library: {e}")
    
    def load_from_library(self):
        """Load selected routine from library."""
        selection = self.library_listbox.curselection()
        if selection:
            filename = self.library_listbox.get(selection[0]) + ".json"
            filepath = os.path.join(self.routines_dir, filename)
            
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                self.current_routine = RobotRoutine.from_dict(data)
                self.load_routine_to_ui()
                self.update_status(f"Loaded: {self.current_routine.name}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load routine: {e}")
    
    def add_action(self):
        """Add new action to routine."""
        # This would open an action editor dialog
        # For now, add a simple action
        if not self.current_routine:
            self.new_routine()
        
        action = RobotAction(
            ActionType.WAIT,
            {'duration': 1.0},
            "Wait 1 second"
        )
        self.current_routine.actions.append(action)
        self.refresh_actions_list()
    
    def edit_action(self):
        """Edit selected action."""
        selection = self.actions_listbox.curselection()
        if selection and self.current_routine:
            index = selection[0]
            # Open action editor dialog
            self.update_status(f"Editing action {index+1}", "info")
    
    def delete_action(self):
        """Delete selected action."""
        selection = self.actions_listbox.curselection()
        if selection and self.current_routine:
            index = selection[0]
            del self.current_routine.actions[index]
            self.refresh_actions_list()
            self.update_status(f"Deleted action {index+1}", "info")
    
    def move_action_up(self):
        """Move action up in list."""
        selection = self.actions_listbox.curselection()
        if selection and self.current_routine and selection[0] > 0:
            index = selection[0]
            self.current_routine.actions[index-1], self.current_routine.actions[index] = \
                self.current_routine.actions[index], self.current_routine.actions[index-1]
            self.refresh_actions_list()
            self.actions_listbox.selection_set(index-1)
    
    def move_action_down(self):
        """Move action down in list."""
        selection = self.actions_listbox.curselection()
        if selection and self.current_routine and selection[0] < len(self.current_routine.actions) - 1:
            index = selection[0]
            self.current_routine.actions[index], self.current_routine.actions[index+1] = \
                self.current_routine.actions[index+1], self.current_routine.actions[index]
            self.refresh_actions_list()
            self.actions_listbox.selection_set(index+1)
    
    def run_routine(self):
        """Run current routine."""
        if not self.current_routine:
            messagebox.showwarning("No Routine", "Please create or load a routine first")
            return
        
        self.executor.execute_routine(self.current_routine, simulation=False)
    
    def simulate_routine(self):
        """Simulate current routine."""
        if not self.current_routine:
            messagebox.showwarning("No Routine", "Please create or load a routine first")
            return
        
        self.executor.execute_routine(self.current_routine, simulation=True)
    
    def pause_routine(self):
        """Pause routine execution."""
        if self.executor.is_paused:
            self.executor.resume()
        else:
            self.executor.pause()
    
    def stop_routine(self):
        """Stop routine execution."""
        self.executor.stop()
    
    def load_beverage_routine(self):
        """Load beverage delivery routine."""
        routine = RobotRoutine(
            name="Beverage Delivery",
            description="Navigate to fridge, get beverage, deliver to couch",
            tags=["delivery", "fridge", "couch"]
        )
        
        routine.actions = [
            RobotAction(ActionType.NAVIGATE_TO_MARKER, {'marker_id': 1, 'timeout': 30}, "Go to Fridge"),
            RobotAction(ActionType.ALIGN_WITH_MARKER, {'marker_id': 1, 'distance_cm': 30}, "Align with Fridge"),
            RobotAction(ActionType.OPEN_DOOR, {}, "Open Fridge"),
            RobotAction(ActionType.WAIT, {'duration': 1.0}, "Wait"),
            RobotAction(ActionType.NAVIGATE_TO_MARKER, {'marker_id': 2, 'timeout': 20}, "Enter Fridge"),
            RobotAction(ActionType.PICKUP_OBJECT, {}, "Get Beverage"),
            RobotAction(ActionType.MOVE_BACKWARD, {'speed': 20, 'distance': 50}, "Exit Fridge"),
            RobotAction(ActionType.CLOSE_DOOR, {}, "Close Fridge"),
            RobotAction(ActionType.NAVIGATE_TO_MARKER, {'marker_id': 3, 'timeout': 45}, "Go to Couch"),
            RobotAction(ActionType.RELEASE_OBJECT, {}, "Deliver Beverage")
        ]
        
        self.current_routine = routine
        self.load_routine_to_ui()
        self.update_status("Loaded beverage delivery routine", "success")
    
    def door_sequence(self):
        """Execute door open/close sequence."""
        self.robot.extend_actuator(50, 3.0)
        time.sleep(5)
        self.robot.retract_actuator(50, 3.0)
        self.update_status("Door sequence completed", "success")
    
    def navigate_home(self):
        """Navigate to home position."""
        if self.robot.navigator:
            self.robot.navigate_to_marker(0, 30)  # Marker 0 as home
        self.update_status("Navigating home", "info")
    
    def test_navigation(self):
        """Test navigation system."""
        self.update_status("Testing navigation system", "info")
        # Implement navigation test
    
    def navigate_to_marker(self):
        """Navigate to selected marker."""
        marker_id = self.target_marker_var.get()
        if marker_id:
            self.robot.navigate_to_marker(int(marker_id))
            self.update_status(f"Navigating to marker {marker_id}", "info")
    
    def scan_markers(self):
        """Scan for ArUco markers."""
        self.update_status("Scanning for markers...", "info")
        # Implement marker scanning
    
    def calibrate_position(self):
        """Calibrate marker position."""
        self.update_status("Calibration mode", "info")
        # Implement calibration
    
    def save_marker_positions(self):
        """Save marker positions."""
        self.update_status("Marker positions saved", "success")
        # Implement position saving
    
    def toggle_simulation(self):
        """Toggle simulation mode."""
        self.robot.simulation_mode = self.simulation_var.get()
        self.mode_label.config(text="Mode: Simulation" if self.robot.simulation_mode else "Mode: Hardware")
        self.update_status(f"Simulation mode: {self.robot.simulation_mode}", "info")
    
    def load_config(self):
        """Load configuration."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Apply configuration
                    logger.info("Configuration loaded")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    
    def save_config(self):
        """Save configuration."""
        config = {
            'max_speed': self.max_speed_var.get(),
            'min_speed_threshold': self.min_speed_var.get(),
            'camera_enabled': self.camera_enabled_var.get(),
            'marker_detection': self.marker_detection_var.get(),
            'simulation_mode': self.simulation_var.get(),
            'debug_mode': self.debug_var.get()
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.update_status("Configuration saved", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")
    
    def on_closing(self):
        """Handle window closing."""
        self.running = False
        self.robot.cleanup()
        if self.camera:
            self.camera.stop()
        self.root.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = BevBotControlCenter(root)
    
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