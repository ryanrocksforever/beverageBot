#!/bin/bash
# Check OpenCV version and provide update instructions

cd "$(dirname "$0")/.."

echo "=== OpenCV Version Check ==="
echo ""

# Check current OpenCV version
echo "Current OpenCV version:"
python3 -c "import cv2; print(f'OpenCV: {cv2.__version__}')"

# Check if ArUco module is available
python3 -c "
import cv2
import sys

version = cv2.__version__
major, minor = map(int, version.split('.')[:2])

print(f'\nVersion details:')
print(f'  Major: {major}')
print(f'  Minor: {minor}')

if hasattr(cv2, 'aruco'):
    print('  ArUco module: Available')
    
    if hasattr(cv2.aruco, 'ArucoDetector'):
        print('  ArUco API: New (4.7+)')
    else:
        print('  ArUco API: Old (< 4.7)')
else:
    print('  ArUco module: NOT AVAILABLE')
    sys.exit(1)
" || echo "Error checking OpenCV"

echo ""
echo "=== How to Update OpenCV ==="
echo ""
echo "Option 1: Update via pip (recommended for latest version):"
echo "  pip3 install --upgrade opencv-python opencv-contrib-python"
echo ""
echo "Option 2: Build from source for Raspberry Pi optimization:"
echo "  See: https://docs.opencv.org/4.x/d7/d9f/tutorial_linux_install.html"
echo ""
echo "Option 3: Use system packages (may be older):"
echo "  sudo apt update"
echo "  sudo apt install python3-opencv"
echo ""
echo "Note: OpenCV 4.7+ has the new ArUco API with better performance."
echo "Your current version will work with our code (we support both APIs)."