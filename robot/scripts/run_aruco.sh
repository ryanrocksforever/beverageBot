#!/bin/bash
# Run BevBot ArUco detection test

cd "$(dirname "$0")/.."

echo "=== BevBot ArUco Detection Test ==="
echo "This will start live ArUco marker detection"
echo "Press 'q' or Ctrl+C to quit"
echo ""
echo "Usage:"
echo "  $0                    # Default: DICT_4X4_50, 1920x1080, with display"
echo "  $0 --dict DICT_5X5_50 --camera-res 1280x720"
echo "  $0 --no-display      # Headless mode"
echo ""

# Check USB camera
if ! python3 -c "import cv2; cam = cv2.VideoCapture(0); available = cam.isOpened(); cam.release(); exit(0 if available else 1)" 2>/dev/null; then
    echo "❌ USB Camera not available"
    echo "Make sure USB camera is connected. Check with: lsusb | grep -i camera"
    exit 1
fi

echo "✓ USB Camera available"
echo ""

# Run the ArUco test
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.aruco_test "$@"