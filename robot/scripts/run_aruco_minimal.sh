#!/bin/bash
# Minimal ArUco detection following OpenCV documentation

cd "$(dirname "$0")/.."

echo "=== Minimal ArUco Detection ==="
echo "This follows the OpenCV documentation example exactly"
echo "Press 'q' or ESC to quit"
echo ""

# Run the minimal ArUco test
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.aruco_minimal