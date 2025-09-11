#!/usr/bin/env python3
"""Example routines for BevBot beverage delivery system."""

from .routine_system import (
    RoutineBuilder, MarkerApproach, MarkerGoal,
    Routine, MoveAction, TurnAction, ActuatorAction, 
    WaitAction, NavigateToMarkerAction, SearchForMarkerAction,
    LoopAction, ConditionalAction
)
from .routine_factory import RoutineManager

def create_fridge_open_routine() -> Routine:
    """Create routine to open fridge door.
    
    This routine:
    1. Navigates to fridge marker (ID 1)
    2. Positions at left side of fridge
    3. Extends actuator to hook door handle
    4. Pulls door open by backing up
    5. Releases door
    """
    builder = RoutineBuilder("Open Fridge", "Opens refrigerator door using actuator")
    
    routine = (builder
        # Find and approach fridge marker from left side
        .search_for_marker(1, timeout=15, name="Find fridge")
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.LEFT,
            distance_cm=25,  # Close enough to reach handle
            name="Position at fridge side"
        )
        
        # Hook door handle
        .actuator("extend", duration=3, speed=40, name="Extend to door handle")
        .wait(0.5, "Stabilize")
        
        # Pull door open by backing up with turn
        .move(-30, -25, duration=2, name="Pull door open")  # Slight turn while backing
        
        # Release handle
        .actuator("retract", duration=2, speed=50, name="Release handle")
        .wait(0.5, "Stabilize")
        
        # Back away from fridge
        .move(-30, -30, duration=1, name="Clear doorway")
        .build()
    )
    
    return routine

def create_beverage_pickup_routine() -> Routine:
    """Create routine to pick up beverage from shelf.
    
    This routine:
    1. Navigates to shelf marker (ID 2)
    2. Approaches from front
    3. Uses actuator to secure beverage
    4. Backs away with beverage
    """
    builder = RoutineBuilder("Pickup Beverage", "Picks up beverage from shelf")
    
    routine = (builder
        # Find and approach shelf
        .search_for_marker(2, timeout=15, name="Find shelf")
        .navigate_to_marker(
            marker_id=2,
            approach=MarkerApproach.FRONT,
            distance_cm=20,  # Very close for pickup
            name="Approach shelf"
        )
        
        # Secure beverage
        .actuator("extend", duration=2, speed=30, name="Secure beverage")
        .wait(1, "Grip stabilize")
        
        # Back away with beverage
        .move(-25, -25, duration=2, name="Back away from shelf")
        .build()
    )
    
    return routine

def create_delivery_routine() -> Routine:
    """Create complete beverage delivery routine.
    
    This routine:
    1. Starts at station (marker 0)
    2. Opens fridge
    3. Gets beverage
    4. Delivers to destination (marker 3)
    5. Returns to station
    """
    builder = RoutineBuilder("Beverage Delivery", "Complete delivery sequence")
    
    # Build main delivery sequence
    routine = (builder
        # Start sequence
        .search_for_marker(0, timeout=10, name="Find home station")
        .navigate_to_marker(0, distance_cm=30, name="Position at station")
        
        # Go to fridge and open it
        .search_for_marker(1, timeout=20, name="Find fridge")
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.LEFT,
            distance_cm=25,
            name="Position at fridge"
        )
        .actuator("extend", duration=3, speed=40, name="Hook door")
        .move(-30, -25, duration=2, name="Pull door open")
        .actuator("retract", duration=2, speed=50, name="Release door")
        
        # Get beverage from inside fridge
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.FRONT,
            distance_cm=40,
            name="Enter fridge area"
        )
        .search_for_marker(2, timeout=10, name="Find beverage shelf")
        .navigate_to_marker(
            marker_id=2,
            approach=MarkerApproach.FRONT,
            distance_cm=15,
            name="Approach beverage"
        )
        .actuator("extend", duration=2, speed=30, name="Secure beverage")
        .wait(1, "Stabilize grip")
        .move(-30, -30, duration=2, name="Back out with beverage")
        
        # Navigate to delivery location
        .search_for_marker(3, timeout=20, name="Find delivery location")
        .navigate_to_marker(
            marker_id=3,
            approach=MarkerApproach.FRONT,
            distance_cm=25,
            name="Approach delivery point"
        )
        
        # Release beverage
        .actuator("retract", duration=2, speed=50, name="Release beverage")
        .wait(1, "Ensure placement")
        .move(-25, -25, duration=1, name="Back away")
        
        # Return to station
        .search_for_marker(0, timeout=20, name="Find home station")
        .navigate_to_marker(
            marker_id=0,
            approach=MarkerApproach.FRONT,
            distance_cm=30,
            name="Return to station"
        )
        .build()
    )
    
    return routine

def create_patrol_routine() -> Routine:
    """Create patrol routine between markers.
    
    This routine continuously patrols between markers 0, 1, 2, 3.
    """
    # Create the patrol sequence
    patrol_actions = [
        SearchForMarkerAction(0, timeout=10, name="Find marker 0"),
        NavigateToMarkerAction(
            MarkerGoal(marker_id=0, distance_cm=40),
            name="Go to marker 0"
        ),
        WaitAction(2, name="Pause at marker 0"),
        
        SearchForMarkerAction(1, timeout=10, name="Find marker 1"),
        NavigateToMarkerAction(
            MarkerGoal(marker_id=1, distance_cm=40),
            name="Go to marker 1"
        ),
        WaitAction(2, name="Pause at marker 1"),
        
        SearchForMarkerAction(2, timeout=10, name="Find marker 2"),
        NavigateToMarkerAction(
            MarkerGoal(marker_id=2, distance_cm=40),
            name="Go to marker 2"
        ),
        WaitAction(2, name="Pause at marker 2"),
        
        SearchForMarkerAction(3, timeout=10, name="Find marker 3"),
        NavigateToMarkerAction(
            MarkerGoal(marker_id=3, distance_cm=40),
            name="Go to marker 3"
        ),
        WaitAction(2, name="Pause at marker 3"),
    ]
    
    # Create routine with infinite loop
    routine = Routine("Patrol", "Continuously patrol between markers")
    routine.add_action(LoopAction(patrol_actions, count=-1, name="Patrol loop"))
    
    return routine

def create_conditional_delivery_routine() -> Routine:
    """Create delivery routine with conditional logic.
    
    This routine checks if marker 3 (delivery point) is visible.
    If visible, delivers directly. If not, searches for it first.
    """
    routine = Routine("Smart Delivery", "Delivery with conditional navigation")
    
    # Start at station
    routine.add_action(SearchForMarkerAction(0, timeout=10, name="Find station"))
    routine.add_action(NavigateToMarkerAction(
        MarkerGoal(marker_id=0, distance_cm=30),
        name="Position at station"
    ))
    
    # Pick up beverage (simplified)
    routine.add_action(ActuatorAction("extend", duration=2, speed=40, name="Grab item"))
    routine.add_action(WaitAction(1, name="Secure grip"))
    
    # Conditional delivery based on marker 3 visibility
    if_visible_actions = [
        # Marker 3 is visible, go directly
        NavigateToMarkerAction(
            MarkerGoal(marker_id=3, distance_cm=25),
            name="Direct delivery"
        )
    ]
    
    if_not_visible_actions = [
        # Marker 3 not visible, search first
        TurnAction(360, speed=25, name="Full rotation search"),
        SearchForMarkerAction(3, timeout=15, name="Extended search"),
        NavigateToMarkerAction(
            MarkerGoal(marker_id=3, distance_cm=25),
            name="Navigate after search"
        )
    ]
    
    routine.add_action(ConditionalAction(
        marker_id=3,
        if_visible=if_visible_actions,
        if_not_visible=if_not_visible_actions,
        name="Check delivery visibility"
    ))
    
    # Release item
    routine.add_action(ActuatorAction("retract", duration=2, speed=50, name="Release item"))
    routine.add_action(MoveAction(-25, -25, duration=1, name="Back away"))
    
    return routine

def create_approach_demo_routine() -> Routine:
    """Create routine demonstrating different approach angles.
    
    Shows how to approach the same marker from different directions.
    """
    builder = RoutineBuilder("Approach Demo", "Demonstrates different marker approaches")
    
    routine = (builder
        # Approach from front
        .search_for_marker(1, timeout=10, name="Find marker")
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.FRONT,
            distance_cm=30,
            name="Front approach"
        )
        .wait(2, "Show front position")
        .move(-30, -30, duration=1.5, name="Back away")
        
        # Approach from left
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.LEFT,
            distance_cm=30,
            name="Left approach"
        )
        .wait(2, "Show left position")
        .move(-30, -30, duration=1.5, name="Back away")
        
        # Approach from right
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.RIGHT,
            distance_cm=30,
            name="Right approach"
        )
        .wait(2, "Show right position")
        .move(-30, -30, duration=1.5, name="Back away")
        
        # Custom angle approach (45 degrees)
        .navigate_to_marker(
            marker_id=1,
            approach=MarkerApproach.CUSTOM,
            distance_cm=30,
            angle_degrees=45,
            name="45° approach"
        )
        .wait(2, "Show angled position")
        .build()
    )
    
    return routine

def save_all_examples():
    """Save all example routines to files."""
    manager = RoutineManager()
    
    # Create and save each routine
    routines = [
        create_fridge_open_routine(),
        create_beverage_pickup_routine(),
        create_delivery_routine(),
        create_patrol_routine(),
        create_conditional_delivery_routine(),
        create_approach_demo_routine()
    ]
    
    for routine in routines:
        filename = manager.save_routine(routine)
        print(f"Saved: {filename}")
    
    print(f"\nAll routines saved to {manager.routines_dir}")
    print(f"Available routines: {manager.list_routines()}")

if __name__ == "__main__":
    save_all_examples()