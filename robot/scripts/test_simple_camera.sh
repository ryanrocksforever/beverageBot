#!/bin/bash
# Test camera with the proven simple approach

cd "$(dirname "$0")/.."

echo "=== Simple Camera Test ==="
echo "Testing camera with the exact approach from your working script"
echo "Press ESC or Q to quit the camera view"
echo ""

# Run the simple camera test
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.simple_camera_test