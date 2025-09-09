# BevBot - Raspberry Pi 5 Robot Control

A Python robotics control system for Raspberry Pi 5 with BTS7960 motor drivers, USB camera, and ArUco detection.

## Hardware Requirements

- Raspberry Pi 5
- USB Camera (1080p recommended)
- 3x BTS7960 motor driver modules
- 2x DC drive motors
- 1x 12V linear actuator
- 12V power supply + buck converter for actuator
- Push button and LED/buzzer for testing

## Pin Wiring Diagram

| Component | Pin | GPIO | Description |
|-----------|-----|------|-------------|
| **Left Motor** | | | |
| BTS7960 R_EN | 29 | GPIO5 | Right enable |
| BTS7960 L_EN | 31 | GPIO6 | Left enable |
| BTS7960 RPWM | 12 | GPIO18 | Right PWM (hardware PWM) |
| BTS7960 LPWM | 33 | GPIO13 | Left PWM (hardware PWM) |
| **Right Motor** | | | |
| BTS7960 R_EN | 38 | GPIO20 | Right enable |
| BTS7960 L_EN | 40 | GPIO21 | Left enable |
| BTS7960 RPWM | 35 | GPIO19 | Right PWM (hardware PWM) |
| BTS7960 LPWM | 32 | GPIO12 | Left PWM (hardware PWM) |
| **Actuator** | | | |
| BTS7960 R_EN | 36 | GPIO16 | Right enable |
| BTS7960 L_EN | 37 | GPIO26 | Left enable |
| BTS7960 RPWM | 16 | GPIO23 | Right PWM (hardware PWM) |
| BTS7960 LPWM | 18 | GPIO24 | Left PWM (hardware PWM) |
| **IO** | | | |
| Test Button | 11 | GPIO17 | Pull-up enabled |
| LED/Buzzer | 13 | GPIO27 | Output |

## BTS7960 Wiring Notes

Each BTS7960 module should be wired as follows:
- **VCC**: 5V from Pi
- **GND**: Ground (common with Pi)
- **R_EN/L_EN**: Enable pins to respective GPIO
- **RPWM/LPWM**: PWM control pins to respective GPIO
- **Motor terminals**: M+ and M- to motor
- **Power**: B+ to battery positive, B- to battery negative

⚠️ **Safety**: Always connect motor power (B+/B-) AFTER connecting control signals to prevent unexpected motor movement.

## Installation

1. **On Raspberry Pi 5**:
   ```bash
   cd robot
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

2. **Manual installation** (if setup script fails):
   ```bash
   # System packages
   sudo apt update
   sudo apt install python3-pip python3-picamera2 python3-opencv pigpio
   
   # Python packages
   pip3 install pigpio opencv-python numpy
   
   # Start pigpiod daemon
   sudo systemctl enable pigpiod
   sudo systemctl start pigpiod
   ```

## Usage

### Hardware IO Test
Tests all motors, actuator, camera, and GPIO:
```bash
cd robot
./scripts/run_io_test.sh
```

**Safety**: Hold the test button (GPIO17) during motor tests to skip motor movements.

### ArUco Marker Detection
Live ArUco marker detection with camera preview:
```bash
cd robot
./scripts/run_aruco.sh

# With options:
./scripts/run_aruco.sh --dict DICT_5X5_50 --camera-res 640x480
./scripts/run_aruco.sh --no-display  # Headless mode
```

## Safety Features

- **Emergency stop**: Button on GPIO17 (active low) skips motor tests when held
- **Safe shutdown**: Ctrl+C gracefully stops all motors and disables drivers
- **Context managers**: All hardware classes support `with` statements for automatic cleanup
- **Error handling**: Comprehensive exception handling with safe fallbacks

## Hardware PWM Usage

The code uses hardware PWM on these pins for precise motor control:
- GPIO12, GPIO13, GPIO18, GPIO19 (PWM0 channel)
- GPIO23, GPIO24 (PWM1 channel)

## Troubleshooting

### pigpiod Issues
```bash
# Check if running
sudo systemctl status pigpiod

# Restart if needed
sudo systemctl restart pigpiod

# Test connection
python3 -c "import pigpio; pi = pigpio.pi(); print('Connected:', pi.connected); pi.stop()"
```

### Camera Issues
```bash
# Enable camera in raspi-config
sudo raspi-config
# Navigate to Interface Options > Camera > Enable

# Check camera detection
python3 -c "from picamera2 import Picamera2; cam = Picamera2(); print('Camera OK'); cam.close()"
```

### Permission Issues
```bash
# Add user to video group
sudo usermod -a -G video $USER
# Log out and back in for changes to take effect
```

## Code Structure

- `src/pins.py`: GPIO pin definitions and PWM utilities
- `src/motor.py`: BTS7960 motor driver with shared pigpio instance
- `src/actuator.py`: Linear actuator wrapper using BTS7960 driver
- `src/camera.py`: Picamera2 interface with frame capture
- `src/io_test.py`: Hardware test suite
- `src/aruco_test.py`: ArUco detection with live preview
- `scripts/setup.sh`: System setup and dependency installation
- `scripts/run_*.sh`: Test execution scripts

## Development Notes

This project is designed for deployment on Raspberry Pi 5 but can be developed on other platforms. Hardware-specific modules (pigpio, picamera2) will show import warnings on non-Pi systems but won't break the code structure.