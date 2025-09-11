#!/bin/bash
# Test ArUco marker distance measurement

cd "$(dirname "$0")/.." || exit 1

echo "=== ArUco Distance Measurement Test ==="
echo ""
echo "Camera: Innomaker 1080P 130° Wide Angle"
echo "Marker Size: 100mm"
echo "Focal Length: 149 pixels (for 640x480)"
echo ""
echo "This will display real-time distance measurements."
echo "Place a 100mm ArUco marker in front of the camera."
echo ""

python3 - << 'EOF'
import cv2
import numpy as np
import time
from src.camera import CameraInterface
from src.aruco_center_demo import ArUcoDetector
from src.camera_config import MARKER_SIZE_CM, CAMERA_MATRIX

print("Initializing camera...")
camera = CameraInterface()
if not camera.is_available():
    print("Camera not available!")
    exit(1)

camera.start()
detector = ArUcoDetector(marker_size_cm=MARKER_SIZE_CM)

print("Starting distance measurement (Press Ctrl+C to stop)")
print("")
print("Focal length:", CAMERA_MATRIX[0,0], "pixels")
print("Marker size:", MARKER_SIZE_CM, "cm")
print("")

try:
    while True:
        frame, _ = camera.capture_frame()
        markers = detector.detect_markers(frame)
        
        if markers:
            print("Detected markers:")
            for marker_id, marker in markers.items():
                print(f"  ID {marker_id}: {marker.distance:.1f}cm (size: {marker.size:.1f}px)")
        else:
            print("No markers detected", end='')
        
        print("                    ", end='\r')  # Clear line
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("\n\nStopping...")
finally:
    camera.stop()
    
print("Test complete!")
EOF