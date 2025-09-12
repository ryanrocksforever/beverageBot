# BevBot Control System - Production

## Project Structure

The BevBot project has been reorganized into a clean production structure:

```
robot/
├── production/          # Production-ready code
│   ├── gui/            # Main control center GUI
│   ├── core/           # Core robot functionality
│   ├── config/         # Configuration files
│   └── launch.py       # Main launch script
├── tools/              # Development and calibration tools
│   ├── calibration/    # Marker calibration tools
│   ├── testing/        # Hardware testing utilities
│   └── generation/     # Marker generation tools
├── routines/           # Saved robot routines
└── src/                # Original source modules
```

## Quick Start

### Launch the Control Center

```bash
cd robot/production
python launch.py
```

This will start the BevBot Control Center with:
- Full GUI interface
- Manual control with camera feed
- Routine editor and executor
- ArUco marker navigation
- System settings and configuration

## Features

### 1. **Dashboard Tab**
- **Live Camera Feed**: Real-time video with ArUco marker detection
- **Manual Control**: Direction pad for movement, actuator controls
- **Quick Actions**: Pre-programmed routines like beverage delivery
- **Keyboard Control**: WASD + QE keys for direct control
- **Emergency Stop**: Instant system halt

### 2. **Routine Editor Tab**
- **Visual Routine Builder**: Drag-and-drop action creation
- **Action Types**:
  - Movement (forward, backward, turn, rotate)
  - Navigation (navigate to marker, align with marker)
  - Actuator (extend, retract, open/close door)
  - Object manipulation (pickup, release)
  - Control flow (wait, loops, conditionals)
- **Recording Mode**: Record manual actions into routines
- **Routine Library**: Save and load routine files
- **Simulation Mode**: Test routines without hardware

### 3. **Navigation Tab**
- **Marker Detection**: Real-time ArUco marker tracking
- **Marker Database**: Manage marker definitions and positions
- **Calibration**: Save precise robot positions relative to markers
- **Navigation Control**: Direct navigation to specific markers

### 4. **Settings Tab**
- **Robot Settings**: Speed limits, thresholds
- **Camera Settings**: Enable/disable vision features
- **System Settings**: Simulation mode, debug options
- **Configuration**: Save/load system configuration

## Pre-configured Routines

### Beverage Delivery
The complete fridge-to-couch delivery routine:
1. Navigate to fridge marker
2. Align with door at 30cm
3. Open fridge door (extend actuator)
4. Navigate to inside fridge marker
5. Pick up beverage
6. Back out of fridge
7. Close door (retract actuator)
8. Navigate to couch marker
9. Release beverage

### Quick Actions
- **Door Sequence**: Open and close door
- **Navigate Home**: Return to home marker
- **Test Navigation**: System diagnostic

## Development Tools

### Calibration Tools
```bash
# Interactive calibration mode
python tools/calibration/calibrate_markers.py --interactive

# Save current position for marker
python tools/calibration/calibrate_markers.py --save 1

# List saved positions
python tools/calibration/calibrate_markers.py --list
```

### Marker Generation
```bash
# Generate navigation marker set
python tools/generation/generate_markers.py --preset navigation

# Generate beverage delivery markers
python tools/generation/generate_markers.py --preset beverage --size 10

# Custom markers
python tools/generation/generate_markers.py --ids 0 1 2 3 --size 15
```

### Motor Testing
```bash
# Test all motors
python tools/testing/test_motors.py

# Interactive control
python tools/testing/test_motors.py --interactive

# Test specific motor
python tools/testing/test_motors.py --left --duration 3
```

## ArUco Markers

### Standard Marker Assignments
- **0**: Home position
- **1**: Fridge door
- **2**: Inside fridge
- **3**: Couch
- **4**: Kitchen
- **5**: Living room
- **6-9**: Additional navigation points

### Marker Setup
1. Print markers at 10cm x 10cm size
2. Mount at robot camera height (~30-50cm)
3. Ensure good lighting and contrast
4. Calibrate positions using the GUI

## Hardware Configuration

### GPIO Pin Assignments
- **Left Motor**: Pins defined in `src/pins.py`
- **Right Motor**: Pins defined in `src/pins.py`  
- **Actuator**: Pins defined in `src/pins.py`

### Camera
- USB camera or Raspberry Pi camera module
- 640x480 resolution minimum
- 30 FPS recommended

## Simulation Mode

The system automatically detects hardware availability:
- **Hardware Mode**: Full robot control with motors and actuator
- **Simulation Mode**: GUI only, perfect for routine development

## Creating Custom Routines

### Using the GUI
1. Open Routine Editor tab
2. Click "New" to create routine
3. Add actions using the toolbar
4. Configure each action's parameters
5. Test with "Simulate" button
6. Run with "Run" button

### Using Recording Mode
1. Click "Record" in Routine Editor
2. Manually control the robot
3. Actions are automatically recorded
4. Stop recording to save actions
5. Edit and refine as needed

## File Formats

### Routine Files (.json)
```json
{
  "name": "Beverage Delivery",
  "description": "Complete delivery routine",
  "actions": [...],
  "tags": ["delivery", "fridge"],
  "version": "1.0"
}
```

### Configuration (config/bevbot_config.json)
```json
{
  "max_speed": 100,
  "min_speed_threshold": 10,
  "camera_enabled": true,
  "marker_detection": true,
  "simulation_mode": false
}
```

## Troubleshooting

### Camera Not Found
- Check USB connection
- Verify camera permissions
- Try different camera index in settings

### Motors Not Responding
- Check GPIO connections
- Verify motor driver power
- Test with `tools/testing/test_motors.py`

### Markers Not Detected
- Ensure adequate lighting
- Check marker size and print quality
- Verify camera focus

### GUI Performance
- Reduce camera resolution if needed
- Disable marker detection when not needed
- Close other applications

## Safety

- Always have emergency stop ready
- Test routines in simulation first
- Start with low speeds
- Ensure clear path for robot
- Monitor battery levels

## Support

For issues or questions:
- Check hardware connections
- Review system logs
- Test individual components with tools
- Verify configuration settings