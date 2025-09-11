#!/usr/bin/env python3
"""Test script for the new routine system."""

import sys
import time
import logging
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.motor_gpiozero import MotorController
from src.camera import CameraInterface
from src.aruco_center_demo import ArUcoDetector
from src.camera_config import MARKER_SIZE_CM
from src.routine_system import RoutineContext, RoutineExecutor
from src.routine_factory import RoutineManager, ActionFactory
from src.routine_navigator import RoutineNavigator
from src.routine_examples import (
    create_fridge_open_routine,
    create_beverage_pickup_routine,
    create_delivery_routine,
    create_patrol_routine,
    create_conditional_delivery_routine,
    create_approach_demo_routine,
    save_all_examples
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RoutineTestSystem:
    """System for testing and running routines."""
    
    def __init__(self):
        """Initialize test system."""
        logger.info("Initializing routine test system...")
        
        # Initialize hardware
        self.robot = MotorController()
        self.camera = CameraInterface()
        self.detector = ArUcoDetector(marker_size_cm=MARKER_SIZE_CM)
        
        # Check camera
        if not self.camera.is_available():
            logger.error("Camera not available!")
            self.camera = None
            self.navigator = None
        else:
            self.camera.start()
            # Create navigator
            self.navigator = RoutineNavigator(self.robot, self.camera, self.detector)
        
        # Create routine context
        self.context = RoutineContext(
            robot=self.robot,
            navigator=self.navigator,
            camera=self.camera
        )
        
        # Create executor
        self.executor = RoutineExecutor(self.context)
        
        # Create routine manager
        self.manager = RoutineManager()
        
        logger.info("System initialized")
    
    def list_routines(self):
        """List available routines."""
        print("\nAvailable Routines:")
        print("-" * 40)
        
        # List saved routines
        saved = self.manager.list_routines()
        if saved:
            print("Saved routines:")
            for i, name in enumerate(saved, 1):
                print(f"  {i}. {name}")
        else:
            print("No saved routines found")
        
        # List example routines
        print("\nExample routines (not saved):")
        examples = [
            "fridge_open",
            "beverage_pickup",
            "delivery",
            "patrol",
            "conditional_delivery",
            "approach_demo"
        ]
        for i, name in enumerate(examples, 1):
            print(f"  {i}. {name}")
    
    def run_routine(self, routine_name: str):
        """Run a specific routine.
        
        Args:
            routine_name: Name of routine to run
        """
        # Try to load saved routine first
        try:
            routine = self.manager.load_routine(routine_name)
            logger.info(f"Loaded saved routine: {routine_name}")
        except FileNotFoundError:
            # Try to create example routine
            logger.info(f"Creating example routine: {routine_name}")
            
            if routine_name == "fridge_open":
                routine = create_fridge_open_routine()
            elif routine_name == "beverage_pickup":
                routine = create_beverage_pickup_routine()
            elif routine_name == "delivery":
                routine = create_delivery_routine()
            elif routine_name == "patrol":
                routine = create_patrol_routine()
            elif routine_name == "conditional_delivery":
                routine = create_conditional_delivery_routine()
            elif routine_name == "approach_demo":
                routine = create_approach_demo_routine()
            else:
                logger.error(f"Unknown routine: {routine_name}")
                return
        
        # Execute routine
        print(f"\n{'='*50}")
        print(f"Running routine: {routine.name}")
        print(f"Description: {routine.description}")
        print(f"Actions: {len(routine.actions)}")
        print(f"{'='*50}\n")
        
        # Run synchronously so we can monitor
        result = self.executor.execute(routine, async_exec=False)
        
        if result.success:
            print(f"\n✓ Routine completed successfully!")
            print(f"  Duration: {result.duration:.1f}s")
        else:
            print(f"\n✗ Routine failed!")
            print(f"  Error: {result.message}")
    
    def interactive_mode(self):
        """Run interactive routine testing mode."""
        print("\n" + "="*50)
        print("BevBot Routine System - Interactive Mode")
        print("="*50)
        
        while True:
            print("\nOptions:")
            print("1. List available routines")
            print("2. Run a routine")
            print("3. Save example routines")
            print("4. Create custom routine")
            print("5. Stop current routine")
            print("6. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == '1':
                self.list_routines()
            
            elif choice == '2':
                self.list_routines()
                routine_name = input("\nEnter routine name: ").strip()
                if routine_name:
                    self.run_routine(routine_name)
            
            elif choice == '3':
                print("Saving example routines...")
                save_all_examples()
                print("Done!")
            
            elif choice == '4':
                self.create_custom_routine()
            
            elif choice == '5':
                if self.executor.is_running:
                    print("Stopping current routine...")
                    self.executor.stop()
                    print("Stopped")
                else:
                    print("No routine currently running")
            
            elif choice == '6':
                print("Exiting...")
                break
            
            else:
                print("Invalid choice")
    
    def create_custom_routine(self):
        """Interactive custom routine builder."""
        print("\n=== Custom Routine Builder ===")
        
        name = input("Routine name: ").strip()
        if not name:
            print("Name required")
            return
        
        description = input("Description (optional): ").strip()
        
        from src.routine_system import RoutineBuilder
        builder = RoutineBuilder(name, description)
        
        print("\nAdding actions (type 'done' to finish):")
        print("Available actions:")
        print("  move <left> <right> <duration>")
        print("  turn <angle> [speed]")
        print("  actuator <extend|retract> [duration] [speed]")
        print("  wait <duration>")
        print("  search <marker_id> [timeout]")
        print("  navigate <marker_id> [distance]")
        
        while True:
            action_str = input("\nAction: ").strip()
            
            if action_str.lower() == 'done':
                break
            
            parts = action_str.split()
            if not parts:
                continue
            
            action_type = parts[0].lower()
            
            try:
                if action_type == 'move' and len(parts) >= 4:
                    builder.move(float(parts[1]), float(parts[2]), float(parts[3]))
                
                elif action_type == 'turn' and len(parts) >= 2:
                    speed = float(parts[2]) if len(parts) > 2 else 30
                    builder.turn(float(parts[1]), speed)
                
                elif action_type == 'actuator' and len(parts) >= 2:
                    duration = float(parts[2]) if len(parts) > 2 else 0
                    speed = float(parts[3]) if len(parts) > 3 else 50
                    builder.actuator(parts[1], duration, speed)
                
                elif action_type == 'wait' and len(parts) >= 2:
                    builder.wait(float(parts[1]))
                
                elif action_type == 'search' and len(parts) >= 2:
                    timeout = float(parts[2]) if len(parts) > 2 else 10
                    builder.search_for_marker(int(parts[1]), timeout)
                
                elif action_type == 'navigate' and len(parts) >= 2:
                    distance = float(parts[2]) if len(parts) > 2 else 30
                    builder.navigate_to_marker(int(parts[1]), distance)
                
                else:
                    print(f"Invalid action: {action_str}")
                    continue
                
                print(f"Added: {action_str}")
                
            except (ValueError, IndexError) as e:
                print(f"Error parsing action: {e}")
        
        # Build and optionally save
        routine = builder.build()
        print(f"\nCreated routine '{routine.name}' with {len(routine.actions)} actions")
        
        if input("Save routine? (y/n): ").strip().lower() == 'y':
            filepath = self.manager.save_routine(routine)
            print(f"Saved to: {filepath}")
        
        if input("Run routine? (y/n): ").strip().lower() == 'y':
            result = self.executor.execute(routine, async_exec=False)
            if result.success:
                print("✓ Routine completed!")
            else:
                print(f"✗ Routine failed: {result.message}")
    
    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        
        # Stop any running routine
        if self.executor.is_running:
            self.executor.stop()
        
        # Stop hardware
        self.robot.cleanup()
        if self.camera:
            self.camera.stop()
        
        logger.info("Cleanup complete")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="BevBot Routine System Test")
    parser.add_argument('--routine', '-r', help="Run specific routine")
    parser.add_argument('--list', '-l', action='store_true', help="List available routines")
    parser.add_argument('--save-examples', action='store_true', help="Save example routines")
    parser.add_argument('--interactive', '-i', action='store_true', help="Interactive mode")
    
    args = parser.parse_args()
    
    # Create test system
    system = RoutineTestSystem()
    
    try:
        if args.list:
            system.list_routines()
        
        elif args.save_examples:
            print("Saving example routines...")
            save_all_examples()
            print("Done!")
        
        elif args.routine:
            system.run_routine(args.routine)
        
        elif args.interactive or not any(vars(args).values()):
            # Default to interactive mode
            system.interactive_mode()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    finally:
        system.cleanup()

if __name__ == "__main__":
    main()