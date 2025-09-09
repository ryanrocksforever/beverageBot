#!/bin/bash
# Safe ArUco detection with automatic headless fallback

cd "$(dirname "$0")/.."

echo "=== Safe ArUco Detection Test ==="
echo "Automatically detects display availability"
echo "Falls back to headless mode if needed"
echo ""

# Check if running over SSH without X forwarding
if [ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]; then
    if [ -z "$DISPLAY" ]; then
        echo "SSH session detected without X forwarding"
        echo "Will run in headless mode"
    fi
fi

# Check display variable
if [ -z "$DISPLAY" ]; then
    echo "No DISPLAY variable set"
    echo "Running in headless mode"
fi

echo ""
echo "Options:"
echo "  --headless        Force headless mode"
echo "  --camera-res WxH  Set resolution (default: 1280x720)"
echo "  --dict NAME       ArUco dictionary (default: DICT_4X4_50)"
echo ""

# Run the safe ArUco test
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.aruco_safe "$@"