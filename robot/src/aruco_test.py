#!/usr/bin/env python3
"""ArUco marker detection test with live preview for BevBot."""

import argparse
import time
import logging
import signal
import sys
from typing import List, Tuple, Optional, Dict, Any
import cv2
import numpy as np

from .camera import CameraInterface

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ArUco dictionary mapping
ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
    "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
    "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
    "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
    "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
    "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
    "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
    "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
}

class ArucoDetector:
    """ArUco marker detector with live preview."""
    
    def __init__(self, 
                 dict_name: str = "DICT_4X4_50",
                 camera_width: int = 1920,
                 camera_height: int = 1080,
                 display: bool = True):
        """Initialize ArUco detector.
        
        Args:
            dict_name: ArUco dictionary name
            camera_width: Camera resolution width
            camera_height: Camera resolution height
            display: Show live preview window
        """
        self.dict_name = dict_name
        self.display = display
        self._running = True
        
        # Setup ArUco detection
        if dict_name not in ARUCO_DICTS:
            raise ValueError(f"Unknown ArUco dictionary: {dict_name}. Available: {list(ARUCO_DICTS.keys())}")
            
        self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICTS[dict_name])
        self.aruco_params = cv2.aruco.DetectorParameters_create()
        
        # Setup camera
        self.camera = CameraInterface(camera_width, camera_height)
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"ArUco detector initialized with {dict_name}, resolution {camera_width}x{camera_height}")
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received, stopping...")
        self._running = False
        
    def detect_markers(self, frame: np.ndarray) -> Tuple[List[int], List[np.ndarray]]:
        """Detect ArUco markers in frame.
        
        Args:
            frame: Input frame (BGR format from USB camera)
            
        Returns:
            Tuple of (marker_ids, marker_corners)
        """
        # Convert BGR to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect markers
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )
        
        marker_ids = []
        marker_corners = []
        
        if ids is not None:
            marker_ids = ids.flatten().tolist()
            marker_corners = corners
            
        return marker_ids, marker_corners
        
    def draw_markers(self, frame: np.ndarray, ids: List[int], corners: List[np.ndarray]) -> np.ndarray:
        """Draw detected markers on frame.
        
        Args:
            frame: Input frame (BGR format from USB camera)
            ids: List of detected marker IDs
            corners: List of marker corner arrays
            
        Returns:
            Frame with markers drawn (BGR format)
        """
        if len(ids) == 0:
            return frame
            
        # Frame is already in BGR format for OpenCV drawing
        display_frame = frame.copy()
        
        # Draw marker boundaries and IDs
        cv2.aruco.drawDetectedMarkers(display_frame, corners, np.array(ids))
        
        # Draw ID text with background
        for i, (marker_id, corner) in enumerate(zip(ids, corners)):
            # Get center of marker
            center = corner[0].mean(axis=0).astype(int)
            
            # Draw text background
            text = f"ID: {marker_id}"
            font_scale = 0.7
            thickness = 2
            (text_w, text_h), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            
            # Background rectangle
            cv2.rectangle(display_frame, 
                         (center[0] - text_w//2 - 5, center[1] - text_h - 10),
                         (center[0] + text_w//2 + 5, center[1] + baseline),
                         (0, 0, 0), -1)
            
            # White text
            cv2.putText(display_frame, text,
                       (center[0] - text_w//2, center[1] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
                       
        return display_frame
        
    def run_detection(self) -> None:
        """Run live ArUco detection."""
        try:
            logger.info("Starting ArUco detection...")
            
            if not self.camera.is_available():
                logger.error("Camera not available")
                return
                
            self.camera.start()
            
            if self.display:
                cv2.namedWindow("ArUco Detection", cv2.WINDOW_AUTOSIZE)
                logger.info("Press 'q' or Ctrl+C to quit")
                
            frame_count = 0
            start_time = time.time()
            
            while self._running:
                try:
                    # Capture frame
                    frame, timestamp = self.camera.capture_frame()
                    
                    # Detect markers
                    marker_ids, marker_corners = self.detect_markers(frame)
                    
                    # Print detected IDs
                    if marker_ids:
                        print(f"Frame {frame_count}: ArUco IDs detected: {marker_ids}")
                    else:
                        print(f"Frame {frame_count}: No ArUco markers detected")
                        
                    # Display if requested
                    if self.display:
                        display_frame = self.draw_markers(frame, marker_ids, marker_corners)
                        
                        # Add FPS info
                        fps = frame_count / (time.time() - start_time + 0.001)
                        cv2.putText(display_frame, f"FPS: {fps:.1f} | Dict: {self.dict_name}",
                                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        
                        cv2.imshow("ArUco Detection", display_frame)
                        
                        # Handle window events
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q') or key == 27:  # 'q' or ESC
                            break
                            
                    frame_count += 1
                    
                    # Small delay to prevent overwhelming the system
                    time.sleep(0.01)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error in detection loop: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"ArUco detection failed: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.camera:
                self.camera.stop()
            if self.display:
                cv2.destroyAllWindows()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
        logger.info("ArUco detection stopped")

def parse_resolution(resolution_str: str) -> Tuple[int, int]:
    """Parse resolution string like '1280x720' to (width, height)."""
    try:
        width, height = map(int, resolution_str.split('x'))
        return width, height
    except ValueError:
        raise ValueError(f"Invalid resolution format: {resolution_str}. Use WIDTHxHEIGHT (e.g., 1280x720)")

def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description="ArUco marker detection test for BevBot")
    parser.add_argument("--dict", default="DICT_4X4_50", 
                       choices=list(ARUCO_DICTS.keys()),
                       help="ArUco dictionary to use (default: DICT_4X4_50)")
    parser.add_argument("--camera-res", default="1920x1080",
                       help="Camera resolution as WIDTHxHEIGHT (default: 1920x1080)")
    parser.add_argument("--no-display", action="store_true",
                       help="Run headless without display window")
    
    args = parser.parse_args()
    
    try:
        # Parse resolution
        width, height = parse_resolution(args.camera_res)
        
        # Create detector
        detector = ArucoDetector(
            dict_name=args.dict,
            camera_width=width,
            camera_height=height,
            display=not args.no_display
        )
        
        # Run detection
        detector.run_detection()
        
    except Exception as e:
        logger.error(f"ArUco test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()