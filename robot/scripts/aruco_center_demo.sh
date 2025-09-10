#!/bin/bash
# Launch ArUco marker centering demonstration with GUI
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
echo "=== BevBot ArUco Marker Centering Demo ==="
echo ""
echo "This demo will:"
echo "1. Display camera feed with ArUco marker detection"
echo "2. Track and center on detected markers"
echo "3. Control motors to keep marker centered"
echo ""
echo "Controls:"
echo "- Click 'Start Tracking' to begin centering behavior"
echo "- Click 'Stop Motors' for emergency stop"
echo "- Select specific marker ID or 'Any' to track closest"
echo ""
echo "Make sure you have printed ArUco markers (4x4_50 dictionary)"
echo "You can generate them using: ./generate_aruco_markers.sh"
echo ""
echo "Starting GUI..."

# Check for required Python packages
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

# Set display for GUI (if SSH with X forwarding)
if [ -n "$SSH_CLIENT" ] && [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
    echo "Note: Running over SSH, setting DISPLAY=:0"
    echo "Make sure X11 forwarding is enabled or use VNC"
fi

# Run the demo
python3 -m src.aruco_center_demo "$@"