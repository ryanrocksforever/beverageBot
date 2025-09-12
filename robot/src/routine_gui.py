#!/usr/bin/env python3
"""
BevBot Routine Creator GUI
A comprehensive GUI application for creating, editing, and executing robot routines
with ArUco marker navigation and custom actions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import queue
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ActionType(Enum):
    """Types of actions the robot can perform."""
    NAVIGATE_TO_MARKER = "navigate_to_marker"
    ALIGN_WITH_MARKER = "align_with_marker"
    OPEN_DOOR = "open_door"
    CLOSE_DOOR = "close_door"
    PICKUP_OBJECT = "pickup_object"
    RELEASE_OBJECT = "release_object"
    WAIT = "wait"
    ROTATE = "rotate"
    MOVE_FORWARD = "move_forward"
    MOVE_BACKWARD = "move_backward"
    CUSTOM_SCRIPT = "custom_script"

@dataclass
class RobotAction:
    """Represents a single action in a robot routine."""
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    name: str = ""
    description: str = ""
    
    def to_dict(self):
        return {
            'action_type': self.action_type.value,
            'parameters': self.parameters,
            'name': self.name,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            action_type=ActionType(data['action_type']),
            parameters=data.get('parameters', {}),
            name=data.get('name', ''),
            description=data.get('description', '')
        )

@dataclass
class RobotRoutine:
    """Represents a complete robot routine."""
    name: str
    description: str
    actions: List[RobotAction] = field(default_factory=list)
    created_at: str = ""
    modified_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'actions': [action.to_dict() for action in self.actions],
            'created_at': self.created_at,
            'modified_at': self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data):
        routine = cls(
            name=data['name'],
            description=data.get('description', ''),
            created_at=data.get('created_at', ''),
            modified_at=data.get('modified_at', '')
        )
        routine.actions = [RobotAction.from_dict(a) for a in data.get('actions', [])]
        return routine

class MarkerDatabase:
    """Manages ArUco marker definitions and positions."""
    
    def __init__(self, db_file="marker_database.json"):
        self.db_file = db_file
        self.markers = {}
        self.load()
    
    def load(self):
        """Load marker database from file."""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.markers = data.get('markers', {})
            except Exception as e:
                logger.error(f"Failed to load marker database: {e}")
                self.markers = {}
    
    def save(self):
        """Save marker database to file."""
        try:
            with open(self.db_file, 'w') as f:
                json.dump({'markers': self.markers}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save marker database: {e}")
    
    def add_marker(self, marker_id: int, name: str, location: str, distance_cm: float = 30.0):
        """Add or update a marker definition."""
        self.markers[str(marker_id)] = {
            'id': marker_id,
            'name': name,
            'location': location,
            'default_distance_cm': distance_cm
        }
        self.save()
    
    def get_marker(self, marker_id: int) -> Optional[Dict]:
        """Get marker information."""
        return self.markers.get(str(marker_id))
    
    def get_all_markers(self) -> Dict:
        """Get all markers."""
        return self.markers

class ActionEditor(tk.Toplevel):
    """Dialog for editing a single action."""
    
    def __init__(self, parent, action: Optional[RobotAction] = None, marker_db: MarkerDatabase = None):
        super().__init__(parent)
        self.parent = parent
        self.action = action
        self.marker_db = marker_db or MarkerDatabase()
        self.result = None
        
        self.title("Edit Action" if action else "Add Action")
        self.geometry("500x600")
        self.resizable(False, False)
        
        self.create_widgets()
        
        if action:
            self.load_action(action)
        
        # Center the window
        self.transient(parent)
        self.grab_set()
        
    def create_widgets(self):
        """Create the editor widgets."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Action Type Selection
        ttk.Label(main_frame, text="Action Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.action_type_var = tk.StringVar()
        self.action_type_combo = ttk.Combobox(
            main_frame, 
            textvariable=self.action_type_var,
            values=[t.value for t in ActionType],
            state='readonly',
            width=30
        )
        self.action_type_combo.grid(row=0, column=1, pady=5, padx=5)
        self.action_type_combo.bind('<<ComboboxSelected>>', self.on_action_type_changed)
        
        # Action Name
        ttk.Label(main_frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=32).grid(row=1, column=1, pady=5, padx=5)
        
        # Description
        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(main_frame, width=30, height=3)
        self.description_text.grid(row=2, column=1, pady=5, padx=5)
        
        # Parameters Frame
        ttk.Label(main_frame, text="Parameters:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.params_frame = ttk.LabelFrame(main_frame, text="", padding="5")
        self.params_frame.grid(row=3, column=1, pady=5, padx=5, sticky=tk.NSEW)
        
        # Parameter widgets will be dynamically created
        self.param_widgets = {}
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
    def on_action_type_changed(self, event=None):
        """Handle action type change."""
        action_type = ActionType(self.action_type_var.get())
        self.create_parameter_widgets(action_type)
    
    def create_parameter_widgets(self, action_type: ActionType):
        """Create parameter input widgets based on action type."""
        # Clear existing widgets
        for widget in self.params_frame.winfo_children():
            widget.destroy()
        self.param_widgets.clear()
        
        row = 0
        
        if action_type == ActionType.NAVIGATE_TO_MARKER:
            # Marker ID selection
            ttk.Label(self.params_frame, text="Marker:").grid(row=row, column=0, sticky=tk.W, pady=2)
            marker_var = tk.StringVar()
            
            # Create marker selection combo
            markers = self.marker_db.get_all_markers()
            marker_values = []
            for mid, minfo in markers.items():
                marker_values.append(f"{mid}: {minfo['name']} ({minfo['location']})")
            
            marker_combo = ttk.Combobox(self.params_frame, textvariable=marker_var, 
                                       values=marker_values, width=25)
            marker_combo.grid(row=row, column=1, pady=2)
            self.param_widgets['marker_id'] = marker_var
            row += 1
            
            # Timeout
            ttk.Label(self.params_frame, text="Timeout (s):").grid(row=row, column=0, sticky=tk.W, pady=2)
            timeout_var = tk.StringVar(value="30")
            ttk.Entry(self.params_frame, textvariable=timeout_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['timeout'] = timeout_var
            
        elif action_type == ActionType.ALIGN_WITH_MARKER:
            # Marker ID
            ttk.Label(self.params_frame, text="Marker ID:").grid(row=row, column=0, sticky=tk.W, pady=2)
            marker_var = tk.StringVar()
            ttk.Entry(self.params_frame, textvariable=marker_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['marker_id'] = marker_var
            row += 1
            
            # Distance
            ttk.Label(self.params_frame, text="Distance (cm):").grid(row=row, column=0, sticky=tk.W, pady=2)
            distance_var = tk.StringVar(value="30")
            ttk.Entry(self.params_frame, textvariable=distance_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['distance_cm'] = distance_var
            row += 1
            
            # Tolerance
            ttk.Label(self.params_frame, text="Tolerance (cm):").grid(row=row, column=0, sticky=tk.W, pady=2)
            tolerance_var = tk.StringVar(value="5")
            ttk.Entry(self.params_frame, textvariable=tolerance_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['tolerance_cm'] = tolerance_var
            
        elif action_type == ActionType.WAIT:
            ttk.Label(self.params_frame, text="Duration (s):").grid(row=row, column=0, sticky=tk.W, pady=2)
            duration_var = tk.StringVar(value="1.0")
            ttk.Entry(self.params_frame, textvariable=duration_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['duration'] = duration_var
            
        elif action_type == ActionType.ROTATE:
            ttk.Label(self.params_frame, text="Angle (degrees):").grid(row=row, column=0, sticky=tk.W, pady=2)
            angle_var = tk.StringVar(value="90")
            ttk.Entry(self.params_frame, textvariable=angle_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['angle'] = angle_var
            row += 1
            
            ttk.Label(self.params_frame, text="Speed:").grid(row=row, column=0, sticky=tk.W, pady=2)
            speed_var = tk.StringVar(value="30")
            ttk.Entry(self.params_frame, textvariable=speed_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['speed'] = speed_var
            
        elif action_type in [ActionType.MOVE_FORWARD, ActionType.MOVE_BACKWARD]:
            ttk.Label(self.params_frame, text="Distance (cm):").grid(row=row, column=0, sticky=tk.W, pady=2)
            distance_var = tk.StringVar(value="50")
            ttk.Entry(self.params_frame, textvariable=distance_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['distance'] = distance_var
            row += 1
            
            ttk.Label(self.params_frame, text="Speed:").grid(row=row, column=0, sticky=tk.W, pady=2)
            speed_var = tk.StringVar(value="30")
            ttk.Entry(self.params_frame, textvariable=speed_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['speed'] = speed_var
            
        elif action_type == ActionType.CUSTOM_SCRIPT:
            ttk.Label(self.params_frame, text="Script:").grid(row=row, column=0, sticky=tk.NW, pady=2)
            script_text = tk.Text(self.params_frame, width=25, height=5)
            script_text.grid(row=row, column=1, pady=2)
            self.param_widgets['script'] = script_text
            
        elif action_type in [ActionType.OPEN_DOOR, ActionType.CLOSE_DOOR]:
            ttk.Label(self.params_frame, text="Duration (s):").grid(row=row, column=0, sticky=tk.W, pady=2)
            duration_var = tk.StringVar(value="3.0")
            ttk.Entry(self.params_frame, textvariable=duration_var, width=10).grid(row=row, column=1, sticky=tk.W, pady=2)
            self.param_widgets['duration'] = duration_var
            
    def load_action(self, action: RobotAction):
        """Load an existing action for editing."""
        self.action_type_var.set(action.action_type.value)
        self.name_var.set(action.name)
        self.description_text.insert('1.0', action.description)
        
        # Create parameter widgets
        self.create_parameter_widgets(action.action_type)
        
        # Load parameter values
        for param_name, param_value in action.parameters.items():
            if param_name in self.param_widgets:
                widget = self.param_widgets[param_name]
                if isinstance(widget, tk.StringVar):
                    widget.set(str(param_value))
                elif isinstance(widget, tk.Text):
                    widget.insert('1.0', str(param_value))
    
    def ok_clicked(self):
        """Handle OK button click."""
        try:
            # Get action type
            action_type = ActionType(self.action_type_var.get())
            
            # Get parameters
            parameters = {}
            for param_name, widget in self.param_widgets.items():
                if isinstance(widget, tk.StringVar):
                    value = widget.get()
                    # Try to convert to appropriate type
                    if param_name in ['marker_id']:
                        # Extract marker ID from combo selection
                        if ':' in value:
                            value = int(value.split(':')[0])
                        else:
                            value = int(value) if value else 0
                    elif param_name in ['timeout', 'duration', 'distance', 'distance_cm', 'tolerance_cm', 'speed']:
                        value = float(value) if value else 0.0
                    elif param_name in ['angle']:
                        value = int(value) if value else 0
                    parameters[param_name] = value
                elif isinstance(widget, tk.Text):
                    parameters[param_name] = widget.get('1.0', 'end-1c')
            
            # Create action
            self.result = RobotAction(
                action_type=action_type,
                parameters=parameters,
                name=self.name_var.get(),
                description=self.description_text.get('1.0', 'end-1c').strip()
            )
            
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
    
    def cancel_clicked(self):
        """Handle Cancel button click."""
        self.result = None
        self.destroy()

class RoutineExecutor:
    """Executes robot routines."""
    
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.is_running = False
        self.current_action_index = 0
        self.navigator = None
        self.simulation_mode = True
        
    def initialize_hardware(self):
        """Initialize hardware components."""
        try:
            from aruco_navigation import ArUcoNavigator
            self.navigator = ArUcoNavigator(simulation_mode=self.simulation_mode)
            if not self.navigator.init_camera():
                raise Exception("Failed to initialize camera")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            return False
    
    def execute_routine(self, routine: RobotRoutine, simulation: bool = True):
        """Execute a complete routine."""
        self.simulation_mode = simulation
        self.is_running = True
        self.current_action_index = 0
        
        if not simulation and not self.initialize_hardware():
            self.update_status("Failed to initialize hardware", "error")
            return False
        
        self.update_status(f"Starting routine: {routine.name}", "info")
        
        for i, action in enumerate(routine.actions):
            if not self.is_running:
                self.update_status("Routine stopped by user", "warning")
                break
            
            self.current_action_index = i
            self.execute_action(action)
        
        self.update_status(f"Routine completed: {routine.name}", "success")
        
        if self.navigator:
            self.navigator.cleanup()
        
        return True
    
    def execute_action(self, action: RobotAction):
        """Execute a single action."""
        self.update_status(f"Executing: {action.name or action.action_type.value}", "info")
        
        if self.simulation_mode:
            # Simulate action execution
            time.sleep(1.0)
            self.update_status(f"[SIM] Completed: {action.name}", "success")
            return
        
        try:
            if action.action_type == ActionType.NAVIGATE_TO_MARKER:
                marker_id = action.parameters.get('marker_id', 0)
                timeout = action.parameters.get('timeout', 30)
                if self.navigator:
                    success = self.navigator.navigate_to_marker(marker_id, timeout)
                    if not success:
                        self.update_status(f"Failed to navigate to marker {marker_id}", "error")
                        
            elif action.action_type == ActionType.WAIT:
                duration = action.parameters.get('duration', 1.0)
                time.sleep(duration)
                
            elif action.action_type == ActionType.ROTATE:
                angle = action.parameters.get('angle', 90)
                speed = action.parameters.get('speed', 30)
                # Implement rotation logic
                self.update_status(f"Rotating {angle} degrees", "info")
                time.sleep(abs(angle) / 45.0)  # Rough estimate
                
            elif action.action_type in [ActionType.MOVE_FORWARD, ActionType.MOVE_BACKWARD]:
                distance = action.parameters.get('distance', 50)
                speed = action.parameters.get('speed', 30)
                direction = 1 if action.action_type == ActionType.MOVE_FORWARD else -1
                # Implement movement logic
                self.update_status(f"Moving {'forward' if direction > 0 else 'backward'} {distance}cm", "info")
                time.sleep(distance / 20.0)  # Rough estimate
                
            elif action.action_type == ActionType.OPEN_DOOR:
                # Implement door opening logic
                self.update_status("Opening door", "info")
                time.sleep(3.0)
                
            elif action.action_type == ActionType.CLOSE_DOOR:
                # Implement door closing logic
                self.update_status("Closing door", "info")
                time.sleep(3.0)
                
            elif action.action_type == ActionType.PICKUP_OBJECT:
                # Implement pickup logic
                self.update_status("Picking up object", "info")
                time.sleep(2.0)
                
            elif action.action_type == ActionType.RELEASE_OBJECT:
                # Implement release logic
                self.update_status("Releasing object", "info")
                time.sleep(1.0)
                
        except Exception as e:
            self.update_status(f"Error executing action: {e}", "error")
    
    def stop(self):
        """Stop routine execution."""
        self.is_running = False
        if self.navigator:
            self.navigator._stop_motors()
    
    def update_status(self, message: str, level: str = "info"):
        """Update status through callback."""
        if self.status_callback:
            self.status_callback(message, level)
        logger.log(getattr(logging, level.upper(), logging.INFO), message)

class BevBotRoutineGUI:
    """Main GUI application for BevBot routine creation."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("BevBot Routine Creator")
        self.root.geometry("1200x800")
        
        # Data
        self.current_routine = None
        self.routines_dir = "routines"
        self.marker_db = MarkerDatabase()
        self.executor = RoutineExecutor(self.update_status)
        self.execution_thread = None
        
        # Create routines directory
        os.makedirs(self.routines_dir, exist_ok=True)
        
        # Setup UI
        self.setup_menu()
        self.setup_ui()
        
        # Load default routine if exists
        self.load_recent_routine()
        
    def setup_menu(self):
        """Setup application menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Routine", command=self.new_routine, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Routine...", command=self.open_routine, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Routine", command=self.save_routine, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_routine_as)
        file_menu.add_separator()
        file_menu.add_command(label="Import...", command=self.import_routine)
        file_menu.add_command(label="Export...", command=self.export_routine)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Add Action", command=self.add_action)
        edit_menu.add_command(label="Edit Action", command=self.edit_action)
        edit_menu.add_command(label="Delete Action", command=self.delete_action)
        edit_menu.add_separator()
        edit_menu.add_command(label="Move Up", command=self.move_action_up)
        edit_menu.add_command(label="Move Down", command=self.move_action_down)
        
        # Markers menu
        markers_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Markers", menu=markers_menu)
        markers_menu.add_command(label="Manage Markers...", command=self.manage_markers)
        markers_menu.add_command(label="Scan for Markers", command=self.scan_markers)
        markers_menu.add_command(label="Calibrate Position", command=self.calibrate_position)
        
        # Execute menu
        execute_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Execute", menu=execute_menu)
        execute_menu.add_command(label="Run Routine", command=self.run_routine, accelerator="F5")
        execute_menu.add_command(label="Run in Simulation", command=self.run_simulation, accelerator="F6")
        execute_menu.add_command(label="Stop", command=self.stop_routine, accelerator="Esc")
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self.show_documentation)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Bind shortcuts
        self.root.bind('<Control-n>', lambda e: self.new_routine())
        self.root.bind('<Control-o>', lambda e: self.open_routine())
        self.root.bind('<Control-s>', lambda e: self.save_routine())
        self.root.bind('<F5>', lambda e: self.run_routine())
        self.root.bind('<F6>', lambda e: self.run_simulation())
        self.root.bind('<Escape>', lambda e: self.stop_routine())
        
    def setup_ui(self):
        """Setup main UI components."""
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Routine editor
        left_frame = ttk.Frame(main_container)
        main_container.add(left_frame, weight=2)
        
        # Routine info
        info_frame = ttk.LabelFrame(left_frame, text="Routine Information", padding="10")
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.routine_name_var = tk.StringVar(value="New Routine")
        ttk.Entry(info_frame, textvariable=self.routine_name_var, width=40).grid(row=0, column=1, pady=2, padx=5)
        
        ttk.Label(info_frame, text="Description:").grid(row=1, column=0, sticky=tk.NW, pady=2)
        self.routine_desc_text = tk.Text(info_frame, width=40, height=3)
        self.routine_desc_text.grid(row=1, column=1, pady=2, padx=5)
        
        # Actions list
        actions_frame = ttk.LabelFrame(left_frame, text="Actions", padding="10")
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Toolbar
        toolbar = ttk.Frame(actions_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="Add", command=self.add_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit", command=self.edit_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete", command=self.delete_action).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(toolbar, text="↑", command=self.move_action_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="↓", command=self.move_action_down).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Button(toolbar, text="Duplicate", command=self.duplicate_action).pack(side=tk.LEFT, padx=2)
        
        # Actions listbox with scrollbar
        list_frame = ttk.Frame(actions_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.actions_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
        self.actions_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.actions_listbox.yview)
        
        self.actions_listbox.bind('<Double-Button-1>', lambda e: self.edit_action())
        
        # Right panel - Execution and monitoring
        right_frame = ttk.Frame(main_container)
        main_container.add(right_frame, weight=1)
        
        # Control panel
        control_frame = ttk.LabelFrame(right_frame, text="Execution Control", padding="10")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="▶ Run", command=self.run_routine, width=15).pack(pady=2)
        ttk.Button(control_frame, text="▶ Simulate", command=self.run_simulation, width=15).pack(pady=2)
        ttk.Button(control_frame, text="■ Stop", command=self.stop_routine, width=15).pack(pady=2)
        
        # Quick actions
        quick_frame = ttk.LabelFrame(right_frame, text="Quick Actions", padding="10")
        quick_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(quick_frame, text="Fridge → Couch", 
                  command=self.create_fridge_couch_routine, width=15).pack(pady=2)
        ttk.Button(quick_frame, text="Test Navigation", 
                  command=self.test_navigation, width=15).pack(pady=2)
        ttk.Button(quick_frame, text="Calibrate Markers", 
                  command=self.calibrate_position, width=15).pack(pady=2)
        
        # Status panel
        status_frame = ttk.LabelFrame(right_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=15, width=40)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Progress bar
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(right_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def new_routine(self):
        """Create a new routine."""
        self.current_routine = RobotRoutine(name="New Routine", description="")
        self.routine_name_var.set(self.current_routine.name)
        self.routine_desc_text.delete('1.0', tk.END)
        self.actions_listbox.delete(0, tk.END)
        self.update_status("Created new routine", "info")
        
    def open_routine(self):
        """Open an existing routine."""
        filename = filedialog.askopenfilename(
            initialdir=self.routines_dir,
            title="Open Routine",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                self.current_routine = RobotRoutine.from_dict(data)
                self.load_routine_to_ui()
                self.update_status(f"Loaded routine: {self.current_routine.name}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load routine: {e}")
                
    def save_routine(self):
        """Save the current routine."""
        if not self.current_routine:
            self.current_routine = RobotRoutine(
                name=self.routine_name_var.get(),
                description=self.routine_desc_text.get('1.0', 'end-1c')
            )
        
        self.current_routine.name = self.routine_name_var.get()
        self.current_routine.description = self.routine_desc_text.get('1.0', 'end-1c').strip()
        self.current_routine.modified_at = datetime.now().isoformat()
        
        filename = os.path.join(self.routines_dir, f"{self.current_routine.name.replace(' ', '_')}.json")
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.current_routine.to_dict(), f, indent=2)
            self.update_status(f"Saved routine: {filename}", "success")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save routine: {e}")
            
    def save_routine_as(self):
        """Save routine with a new name."""
        filename = filedialog.asksaveasfilename(
            initialdir=self.routines_dir,
            title="Save Routine As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            self.save_routine()
            
    def import_routine(self):
        """Import a routine from file."""
        self.open_routine()
        
    def export_routine(self):
        """Export routine to file."""
        self.save_routine_as()
        
    def add_action(self):
        """Add a new action to the routine."""
        editor = ActionEditor(self.root, marker_db=self.marker_db)
        self.root.wait_window(editor)
        
        if editor.result:
            if not self.current_routine:
                self.new_routine()
            
            self.current_routine.actions.append(editor.result)
            self.refresh_actions_list()
            self.update_status(f"Added action: {editor.result.name or editor.result.action_type.value}", "info")
            
    def edit_action(self):
        """Edit the selected action."""
        selection = self.actions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an action to edit")
            return
        
        index = selection[0]
        action = self.current_routine.actions[index]
        
        editor = ActionEditor(self.root, action=action, marker_db=self.marker_db)
        self.root.wait_window(editor)
        
        if editor.result:
            self.current_routine.actions[index] = editor.result
            self.refresh_actions_list()
            self.actions_listbox.selection_set(index)
            self.update_status(f"Updated action: {editor.result.name}", "info")
            
    def delete_action(self):
        """Delete the selected action."""
        selection = self.actions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an action to delete")
            return
        
        index = selection[0]
        action = self.current_routine.actions[index]
        
        if messagebox.askyesno("Confirm Delete", f"Delete action: {action.name or action.action_type.value}?"):
            del self.current_routine.actions[index]
            self.refresh_actions_list()
            self.update_status(f"Deleted action: {action.name}", "info")
            
    def duplicate_action(self):
        """Duplicate the selected action."""
        selection = self.actions_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an action to duplicate")
            return
        
        index = selection[0]
        action = self.current_routine.actions[index]
        
        # Create a copy of the action
        new_action = RobotAction(
            action_type=action.action_type,
            parameters=action.parameters.copy(),
            name=f"{action.name} (copy)" if action.name else "",
            description=action.description
        )
        
        self.current_routine.actions.insert(index + 1, new_action)
        self.refresh_actions_list()
        self.actions_listbox.selection_set(index + 1)
        self.update_status(f"Duplicated action: {action.name}", "info")
        
    def move_action_up(self):
        """Move selected action up in the list."""
        selection = self.actions_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        
        index = selection[0]
        self.current_routine.actions[index-1], self.current_routine.actions[index] = \
            self.current_routine.actions[index], self.current_routine.actions[index-1]
        
        self.refresh_actions_list()
        self.actions_listbox.selection_set(index-1)
        
    def move_action_down(self):
        """Move selected action down in the list."""
        selection = self.actions_listbox.curselection()
        if not selection or selection[0] >= len(self.current_routine.actions) - 1:
            return
        
        index = selection[0]
        self.current_routine.actions[index], self.current_routine.actions[index+1] = \
            self.current_routine.actions[index+1], self.current_routine.actions[index]
        
        self.refresh_actions_list()
        self.actions_listbox.selection_set(index+1)
        
    def refresh_actions_list(self):
        """Refresh the actions listbox."""
        self.actions_listbox.delete(0, tk.END)
        
        if self.current_routine:
            for i, action in enumerate(self.current_routine.actions):
                display_text = f"{i+1}. {action.name or action.action_type.value}"
                if action.action_type == ActionType.NAVIGATE_TO_MARKER:
                    marker_id = action.parameters.get('marker_id', '?')
                    display_text += f" (Marker {marker_id})"
                elif action.action_type == ActionType.WAIT:
                    duration = action.parameters.get('duration', '?')
                    display_text += f" ({duration}s)"
                    
                self.actions_listbox.insert(tk.END, display_text)
                
    def load_routine_to_ui(self):
        """Load routine data into UI."""
        if not self.current_routine:
            return
        
        self.routine_name_var.set(self.current_routine.name)
        self.routine_desc_text.delete('1.0', tk.END)
        self.routine_desc_text.insert('1.0', self.current_routine.description)
        self.refresh_actions_list()
        
    def load_recent_routine(self):
        """Load the most recent routine."""
        try:
            files = [f for f in os.listdir(self.routines_dir) if f.endswith('.json')]
            if files:
                files.sort(key=lambda x: os.path.getmtime(os.path.join(self.routines_dir, x)), reverse=True)
                most_recent = os.path.join(self.routines_dir, files[0])
                
                with open(most_recent, 'r') as f:
                    data = json.load(f)
                self.current_routine = RobotRoutine.from_dict(data)
                self.load_routine_to_ui()
                self.update_status(f"Loaded recent routine: {self.current_routine.name}", "info")
        except Exception as e:
            logger.debug(f"No recent routine to load: {e}")
            
    def run_routine(self):
        """Run the current routine on actual hardware."""
        if not self.current_routine or not self.current_routine.actions:
            messagebox.showwarning("No Routine", "Please create or load a routine first")
            return
        
        if self.execution_thread and self.execution_thread.is_alive():
            messagebox.showwarning("Already Running", "A routine is already running")
            return
        
        # Save routine before execution
        self.save_routine()
        
        # Start execution in thread
        self.execution_thread = threading.Thread(
            target=self.executor.execute_routine,
            args=(self.current_routine, False)
        )
        self.execution_thread.start()
        
        # Update progress
        self.update_progress()
        
    def run_simulation(self):
        """Run routine in simulation mode."""
        if not self.current_routine or not self.current_routine.actions:
            messagebox.showwarning("No Routine", "Please create or load a routine first")
            return
        
        if self.execution_thread and self.execution_thread.is_alive():
            messagebox.showwarning("Already Running", "A routine is already running")
            return
        
        # Start simulation in thread
        self.execution_thread = threading.Thread(
            target=self.executor.execute_routine,
            args=(self.current_routine, True)
        )
        self.execution_thread.start()
        
        # Update progress
        self.update_progress()
        
    def stop_routine(self):
        """Stop routine execution."""
        self.executor.stop()
        self.update_status("Stopping routine...", "warning")
        
    def update_progress(self):
        """Update progress bar during execution."""
        if self.execution_thread and self.execution_thread.is_alive():
            if self.current_routine:
                total = len(self.current_routine.actions)
                current = self.executor.current_action_index
                progress = int((current / total) * 100) if total > 0 else 0
                self.progress_var.set(progress)
            
            # Schedule next update
            self.root.after(100, self.update_progress)
        else:
            # Execution complete
            self.progress_var.set(100 if self.executor.is_running else 0)
            
    def update_status(self, message: str, level: str = "info"):
        """Update status display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color coding
        colors = {
            'info': 'black',
            'success': 'green',
            'warning': 'orange',
            'error': 'red'
        }
        
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # Add color tag
        line_start = self.status_text.index("end-2c linestart")
        line_end = self.status_text.index("end-1c")
        self.status_text.tag_add(level, line_start, line_end)
        self.status_text.tag_config(level, foreground=colors.get(level, 'black'))
        
        # Auto-scroll
        self.status_text.see(tk.END)
        
        # Update status bar
        self.status_bar.config(text=message)
        
    def create_fridge_couch_routine(self):
        """Create the fridge-to-couch beverage delivery routine."""
        routine = RobotRoutine(
            name="Beverage Delivery",
            description="Navigate to fridge, open door, get beverage, navigate to couch"
        )
        
        # Add actions for the routine
        routine.actions = [
            RobotAction(
                ActionType.NAVIGATE_TO_MARKER,
                {'marker_id': 1, 'timeout': 30},
                "Go to Fridge",
                "Navigate to the fridge marker"
            ),
            RobotAction(
                ActionType.ALIGN_WITH_MARKER,
                {'marker_id': 1, 'distance_cm': 30, 'tolerance_cm': 5},
                "Align with Fridge",
                "Precisely align with fridge door"
            ),
            RobotAction(
                ActionType.OPEN_DOOR,
                {'duration': 3.0},
                "Open Fridge Door",
                "Execute door opening routine"
            ),
            RobotAction(
                ActionType.WAIT,
                {'duration': 1.0},
                "Wait",
                "Wait for door to fully open"
            ),
            RobotAction(
                ActionType.NAVIGATE_TO_MARKER,
                {'marker_id': 2, 'timeout': 20},
                "Enter Fridge",
                "Navigate to inside fridge marker"
            ),
            RobotAction(
                ActionType.PICKUP_OBJECT,
                {},
                "Get Beverage",
                "Pick up the beverage"
            ),
            RobotAction(
                ActionType.MOVE_BACKWARD,
                {'distance': 50, 'speed': 20},
                "Exit Fridge",
                "Back out of the fridge"
            ),
            RobotAction(
                ActionType.CLOSE_DOOR,
                {'duration': 3.0},
                "Close Fridge",
                "Close the fridge door"
            ),
            RobotAction(
                ActionType.NAVIGATE_TO_MARKER,
                {'marker_id': 3, 'timeout': 45},
                "Go to Couch",
                "Navigate to the couch marker"
            ),
            RobotAction(
                ActionType.ALIGN_WITH_MARKER,
                {'marker_id': 3, 'distance_cm': 50, 'tolerance_cm': 10},
                "Position at Couch",
                "Align for beverage delivery"
            ),
            RobotAction(
                ActionType.RELEASE_OBJECT,
                {},
                "Deliver Beverage",
                "Place the beverage"
            )
        ]
        
        self.current_routine = routine
        self.load_routine_to_ui()
        self.update_status("Created fridge-to-couch delivery routine", "success")
        
    def test_navigation(self):
        """Test basic navigation."""
        messagebox.showinfo("Test Navigation", "Navigation test will scan for markers and perform basic movements")
        # Implement navigation test
        
    def calibrate_position(self):
        """Open calibration mode."""
        messagebox.showinfo("Calibration", "Position calibration mode - position robot at desired location relative to marker")
        # Implement calibration
        
    def manage_markers(self):
        """Open marker management dialog."""
        dialog = MarkerManagerDialog(self.root, self.marker_db)
        self.root.wait_window(dialog)
        
    def scan_markers(self):
        """Scan for visible ArUco markers."""
        messagebox.showinfo("Scan", "Scanning for ArUco markers...")
        # Implement marker scanning
        
    def show_documentation(self):
        """Show documentation."""
        messagebox.showinfo("Documentation", 
            "BevBot Routine Creator\n\n"
            "1. Create routines by adding actions\n"
            "2. Configure ArUco markers for navigation\n"
            "3. Test in simulation mode\n"
            "4. Execute on actual robot\n\n"
            "For detailed documentation, see README.md")
        
    def show_about(self):
        """Show about dialog."""
        messagebox.showinfo("About", 
            "BevBot Routine Creator v1.0\n\n"
            "A comprehensive GUI for creating and executing\n"
            "robot routines with ArUco marker navigation.\n\n"
            "© 2024 BevBot Project")

class MarkerManagerDialog(tk.Toplevel):
    """Dialog for managing ArUco markers."""
    
    def __init__(self, parent, marker_db: MarkerDatabase):
        super().__init__(parent)
        self.marker_db = marker_db
        
        self.title("Marker Manager")
        self.geometry("600x400")
        
        self.create_widgets()
        self.refresh_list()
        
        self.transient(parent)
        self.grab_set()
        
    def create_widgets(self):
        """Create dialog widgets."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Marker", command=self.add_marker).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Marker", command=self.edit_marker).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Marker", command=self.delete_marker).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Generate PDF", command=self.generate_pdf).pack(side=tk.LEFT, padx=10)
        
        # Marker list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for markers
        columns = ('ID', 'Name', 'Location', 'Distance')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scrollbar.set)
        
        # Close button
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=10)
        
    def refresh_list(self):
        """Refresh the marker list."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add markers
        for marker_id, info in self.marker_db.get_all_markers().items():
            self.tree.insert('', 'end', values=(
                info['id'],
                info['name'],
                info['location'],
                f"{info['default_distance_cm']} cm"
            ))
            
    def add_marker(self):
        """Add a new marker."""
        dialog = MarkerEditDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            self.marker_db.add_marker(**dialog.result)
            self.refresh_list()
            
    def edit_marker(self):
        """Edit selected marker."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a marker to edit")
            return
        
        item = self.tree.item(selection[0])
        marker_id = item['values'][0]
        marker = self.marker_db.get_marker(marker_id)
        
        dialog = MarkerEditDialog(self, marker)
        self.wait_window(dialog)
        
        if dialog.result:
            self.marker_db.add_marker(**dialog.result)
            self.refresh_list()
            
    def delete_marker(self):
        """Delete selected marker."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a marker to delete")
            return
        
        item = self.tree.item(selection[0])
        marker_id = str(item['values'][0])
        
        if messagebox.askyesno("Confirm Delete", f"Delete marker {marker_id}?"):
            if marker_id in self.marker_db.markers:
                del self.marker_db.markers[marker_id]
                self.marker_db.save()
                self.refresh_list()
                
    def generate_pdf(self):
        """Generate PDF with ArUco markers."""
        messagebox.showinfo("Generate PDF", "This will generate a PDF with all configured ArUco markers")
        # Implement PDF generation

class MarkerEditDialog(tk.Toplevel):
    """Dialog for editing a single marker."""
    
    def __init__(self, parent, marker=None):
        super().__init__(parent)
        self.marker = marker
        self.result = None
        
        self.title("Edit Marker" if marker else "Add Marker")
        self.geometry("400x250")
        
        self.create_widgets()
        
        if marker:
            self.load_marker(marker)
        
        self.transient(parent)
        self.grab_set()
        
    def create_widgets(self):
        """Create dialog widgets."""
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Marker ID
        ttk.Label(frame, text="Marker ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.id_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.id_var, width=20).grid(row=0, column=1, pady=5)
        
        # Name
        ttk.Label(frame, text="Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=1, column=1, pady=5)
        
        # Location
        ttk.Label(frame, text="Location:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.location_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.location_var, width=30).grid(row=2, column=1, pady=5)
        
        # Default Distance
        ttk.Label(frame, text="Default Distance (cm):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.distance_var = tk.StringVar(value="30")
        ttk.Entry(frame, textvariable=self.distance_var, width=20).grid(row=3, column=1, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
    def load_marker(self, marker):
        """Load marker data."""
        self.id_var.set(str(marker['id']))
        self.name_var.set(marker['name'])
        self.location_var.set(marker['location'])
        self.distance_var.set(str(marker['default_distance_cm']))
        
    def ok_clicked(self):
        """Handle OK button."""
        try:
            self.result = {
                'marker_id': int(self.id_var.get()),
                'name': self.name_var.get(),
                'location': self.location_var.get(),
                'distance_cm': float(self.distance_var.get())
            }
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e))
            
    def cancel_clicked(self):
        """Handle Cancel button."""
        self.result = None
        self.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = BevBotRoutineGUI(root)
    
    # Configure some initial markers for demo
    app.marker_db.add_marker(1, "Fridge Door", "Kitchen - Front", 30)
    app.marker_db.add_marker(2, "Inside Fridge", "Kitchen - Inside", 20)
    app.marker_db.add_marker(3, "Couch", "Living Room", 50)
    
    root.mainloop()

if __name__ == "__main__":
    main()