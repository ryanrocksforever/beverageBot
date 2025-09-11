#!/usr/bin/env python3
"""Distance calibration utility for ArUco markers.

This utility helps calibrate the focal length parameter by measuring
markers at known distances.
"""

import cv2
import numpy as np
import sys
import time
sys.path.append('..')

from src.camera import CameraInterface
from src.aruco_center_demo import ArUcoDetector
from src.camera_config import MARKER_SIZE_CM, CAMERA_MATRIX

def calibrate_focal_length():
    """Interactive focal length calibration."""
    
    print("=== ArUco Distance Calibration ===")
    print(f"Using {MARKER_SIZE_CM*10}mm markers")
    print("")
    print("Instructions:")
    print("1. Place an ArUco marker at exactly 30cm from the camera")
    print("2. Make sure the marker is perpendicular to the camera")
    print("3. The marker should be clearly visible and centered")
    print("")
    
    # Initialize camera and detector
    camera = CameraInterface()
    if not camera.is_available():
        print("Camera not available!")
        return
    
    camera.start()
    detector = ArUcoDetector(marker_size_cm=MARKER_SIZE_CM)
    
    measurements = []
    actual_distances = []
    
    try:
        while True:
            print("\nOptions:")
            print("1. Measure at current position")
            print("2. Calculate focal length")
            print("3. Test with new focal length")
            print("4. Exit")
            
            choice = input("Choice: ").strip()
            
            if choice == '1':
                # Get actual distance
                distance_cm = input("Enter actual distance in cm: ").strip()
                try:
                    actual_distance = float(distance_cm)
                except ValueError:
                    print("Invalid distance")
                    continue
                
                # Capture and measure
                print("Measuring... ", end='')
                samples = []
                
                for _ in range(10):  # Take 10 samples
                    frame, _ = camera.capture_frame()
                    markers = detector.detect_markers(frame)
                    
                    if markers:
                        # Use first marker found
                        marker = list(markers.values())[0]
                        
                        # Calculate size
                        corners = marker.corners
                        width = np.linalg.norm(corners[0] - corners[1])
                        height = np.linalg.norm(corners[1] - corners[2])
                        size = (width + height) / 2
                        samples.append(size)
                    
                    time.sleep(0.1)
                
                if samples:
                    avg_size = np.mean(samples)
                    measurements.append(avg_size)
                    actual_distances.append(actual_distance)
                    
                    print(f"Done!")
                    print(f"Average marker size: {avg_size:.1f} pixels")
                    print(f"Actual distance: {actual_distance} cm")
                    
                    # Calculate what focal length would give correct distance
                    focal_length = (avg_size * actual_distance) / MARKER_SIZE_CM
                    print(f"Implied focal length: {focal_length:.1f} pixels")
                else:
                    print("No marker detected!")
                    
            elif choice == '2':
                if len(measurements) < 2:
                    print("Need at least 2 measurements")
                    continue
                
                # Calculate average focal length from all measurements
                focal_lengths = []
                for size, distance in zip(measurements, actual_distances):
                    fl = (size * distance) / MARKER_SIZE_CM
                    focal_lengths.append(fl)
                
                avg_focal_length = np.mean(focal_lengths)
                std_focal_length = np.std(focal_lengths)
                
                print(f"\nCalibration Results:")
                print(f"Average focal length: {avg_focal_length:.1f} pixels")
                print(f"Standard deviation: {std_focal_length:.1f} pixels")
                print(f"Current setting: {CAMERA_MATRIX[0,0]:.1f} pixels")
                print("")
                print(f"Recommended focal length: {avg_focal_length:.1f}")
                print("")
                print("Update src/camera_config.py with:")
                print(f"FOCAL_LENGTH_PIXELS = {int(avg_focal_length)}")
                
            elif choice == '3':
                try:
                    test_fl = float(input("Enter focal length to test: "))
                except ValueError:
                    print("Invalid focal length")
                    continue
                
                print(f"Testing with focal length: {test_fl}")
                print("Press Ctrl+C to stop")
                
                # Temporarily update detector
                detector.camera_matrix[0, 0] = test_fl
                detector.camera_matrix[1, 1] = test_fl
                
                while True:
                    frame, _ = camera.capture_frame()
                    markers = detector.detect_markers(frame)
                    
                    if markers:
                        for marker_id, marker in markers.items():
                            # Recalculate distance with new focal length
                            corners = marker.corners
                            width = np.linalg.norm(corners[0] - corners[1])
                            height = np.linalg.norm(corners[1] - corners[2])
                            size = (width + height) / 2
                            distance = (MARKER_SIZE_CM * test_fl) / size
                            
                            print(f"Marker {marker_id}: {distance:.1f}cm (size: {size:.1f}px)    ", end='\r')
                    
                    time.sleep(0.1)
                    
            elif choice == '4':
                break
            else:
                print("Invalid choice")
                
    except KeyboardInterrupt:
        print("\nCalibration interrupted")
    finally:
        camera.stop()
        
    print("\nCalibration complete!")

if __name__ == "__main__":
    calibrate_focal_length()