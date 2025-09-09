#!/usr/bin/env python3
"""Safe ArUco detection with automatic headless fallback."""

import os
import sys
import cv2
import numpy as np
import time
import logging
from typing import List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_display_available():
    """Check if display is available."""
    # Check for X11 display
    if os.environ.get('DISPLAY'):
        return True
    # Check for SSH session without X forwarding
    if os.environ.get('SSH_CLIENT') or os.environ.get('SSH_TTY'):
        logger.info("SSH session detected without X forwarding")
        return False
    # Try to detect if we're in a headless environment
    try:
        # Try to create a test window
        test_window = "test"
        cv2.namedWindow(test_window, cv2.WINDOW_NORMAL)
        cv2.destroyWindow(test_window)
        return True
    except Exception as e:
        logger.warning(f"Display test failed: {e}")
        return False

def run_safe_aruco(camera_res=(1280, 720), dict_name="DICT_4X4_50", force_headless=False):
    """Run ArUco detection with safe display handling."""
    
    # Check display availability
    has_display = not force_headless and check_display_available()
    
    if not has_display:
        logger.info("Running in headless mode (no display available)")
    else:
        logger.info("Display available, will show live view")
    
    # Setup ArUco
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.__dict__[dict_name])
    aruco_params = cv2.aruco.DetectorParameters()
    
    # Open camera using the working approach
    import glob
    devs = sorted(glob.glob("/dev/v4l/by-id/*")) or ["/dev/video0"]
    
    cap = None
    for dev in devs:
        try:
            path = os.path.realpath(dev)
            cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
            if cap.isOpened():
                logger.info(f"Opened camera: {dev} -> {path}")
                break
        except:
            continue
    
    if cap is None or not cap.isOpened():
        logger.error("Cannot open camera")
        return
    
    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_res[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_res[1])
    
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"Camera resolution: {actual_width}x{actual_height}")
    
    # Create window if display available
    if has_display:
        try:
            cv2.namedWindow("ArUco Safe", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("ArUco Safe", min(actual_width, 1280), min(actual_height, 720))
        except Exception as e:
            logger.error(f"Cannot create window: {e}")
            has_display = False
    
    # BevBot location mapping
    location_map = {
        1: "Home Base",
        2: "Fridge Side", 
        3: "Fridge Pickup",
        4: "Couch",
        5: "Outside"
    }
    
    frame_count = 0
    start_time = time.time()
    
    logger.info("Starting detection loop...")
    logger.info("Press Ctrl+C to stop")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.error("Failed to capture frame")
                break
            
            # Convert to grayscale for detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect markers
            try:
                detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
                corners, ids, rejected = detector.detectMarkers(gray)
            except AttributeError:
                # Fallback for older OpenCV
                corners, ids, rejected = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)
            
            # Process detections
            if ids is not None:
                marker_ids = ids.flatten().tolist()
                print(f"Frame {frame_count}: Detected markers: {marker_ids}")
                
                # Draw on frame if display available
                if has_display:
                    cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                    
                    # Add location labels
                    for i, marker_id in enumerate(marker_ids):
                        if marker_id in location_map:
                            corner = corners[i][0]
                            center = corner.mean(axis=0).astype(int)
                            cv2.putText(frame, location_map[marker_id], 
                                      (center[0] - 40, center[1] + 40),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                if frame_count % 30 == 0:  # Print every second
                    print(f"Frame {frame_count}: No markers detected")
            
            # Add FPS counter
            fps = frame_count / (time.time() - start_time + 0.001)
            if has_display:
                cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Show frame if display available
            if has_display:
                try:
                    cv2.imshow("ArUco Safe", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        logger.info("User quit")
                        break
                except Exception as e:
                    logger.error(f"Display error: {e}")
                    logger.info("Disabling display, continuing headless")
                    has_display = False
                    cv2.destroyAllWindows()
            
            frame_count += 1
            
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        cap.release()
        if has_display:
            cv2.destroyAllWindows()
        logger.info("Cleanup complete")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Safe ArUco detection")
    parser.add_argument("--camera-res", default="1280x720", help="Camera resolution")
    parser.add_argument("--dict", default="DICT_4X4_50", help="ArUco dictionary")
    parser.add_argument("--headless", action="store_true", help="Force headless mode")
    
    args = parser.parse_args()
    
    # Parse resolution
    width, height = map(int, args.camera_res.split('x'))
    
    run_safe_aruco(
        camera_res=(width, height),
        dict_name=args.dict,
        force_headless=args.headless
    )