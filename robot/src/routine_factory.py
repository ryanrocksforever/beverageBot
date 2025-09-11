#!/usr/bin/env python3
"""Factory for creating actions from serialized data."""

import json
import logging
from typing import Dict, Any, List, Type
from pathlib import Path

from .routine_system import (
    Action, MoveAction, TurnAction, ActuatorAction, WaitAction,
    NavigateToMarkerAction, SearchForMarkerAction, ConditionalAction,
    LoopAction, MarkerGoal, MarkerApproach, Routine
)

logger = logging.getLogger(__name__)

class ActionFactory:
    """Factory for creating actions from dictionaries."""
    
    # Registry of action types
    ACTION_TYPES: Dict[str, Type[Action]] = {
        'MoveAction': MoveAction,
        'TurnAction': TurnAction,
        'ActuatorAction': ActuatorAction,
        'WaitAction': WaitAction,
        'NavigateToMarkerAction': NavigateToMarkerAction,
        'SearchForMarkerAction': SearchForMarkerAction,
        'ConditionalAction': ConditionalAction,
        'LoopAction': LoopAction,
    }
    
    @classmethod
    def create_action(cls, data: Dict[str, Any]) -> Action:
        """Create an action from a dictionary.
        
        Args:
            data: Dictionary with action type and parameters
            
        Returns:
            Action instance
            
        Raises:
            ValueError: If action type is unknown
        """
        action_type = data.get('type')
        if not action_type:
            raise ValueError("Action data missing 'type' field")
        
        if action_type not in cls.ACTION_TYPES:
            raise ValueError(f"Unknown action type: {action_type}")
        
        action_class = cls.ACTION_TYPES[action_type]
        name = data.get('name', '')
        params = data.get('params', {})
        
        # Special handling for different action types
        if action_type == 'MoveAction':
            return MoveAction(
                left_speed=params['left_speed'],
                right_speed=params['right_speed'],
                duration=params['duration'],
                name=name
            )
        
        elif action_type == 'TurnAction':
            return TurnAction(
                angle_degrees=params['angle_degrees'],
                speed=params.get('speed', 30),
                name=name
            )
        
        elif action_type == 'ActuatorAction':
            return ActuatorAction(
                action=params['action'],
                duration=params.get('duration', 0),
                speed=params.get('speed', 50),
                name=name
            )
        
        elif action_type == 'WaitAction':
            return WaitAction(
                duration=params['duration'],
                name=name
            )
        
        elif action_type == 'NavigateToMarkerAction':
            # Reconstruct MarkerGoal
            goal_data = params['goal']
            goal = MarkerGoal.from_dict(goal_data)
            return NavigateToMarkerAction(goal=goal, name=name)
        
        elif action_type == 'SearchForMarkerAction':
            return SearchForMarkerAction(
                marker_id=params['marker_id'],
                timeout=params.get('timeout', 10),
                turn_speed=params.get('turn_speed', 20),
                name=name
            )
        
        elif action_type == 'ConditionalAction':
            # Recursively create nested actions
            if_visible = [cls.create_action(a) for a in params.get('if_visible', [])]
            if_not_visible = [cls.create_action(a) for a in params.get('if_not_visible', [])]
            return ConditionalAction(
                marker_id=params['marker_id'],
                if_visible=if_visible,
                if_not_visible=if_not_visible,
                name=name
            )
        
        elif action_type == 'LoopAction':
            # Recursively create nested actions
            actions = [cls.create_action(a) for a in params.get('actions', [])]
            return LoopAction(
                actions=actions,
                count=params.get('count', 1),
                name=name
            )
        
        else:
            # Generic fallback
            return action_class(name=name, **params)
    
    @classmethod
    def action_to_dict(cls, action: Action) -> Dict[str, Any]:
        """Convert an action to a dictionary.
        
        Args:
            action: Action to convert
            
        Returns:
            Dictionary representation
        """
        base_dict = {
            'type': action.__class__.__name__,
            'name': action.name,
            'params': {}
        }
        
        # Add parameters based on action type
        if isinstance(action, MoveAction):
            base_dict['params'] = {
                'left_speed': action.left_speed,
                'right_speed': action.right_speed,
                'duration': action.duration
            }
        
        elif isinstance(action, TurnAction):
            base_dict['params'] = {
                'angle_degrees': action.angle_degrees,
                'speed': action.speed
            }
        
        elif isinstance(action, ActuatorAction):
            base_dict['params'] = {
                'action': action.action,
                'duration': action.duration,
                'speed': action.speed
            }
        
        elif isinstance(action, WaitAction):
            base_dict['params'] = {
                'duration': action.duration
            }
        
        elif isinstance(action, NavigateToMarkerAction):
            base_dict['params'] = {
                'goal': action.goal.to_dict()
            }
        
        elif isinstance(action, SearchForMarkerAction):
            base_dict['params'] = {
                'marker_id': action.marker_id,
                'timeout': action.timeout,
                'turn_speed': action.turn_speed
            }
        
        elif isinstance(action, ConditionalAction):
            base_dict['params'] = {
                'marker_id': action.marker_id,
                'if_visible': [cls.action_to_dict(a) for a in action.if_visible],
                'if_not_visible': [cls.action_to_dict(a) for a in action.if_not_visible]
            }
        
        elif isinstance(action, LoopAction):
            base_dict['params'] = {
                'actions': [cls.action_to_dict(a) for a in action.actions],
                'count': action.count
            }
        
        return base_dict

class RoutineManager:
    """Manages saving and loading routines."""
    
    def __init__(self, routines_dir: str = "routines"):
        """Initialize routine manager.
        
        Args:
            routines_dir: Directory to store routine files
        """
        self.routines_dir = Path(routines_dir)
        self.routines_dir.mkdir(exist_ok=True)
    
    def save_routine(self, routine: Routine, filename: str = None) -> str:
        """Save a routine to file.
        
        Args:
            routine: Routine to save
            filename: Optional filename (defaults to routine name)
            
        Returns:
            Path to saved file
        """
        if not filename:
            filename = f"{routine.name.lower().replace(' ', '_')}.json"
        
        filepath = self.routines_dir / filename
        
        # Convert routine to dictionary
        routine_dict = {
            'name': routine.name,
            'description': routine.description,
            'actions': [ActionFactory.action_to_dict(a) for a in routine.actions],
            'subroutines': {}
        }
        
        # Add subroutines
        for name, sub in routine.subroutines.items():
            routine_dict['subroutines'][name] = {
                'name': sub.name,
                'description': sub.description,
                'actions': [ActionFactory.action_to_dict(a) for a in sub.actions]
            }
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(routine_dict, f, indent=2)
        
        logger.info(f"Saved routine '{routine.name}' to {filepath}")
        return str(filepath)
    
    def load_routine(self, filename: str) -> Routine:
        """Load a routine from file.
        
        Args:
            filename: Name of routine file (with or without .json)
            
        Returns:
            Loaded routine
            
        Raises:
            FileNotFoundError: If routine file doesn't exist
            ValueError: If file format is invalid
        """
        if not filename.endswith('.json'):
            filename += '.json'
        
        filepath = self.routines_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Routine file not found: {filepath}")
        
        # Load from file
        with open(filepath, 'r') as f:
            routine_dict = json.load(f)
        
        # Create routine
        routine = Routine(
            name=routine_dict['name'],
            description=routine_dict.get('description', '')
        )
        
        # Load actions
        for action_data in routine_dict.get('actions', []):
            action = ActionFactory.create_action(action_data)
            routine.add_action(action)
        
        # Load subroutines
        for sub_name, sub_data in routine_dict.get('subroutines', {}).items():
            subroutine = Routine(
                name=sub_data['name'],
                description=sub_data.get('description', '')
            )
            for action_data in sub_data.get('actions', []):
                action = ActionFactory.create_action(action_data)
                subroutine.add_action(action)
            routine.add_subroutine(subroutine)
        
        logger.info(f"Loaded routine '{routine.name}' from {filepath}")
        return routine
    
    def list_routines(self) -> List[str]:
        """List available routine files.
        
        Returns:
            List of routine filenames
        """
        return [f.stem for f in self.routines_dir.glob("*.json")]
    
    def delete_routine(self, filename: str) -> bool:
        """Delete a routine file.
        
        Args:
            filename: Name of routine file
            
        Returns:
            True if deleted, False if not found
        """
        if not filename.endswith('.json'):
            filename += '.json'
        
        filepath = self.routines_dir / filename
        
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted routine file: {filepath}")
            return True
        
        return False