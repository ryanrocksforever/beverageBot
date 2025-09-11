#!/usr/bin/env python3
"""Advanced routine system for BevBot with static actions and dynamic goals.

This system supports:
- Static actions: Fixed movements, actuator control, waiting
- Dynamic goals: ArUco marker navigation with various positioning options
- Conditional logic: If/else based on sensor states
- Error handling and recovery
"""

import time
import logging
import json
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from abc import ABC, abstractmethod
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ActionType(Enum):
    """Types of actions in routines."""
    # Static actions
    MOVE = "move"  # Fixed motor speeds for duration
    TURN = "turn"  # Turn in place
    ACTUATOR = "actuator"  # Actuator control
    WAIT = "wait"  # Wait for duration
    
    # Dynamic goals
    NAVIGATE_TO_MARKER = "navigate_to_marker"  # Navigate to ArUco marker
    ALIGN_WITH_MARKER = "align_with_marker"  # Precise alignment with marker
    SEARCH_FOR_MARKER = "search_for_marker"  # Search for specific marker
    
    # Control flow
    IF_MARKER_VISIBLE = "if_marker_visible"  # Conditional based on marker visibility
    LOOP = "loop"  # Repeat actions
    PARALLEL = "parallel"  # Run actions in parallel
    
    # Utility
    LOG = "log"  # Log message
    SET_VARIABLE = "set_variable"  # Set routine variable
    CALL_SUBROUTINE = "call_subroutine"  # Call another routine

class MarkerApproach(Enum):
    """How to approach an ArUco marker."""
    FRONT = "front"  # Approach from front (default)
    LEFT = "left"  # Approach from left side
    RIGHT = "right"  # Approach from right side
    BACK = "back"  # Approach from behind
    CUSTOM = "custom"  # Custom angle

@dataclass
class MarkerGoal:
    """Goal configuration for ArUco marker navigation."""
    marker_id: int
    approach: MarkerApproach = MarkerApproach.FRONT
    distance_cm: float = 30.0  # Target distance from marker
    angle_degrees: float = 0.0  # Target angle (0 = straight ahead)
    tolerance_cm: float = 5.0  # Distance tolerance
    tolerance_degrees: float = 5.0  # Angle tolerance
    timeout: float = 30.0  # Maximum time to achieve goal
    
    # Advanced positioning
    offset_x_cm: float = 0.0  # Lateral offset from marker center
    offset_y_cm: float = 0.0  # Vertical offset from marker center
    maintain_orientation: bool = True  # Keep facing marker after positioning
    
    def to_dict(self):
        data = asdict(self)
        data['approach'] = self.approach.value
        return data
    
    @classmethod
    def from_dict(cls, data):
        data = data.copy()
        data['approach'] = MarkerApproach(data['approach'])
        return cls(**data)

@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0

class Action(ABC):
    """Base class for all routine actions."""
    
    def __init__(self, name: str = "", **params):
        self.name = name
        self.params = params
        self.start_time = 0
        self.interrupted = False
    
    @abstractmethod
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute the action.
        
        Args:
            context: Routine execution context
            
        Returns:
            ActionResult with success status and any data
        """
        pass
    
    def interrupt(self):
        """Interrupt the action."""
        self.interrupted = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert action to dictionary for serialization."""
        return {
            'type': self.__class__.__name__,
            'name': self.name,
            'params': self.params
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Action':
        """Create action from dictionary."""
        # This would be overridden by factory method
        return cls(name=data.get('name', ''), **data.get('params', {}))

class MoveAction(Action):
    """Fixed movement for specified duration."""
    
    def __init__(self, left_speed: float, right_speed: float, 
                 duration: float, name: str = ""):
        super().__init__(name)
        self.left_speed = left_speed
        self.right_speed = right_speed
        self.duration = duration
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute movement."""
        logger.info(f"Move: L={self.left_speed}%, R={self.right_speed}% for {self.duration}s")
        
        # Set motor speeds
        context.robot.set_motor_speeds(self.left_speed, self.right_speed)
        
        # Wait for duration
        start = time.time()
        while time.time() - start < self.duration:
            if self.interrupted:
                context.robot.stop_motors()
                return ActionResult(False, "Movement interrupted")
            time.sleep(0.05)
        
        # Stop motors
        context.robot.stop_motors()
        
        return ActionResult(True, f"Moved for {self.duration}s")

class TurnAction(Action):
    """Turn in place by specified angle."""
    
    def __init__(self, angle_degrees: float, speed: float = 30, name: str = ""):
        super().__init__(name)
        self.angle_degrees = angle_degrees
        self.speed = speed
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute turn."""
        logger.info(f"Turn: {self.angle_degrees}° at {self.speed}%")
        
        # Calculate turn duration (approximate)
        # This would need calibration for specific robot
        duration = abs(self.angle_degrees) / 90.0 * 2.0  # 2 seconds for 90°
        
        # Set motor speeds for turning
        if self.angle_degrees > 0:  # Turn right
            context.robot.set_motor_speeds(self.speed, -self.speed)
        else:  # Turn left
            context.robot.set_motor_speeds(-self.speed, self.speed)
        
        # Wait for duration
        start = time.time()
        while time.time() - start < duration:
            if self.interrupted:
                context.robot.stop_motors()
                return ActionResult(False, "Turn interrupted")
            time.sleep(0.05)
        
        # Stop motors
        context.robot.stop_motors()
        
        return ActionResult(True, f"Turned {self.angle_degrees}°")

class ActuatorAction(Action):
    """Control linear actuator."""
    
    def __init__(self, action: str, duration: float = 0, 
                 speed: float = 50, name: str = ""):
        super().__init__(name)
        self.action = action  # "extend", "retract", "stop"
        self.duration = duration
        self.speed = speed
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute actuator action."""
        logger.info(f"Actuator: {self.action} at {self.speed}% for {self.duration}s")
        
        # Control actuator
        if self.action == "extend":
            context.robot.extend_actuator(self.speed)
        elif self.action == "retract":
            context.robot.retract_actuator(self.speed)
        else:
            context.robot.stop_actuator()
            return ActionResult(True, "Actuator stopped")
        
        # Wait if duration specified
        if self.duration > 0:
            start = time.time()
            while time.time() - start < self.duration:
                if self.interrupted:
                    context.robot.stop_actuator()
                    return ActionResult(False, "Actuator action interrupted")
                time.sleep(0.05)
            
            context.robot.stop_actuator()
        
        return ActionResult(True, f"Actuator {self.action} complete")

class WaitAction(Action):
    """Wait for specified duration."""
    
    def __init__(self, duration: float, name: str = ""):
        super().__init__(name)
        self.duration = duration
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute wait."""
        logger.info(f"Wait: {self.duration}s")
        
        start = time.time()
        while time.time() - start < self.duration:
            if self.interrupted:
                return ActionResult(False, "Wait interrupted")
            time.sleep(0.05)
        
        return ActionResult(True, f"Waited {self.duration}s")

class NavigateToMarkerAction(Action):
    """Navigate to ArUco marker with specified positioning."""
    
    def __init__(self, goal: MarkerGoal, name: str = ""):
        super().__init__(name)
        self.goal = goal
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute navigation to marker."""
        logger.info(f"Navigate to marker {self.goal.marker_id}")
        
        # Calculate target position based on approach type
        target_position = self._calculate_target_position()
        
        # Use navigation system to reach marker
        success = context.navigator.navigate_to_marker_goal(
            self.goal, timeout=self.goal.timeout
        )
        
        if success:
            return ActionResult(True, f"Reached marker {self.goal.marker_id}")
        else:
            return ActionResult(False, f"Failed to reach marker {self.goal.marker_id}")
    
    def _calculate_target_position(self) -> Tuple[float, float, float]:
        """Calculate target position relative to marker.
        
        Returns:
            Tuple of (x, y, angle) relative to marker
        """
        x, y, angle = 0, 0, 0
        
        if self.goal.approach == MarkerApproach.FRONT:
            y = -self.goal.distance_cm
        elif self.goal.approach == MarkerApproach.BACK:
            y = self.goal.distance_cm
            angle = 180
        elif self.goal.approach == MarkerApproach.LEFT:
            x = -self.goal.distance_cm
            angle = 90
        elif self.goal.approach == MarkerApproach.RIGHT:
            x = self.goal.distance_cm
            angle = -90
        elif self.goal.approach == MarkerApproach.CUSTOM:
            # Use specified angle and distance
            angle = self.goal.angle_degrees
            rad = np.radians(angle)
            x = self.goal.distance_cm * np.sin(rad)
            y = -self.goal.distance_cm * np.cos(rad)
        
        # Apply offsets
        x += self.goal.offset_x_cm
        y += self.goal.offset_y_cm
        
        return x, y, angle

class SearchForMarkerAction(Action):
    """Search for a specific ArUco marker."""
    
    def __init__(self, marker_id: int, timeout: float = 10, 
                 turn_speed: float = 20, name: str = ""):
        super().__init__(name)
        self.marker_id = marker_id
        self.timeout = timeout
        self.turn_speed = turn_speed
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute marker search."""
        logger.info(f"Searching for marker {self.marker_id}")
        
        start = time.time()
        
        # Rotate slowly while searching
        context.robot.set_motor_speeds(-self.turn_speed, self.turn_speed)
        
        while time.time() - start < self.timeout:
            if self.interrupted:
                context.robot.stop_motors()
                return ActionResult(False, "Search interrupted")
            
            # Check for marker
            markers = context.get_visible_markers()
            if self.marker_id in markers:
                context.robot.stop_motors()
                return ActionResult(
                    True, 
                    f"Found marker {self.marker_id}",
                    {'marker_info': markers[self.marker_id]}
                )
            
            time.sleep(0.1)
        
        context.robot.stop_motors()
        return ActionResult(False, f"Marker {self.marker_id} not found")

class ConditionalAction(Action):
    """Conditional execution based on marker visibility."""
    
    def __init__(self, marker_id: int, if_visible: List[Action], 
                 if_not_visible: List[Action] = None, name: str = ""):
        super().__init__(name)
        self.marker_id = marker_id
        self.if_visible = if_visible
        self.if_not_visible = if_not_visible or []
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute conditional logic."""
        markers = context.get_visible_markers()
        
        if self.marker_id in markers:
            logger.info(f"Marker {self.marker_id} visible, executing if_visible actions")
            for action in self.if_visible:
                if self.interrupted:
                    return ActionResult(False, "Conditional interrupted")
                result = action.execute(context)
                if not result.success:
                    return result
        else:
            logger.info(f"Marker {self.marker_id} not visible, executing if_not_visible actions")
            for action in self.if_not_visible:
                if self.interrupted:
                    return ActionResult(False, "Conditional interrupted")
                result = action.execute(context)
                if not result.success:
                    return result
        
        return ActionResult(True, "Conditional complete")

class LoopAction(Action):
    """Loop a set of actions."""
    
    def __init__(self, actions: List[Action], count: int = 1, name: str = ""):
        super().__init__(name)
        self.actions = actions
        self.count = count  # -1 for infinite
    
    def execute(self, context: 'RoutineContext') -> ActionResult:
        """Execute loop."""
        iteration = 0
        
        while self.count == -1 or iteration < self.count:
            if self.interrupted:
                return ActionResult(False, "Loop interrupted")
            
            logger.info(f"Loop iteration {iteration + 1}")
            
            for action in self.actions:
                if self.interrupted:
                    return ActionResult(False, "Loop interrupted")
                result = action.execute(context)
                if not result.success:
                    return result
            
            iteration += 1
        
        return ActionResult(True, f"Loop completed {iteration} iterations")

class RoutineContext:
    """Execution context for routines."""
    
    def __init__(self, robot, navigator=None, camera=None):
        """Initialize routine context.
        
        Args:
            robot: Robot controller instance
            navigator: ArUco navigator instance (optional)
            camera: Camera interface (optional)
        """
        self.robot = robot
        self.navigator = navigator
        self.camera = camera
        self.variables = {}  # Runtime variables
        self.detector = None
        
        if camera:
            from .aruco_center_demo import ArUcoDetector
            from .camera_config import MARKER_SIZE_CM
            self.detector = ArUcoDetector(marker_size_cm=MARKER_SIZE_CM)
    
    def get_visible_markers(self) -> Dict:
        """Get currently visible ArUco markers."""
        if not self.camera or not self.detector:
            return {}
        
        frame, _ = self.camera.capture_frame()
        return self.detector.detect_markers(frame)
    
    def set_variable(self, name: str, value: Any):
        """Set a routine variable."""
        self.variables[name] = value
    
    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a routine variable."""
        return self.variables.get(name, default)

class Routine:
    """A complete routine consisting of multiple actions."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.actions: List[Action] = []
        self.subroutines: Dict[str, 'Routine'] = {}
        self.interrupted = False
        self.current_action_index = 0
    
    def add_action(self, action: Action):
        """Add an action to the routine."""
        self.actions.append(action)
    
    def add_subroutine(self, routine: 'Routine'):
        """Add a subroutine that can be called."""
        self.subroutines[routine.name] = routine
    
    def execute(self, context: RoutineContext) -> ActionResult:
        """Execute the routine."""
        logger.info(f"Starting routine: {self.name}")
        
        for i, action in enumerate(self.actions):
            if self.interrupted:
                return ActionResult(False, "Routine interrupted")
            
            self.current_action_index = i
            logger.info(f"Executing action {i+1}/{len(self.actions)}: {action.name or action.__class__.__name__}")
            
            result = action.execute(context)
            
            if not result.success:
                logger.error(f"Action failed: {result.message}")
                return result
        
        logger.info(f"Routine {self.name} completed successfully")
        return ActionResult(True, "Routine completed")
    
    def interrupt(self):
        """Interrupt the routine."""
        self.interrupted = True
        if 0 <= self.current_action_index < len(self.actions):
            self.actions[self.current_action_index].interrupt()
    
    def reset(self):
        """Reset routine state."""
        self.interrupted = False
        self.current_action_index = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert routine to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'actions': [action.to_dict() for action in self.actions],
            'subroutines': {name: sub.to_dict() 
                          for name, sub in self.subroutines.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Routine':
        """Create routine from dictionary."""
        routine = cls(data['name'], data.get('description', ''))
        
        # Load actions (would need action factory)
        # routine.actions = [Action.from_dict(a) for a in data['actions']]
        
        # Load subroutines
        for name, sub_data in data.get('subroutines', {}).items():
            routine.subroutines[name] = cls.from_dict(sub_data)
        
        return routine

class RoutineBuilder:
    """Builder for creating routines programmatically."""
    
    def __init__(self, name: str, description: str = ""):
        self.routine = Routine(name, description)
    
    def move(self, left_speed: float, right_speed: float, 
             duration: float, name: str = "") -> 'RoutineBuilder':
        """Add move action."""
        self.routine.add_action(MoveAction(left_speed, right_speed, duration, name))
        return self
    
    def turn(self, angle_degrees: float, speed: float = 30, 
             name: str = "") -> 'RoutineBuilder':
        """Add turn action."""
        self.routine.add_action(TurnAction(angle_degrees, speed, name))
        return self
    
    def actuator(self, action: str, duration: float = 0, 
                 speed: float = 50, name: str = "") -> 'RoutineBuilder':
        """Add actuator action."""
        self.routine.add_action(ActuatorAction(action, duration, speed, name))
        return self
    
    def wait(self, duration: float, name: str = "") -> 'RoutineBuilder':
        """Add wait action."""
        self.routine.add_action(WaitAction(duration, name))
        return self
    
    def navigate_to_marker(self, marker_id: int, 
                          distance_cm: float = 30,
                          approach: MarkerApproach = MarkerApproach.FRONT,
                          name: str = "",
                          **kwargs) -> 'RoutineBuilder':
        """Add marker navigation action."""
        goal = MarkerGoal(
            marker_id=marker_id,
            distance_cm=distance_cm,
            approach=approach,
            **kwargs
        )
        self.routine.add_action(NavigateToMarkerAction(goal, name=name))
        return self
    
    def search_for_marker(self, marker_id: int, timeout: float = 10,
                         turn_speed: float = 20, name: str = "") -> 'RoutineBuilder':
        """Add marker search action."""
        self.routine.add_action(SearchForMarkerAction(marker_id, timeout, turn_speed, name))
        return self
    
    def if_marker_visible(self, marker_id: int, 
                         if_visible: Callable[['RoutineBuilder'], None],
                         if_not_visible: Callable[['RoutineBuilder'], None] = None) -> 'RoutineBuilder':
        """Add conditional based on marker visibility."""
        # Build if_visible actions
        if_builder = RoutineBuilder("if_visible")
        if_visible(if_builder)
        
        # Build if_not_visible actions
        else_actions = []
        if if_not_visible:
            else_builder = RoutineBuilder("if_not_visible")
            if_not_visible(else_builder)
            else_actions = else_builder.routine.actions
        
        self.routine.add_action(
            ConditionalAction(marker_id, if_builder.routine.actions, else_actions)
        )
        return self
    
    def loop(self, count: int, 
             actions: Callable[['RoutineBuilder'], None]) -> 'RoutineBuilder':
        """Add loop."""
        loop_builder = RoutineBuilder("loop")
        actions(loop_builder)
        self.routine.add_action(LoopAction(loop_builder.routine.actions, count))
        return self
    
    def build(self) -> Routine:
        """Build and return the routine."""
        return self.routine

class RoutineExecutor:
    """Executes routines with monitoring and control."""
    
    def __init__(self, context: RoutineContext):
        self.context = context
        self.current_routine: Optional[Routine] = None
        self.execution_thread: Optional[threading.Thread] = None
        self.is_running = False
    
    def execute(self, routine: Routine, async_exec: bool = True) -> Optional[ActionResult]:
        """Execute a routine.
        
        Args:
            routine: Routine to execute
            async_exec: If True, execute in background thread
            
        Returns:
            ActionResult if sync execution, None if async
        """
        if self.is_running:
            logger.warning("Another routine is already running")
            return ActionResult(False, "Another routine is running")
        
        self.current_routine = routine
        routine.reset()
        
        if async_exec:
            self.execution_thread = threading.Thread(target=self._execute_routine)
            self.execution_thread.start()
            return None
        else:
            return self._execute_routine()
    
    def _execute_routine(self) -> ActionResult:
        """Internal routine execution."""
        self.is_running = True
        
        try:
            result = self.current_routine.execute(self.context)
        except Exception as e:
            logger.error(f"Routine execution error: {e}")
            result = ActionResult(False, f"Error: {e}")
        finally:
            self.is_running = False
            self.current_routine = None
        
        return result
    
    def stop(self):
        """Stop current routine execution."""
        if self.current_routine:
            self.current_routine.interrupt()
            
        if self.execution_thread:
            self.execution_thread.join(timeout=2)
            self.execution_thread = None
        
        self.is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get execution status."""
        return {
            'running': self.is_running,
            'routine': self.current_routine.name if self.current_routine else None,
            'action_index': self.current_routine.current_action_index if self.current_routine else 0,
            'total_actions': len(self.current_routine.actions) if self.current_routine else 0
        }