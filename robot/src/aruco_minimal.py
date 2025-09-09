#!/usr/bin/env python3
"""Minimal ArUco detection following OpenCV documentation exactly."""

import cv2
import numpy as np
import glob
import os
import sys

def main():
    """Main detection loop as per OpenCV documentation."""
    
    # Setup dictionary and detector parameters exactly as in documentation
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detectorParams = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, detectorParams)
    
    # Open camera using the proven approach
    devs = sorted(glob.glob("/dev/v4l/by-id/*")) or ["/dev/video0"]
    
    inputVideo = None
    for dev in devs:
        try:
            path = os.path.realpath(dev)
            cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
            if cap.isOpened():
                print(f"Opened camera: {dev} -> {path}")
                inputVideo = cap
                break
        except:
            continue
    
    if inputVideo is None:
        print("Cannot open camera")
        return 1
    
    # Set resolution
    inputVideo.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    inputVideo.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    print("Starting detection (press 'q' or ESC to quit)...")
    waitTime = 10
    
    while inputVideo.grab():
        ret, image = inputVideo.retrieve()
        if not ret:
            continue
            
        # Copy image for display
        imageCopy = image.copy()
        
        # Detect markers
        markerCorners, markerIds, rejectedCandidates = detector.detectMarkers(image)
        
        # Draw results
        if len(markerCorners) > 0:
            cv2.aruco.drawDetectedMarkers(imageCopy, markerCorners, markerIds)
            print(f"Detected markers: {markerIds.flatten().tolist() if markerIds is not None else []}")
        
        # Try to show image (with error handling for headless)
        try:
            cv2.imshow("ArUco Detection", imageCopy)
            key = cv2.waitKey(waitTime) & 0xFF
            if key == 27 or key == ord('q'):  # ESC or q
                break
        except Exception as e:
            print(f"Display not available: {e}")
            print("Running headless - press Ctrl+C to stop")
            # In headless mode, just continue detecting
            pass
    
    inputVideo.release()
    cv2.destroyAllWindows()
    return 0

if __name__ == "__main__":
    sys.exit(main())