#!/bin/bash
# Launch BevBot Remote Control GUI
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "Running on: $(cat /proc/device-tree/model)"
    echo "Hardware mode enabled"
else
    echo "Warning: Not running on Raspberry Pi - running in simulation mode"
fi

echo ""
echo "=== BevBot Remote Control System ==="
echo ""
echo "Features:"
echo "• Manual Control - Direct motor and actuator control"
echo "• Routine Programming - Record and playback movement sequences"
echo "• ArUco Tracking - Automatic marker following"
echo "• Camera Feed - Live video display"
echo ""
echo "Control Methods:"
echo "1. GUI Buttons - Click and hold movement buttons"
echo "2. Keyboard (when enabled):"
echo "   W/S - Forward/Backward"
echo "   A/D - Turn Left/Right"
echo "   Q/E - Extend/Retract actuator"
echo "   Space - Emergency stop"
echo ""
echo "Routine Programming:"
echo "1. Click 'Start Recording' in Routine tab"
echo "2. Perform movements using controls"
echo "3. Click 'Stop Recording'"
echo "4. Save routine or play it back"
echo ""

# Check for required Python packages
echo "Checking dependencies..."

python3 -c "import cv2" 2>/dev/null || {
    echo "Error: OpenCV (cv2) not installed"
    echo "Install with: pip3 install opencv-python opencv-contrib-python"
    exit 1
}

python3 -c "import PIL" 2>/dev/null || {
    echo "Error: Pillow not installed"
    echo "Install with: pip3 install Pillow"
    exit 1
}

python3 -c "import numpy" 2>/dev/null || {
    echo "Error: NumPy not installed"
    echo "Install with: pip3 install numpy"
    exit 1
}

python3 -c "import tkinter" 2>/dev/null || {
    echo "Error: tkinter not installed"
    echo "Install with: sudo apt-get install python3-tk"
    exit 1
}

# Set display for GUI (if SSH with X forwarding)
if [ -n "$SSH_CLIENT" ] && [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo ""
    echo "Note: Running over SSH, setting DISPLAY=:0"
    echo "For remote access, consider using:"
    echo "  - X11 forwarding: ssh -X pi@raspberry"
    echo "  - VNC viewer for full desktop access"
    echo "  - Run directly on Pi with attached display"
fi

echo ""
echo "Starting Remote Control GUI..."
echo "Press Ctrl+C to exit"
echo ""

# Run the remote control GUI
python3 -m src.remote_control_gui "$@"