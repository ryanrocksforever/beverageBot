# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BevBot is a Python-based autonomous robot system for Raspberry Pi 5 that uses computer vision (ArUco markers) for navigation. The primary application is autonomous beverage delivery - navigating to a fridge, opening it with a linear actuator, retrieving beverages, and delivering them to specified locations.

## Architecture

### Core Components
- **Hardware Abstraction**: Shared pigpio instance (`PigpioWrapper` singleton) with context managers for automatic cleanup
- **Motor Control**: BTS7960 dual H-bridge drivers controlling 2 drive motors + 1 linear actuator
- **Vision System**: OpenCV-based ArUco marker detection for autonomous navigation
- **GUI Control Center**: Tkinter-based interface for manual control and routine programming
- **Routine Engine**: JSON-based visual programming system with static actions and dynamic goals

### Directory Structure
```
robot/
├── src/                    # Core hardware drivers and navigation
├── production/             # Production GUI application
│   ├── gui/               # Control center interface
│   ├── core/              # Robot control logic
│   └── config/            # Configuration management
├── tools/                  # Development utilities
├── routines/              # Saved routine JSON files
└── scripts/               # Shell script wrappers
```

### Key Files
- `src/pins.py` - GPIO pin definitions (hardware PWM on specific pins)
- `src/motor.py` - BTS7960 motor driver implementation
- `src/robot_controller.py` - High-level robot control interface
- `production/launch.py` - Main GUI entry point
- `marker_database.json` - ArUco marker definitions

## Common Development Commands

### Running the Application
```bash
# Main control center GUI (production)
cd robot/production && python launch.py

# Hardware testing suite
cd robot && ./scripts/run_io_test.sh

# Test specific components
./scripts/test_actuator.sh
python tools/testing/test_motors.py
```

### Vision and Navigation
```bash
# Live ArUco marker detection
./scripts/run_aruco.sh --dict DICT_5X5_50 --camera-res 1280x720

# Navigation demos
./scripts/demo_beverage_delivery.sh
./scripts/aruco_navigate.sh
```

### Marker Generation
```bash
# Generate standard markers (works on any platform)
python -m src.generate_markers --output bevbot_markers.pdf
python tools/generation/generate_markers.py --preset beverage --size 10
```

### Calibration
```bash
python tools/calibration/calibrate_markers.py --interactive
python tools/calibration/calibrate_markers.py --save 1  # Save position for marker ID 1
```

## Hardware Requirements

- **Raspberry Pi 5** with pigpiod daemon running (`sudo systemctl start pigpiod`)
- **PWM Pins**: PWM0 channel (GPIO 12,13,18,19), PWM1 channel (GPIO 23,24)
- **Motor Drivers**: 3x BTS7960 modules (2 drive motors, 1 actuator)
- **Camera**: USB camera (640x480 minimum, 1080p recommended)
- **Markers**: DICT_4X4_50 or DICT_5X5_50, printed at 10cm x 10cm

Standard marker assignments:
- ID 0: Home base
- ID 1: Fridge door
- ID 2: Inside fridge
- ID 3: Delivery location

## Development Notes

### Dual Mode Operation
- **Hardware Mode**: Full robot control on Raspberry Pi 5
- **Simulation Mode**: GUI-only for routine development (auto-detected on non-Pi systems)

### Context Managers
All hardware classes implement `__enter__`/`__exit__` for automatic cleanup:
```python
with Motor(pins_config) as motor:
    motor.forward(50)  # Automatically stops and cleans up on exit
```

### Routine System
Routines are JSON files with action types:
- **Static**: Move, Turn, Actuator, Wait
- **Dynamic**: NavigateToMarker, AlignWithMarker, SearchForMarker
- **Control**: Conditional, Loop, Parallel, Subroutine

### Testing Hardware
When testing motors/actuator, use the test button (GPIO17) to skip movements during development.

### Troubleshooting
```bash
# Check pigpiod connection
python3 -c "import pigpio; pi = pigpio.pi(); print('Connected:', pi.connected)"

# Verify camera
python3 -c "import cv2; cam = cv2.VideoCapture(0); print(cam.isOpened())"

# Restart pigpiod if needed
sudo systemctl restart pigpiod
```

## Important Patterns

1. **Shared pigpio instance** - Never create multiple `pigpio.pi()` connections
2. **Hardware PWM only** - Use designated PWM pins from `src/pins.py`
3. **Context managers** - Always use `with` statements for hardware resources
4. **Simulation fallback** - Code gracefully degrades when hardware unavailable
5. **Marker-based navigation** - All autonomous navigation uses ArUco markers