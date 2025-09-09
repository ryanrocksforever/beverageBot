#!/bin/bash
# Debug camera issues for BevBot

cd "$(dirname "$0")/.."

echo "=== BevBot Camera Debug Tool ==="
echo "This will test your USB camera setup and diagnose issues"
echo ""

# Check dependencies
if ! python3 -c "import cv2" 2>/dev/null; then
    echo "❌ OpenCV not available. Install with:"
    echo "pip3 install opencv-python"
    exit 1
fi

echo "✓ OpenCV available"
echo ""

# Run the camera debug tool
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.camera_debug

echo ""
echo "If issues persist, try:"
echo "  1. Different USB port"
echo "  2. Lower resolution: --camera-res 640x480"
echo "  3. Different camera index: CameraInterface(camera_index=1)"
echo "  4. Check permissions: sudo usermod -a -G video \$USER"