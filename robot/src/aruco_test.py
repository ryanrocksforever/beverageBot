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
            
        # Use newer OpenCV ArUco API (4.7+) with fallback to older API
        try:
            # New API (OpenCV 4.7+)
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTS[dict_name])
            self.aruco_params = cv2.aruco.DetectorParameters()
        except AttributeError:
            # Fallback to older API
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
        
        # Detect markers - try new API first, fallback to old
        try:
            # New API (OpenCV 4.7+)
            detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
            corners, ids, rejected = detector.detectMarkers(gray)
        except AttributeError:
            # Fallback to older API
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
        if len(corners) > 0:
            cv2.aruco.drawDetectedMarkers(display_frame, corners, np.array(ids))
        
        # BevBot location mapping
        location_map = {
            1: "Home Base",
            2: "Fridge Side", 
            3: "Fridge Pickup",
            4: "Couch",
            5: "Outside"
        }
        
        # Draw enhanced marker information
        for i, (marker_id, corner) in enumerate(zip(ids, corners)):
            # Get center and corners of marker
            center = corner[0].mean(axis=0).astype(int)
            corner_points = corner[0].astype(int)
            
            # Calculate marker size (distance between opposite corners)
            marker_size = np.linalg.norm(corner_points[0] - corner_points[2])
            
            # Get location name
            location = location_map.get(marker_id, "Unknown")
            
            # Create info text
            info_lines = [
                f"ID: {marker_id}",
                f"Location: {location}",
                f"Size: {marker_size:.1f}px"
            ]
            
            # Draw info box with background
            font_scale = 0.6
            thickness = 2
            line_height = 20
            box_padding = 5
            
            # Calculate text dimensions
            max_width = 0
            for line in info_lines:
                (text_w, text_h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                max_width = max(max_width, text_w)
            
            box_height = len(info_lines) * line_height + box_padding * 2
            box_width = max_width + box_padding * 2
            
            # Position info box (offset from marker center)
            box_x = center[0] + 30
            box_y = center[1] - box_height // 2
            
            # Keep box within frame bounds
            box_x = max(5, min(box_x, display_frame.shape[1] - box_width - 5))
            box_y = max(5, min(box_y, display_frame.shape[0] - box_height - 5))
            
            # Draw semi-transparent background
            overlay = display_frame.copy()
            cv2.rectangle(overlay, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
            
            # Draw border
            cv2.rectangle(display_frame, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 255, 0), 2)
            
            # Draw text lines
            for j, line in enumerate(info_lines):
                text_y = box_y + box_padding + (j + 1) * line_height - 5
                cv2.putText(display_frame, line, (box_x + box_padding, text_y),
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
                           
            # Draw line from marker center to info box
            cv2.line(display_frame, tuple(center), (box_x, box_y + box_height // 2), (0, 255, 0), 2)
                       
        return display_frame
        
    def run_detection(self) -> None:
        """Run live ArUco detection."""
        try:
            logger.info("Starting ArUco detection...")
            
            if not self.camera.is_available():
                logger.error("Camera not available. Try running: ./scripts/debug_camera.sh")
                return
                
            logger.info("Camera is available, starting...")
            self.camera.start()
            
            if self.display:
                try:
                    # Try to create window with error handling
                    cv2.namedWindow("BevBot ArUco Detection", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow("BevBot ArUco Detection", 1280, 720)
                    logger.info("Live view controls:")
                    logger.info("  'q' or ESC: Quit")
                    logger.info("  'f': Toggle fullscreen")
                    logger.info("  's': Save current frame")
                except Exception as e:
                    logger.error(f"Cannot create display window: {e}")
                    logger.info("Falling back to headless mode")
                    self.display = False
                
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
                        try:
                            display_frame = self.draw_markers(frame, marker_ids, marker_corners)
                            
                            # Add status overlay
                            self._add_status_overlay(display_frame, frame_count, start_time, marker_ids)
                            
                            cv2.imshow("BevBot ArUco Detection", display_frame)
                            
                            # Handle window events
                            key = cv2.waitKey(1) & 0xFF
                            if key == ord('q') or key == 27:  # 'q' or ESC
                                break
                            elif key == ord('f'):  # Toggle fullscreen
                                try:
                                    if cv2.getWindowProperty("BevBot ArUco Detection", cv2.WND_PROP_FULLSCREEN) == cv2.WINDOW_FULLSCREEN:
                                        cv2.setWindowProperty("BevBot ArUco Detection", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                                    else:
                                        cv2.setWindowProperty("BevBot ArUco Detection", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                                except:
                                    pass  # Ignore fullscreen errors
                            elif key == ord('s'):  # Save frame
                                filename = f"aruco_frame_{int(time.time())}.jpg"
                                cv2.imwrite(filename, display_frame)
                                logger.info(f"Frame saved as {filename}")
                        except Exception as e:
                            logger.error(f"Display error: {e}")
                            logger.info("Disabling display, continuing in headless mode")
                            self.display = False
                            
                    frame_count += 1
                    
                    # Small delay to prevent overwhelming the system
                    time.sleep(0.01)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Error in detection loop: {e}")
                    logger.info("Try running: ./scripts/debug_camera.sh for diagnosis")
                    break
                    
        except Exception as e:
            logger.error(f"ArUco detection failed: {e}")
        finally:
            self.cleanup()
            
    def _add_status_overlay(self, frame: np.ndarray, frame_count: int, start_time: float, marker_ids: List[int]) -> None:
        """Add status information overlay to frame."""
        # Calculate FPS
        fps = frame_count / (time.time() - start_time + 0.001)
        
        # Get camera info
        actual_width, actual_height = self.camera.get_actual_resolution()
        camera_fps = self.camera.get_fps()
        
        # Status information
        status_lines = [
            f"FPS: {fps:.1f} (Camera: {camera_fps:.0f})",
            f"Resolution: {actual_width}x{actual_height}",
            f"Dictionary: {self.dict_name}",
            f"Frame: {frame_count}",
            f"Markers: {len(marker_ids)} detected"
        ]
        
        if marker_ids:
            status_lines.append(f"IDs: {marker_ids}")
        
        # Draw status box
        font_scale = 0.5
        thickness = 1
        line_height = 18
        box_padding = 8
        
        # Calculate box dimensions
        max_width = 0
        for line in status_lines:
            (text_w, text_h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            max_width = max(max_width, text_w)
        
        box_height = len(status_lines) * line_height + box_padding * 2
        box_width = max_width + box_padding * 2
        
        # Position at top-left
        box_x, box_y = 10, 10
        
        # Draw semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Draw border
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_width, box_y + box_height), (0, 255, 0), 1)
        
        # Draw status text
        for i, line in enumerate(status_lines):
            text_y = box_y + box_padding + (i + 1) * line_height - 3
            cv2.putText(frame, line, (box_x + box_padding, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
        
        # Add controls info at bottom
        controls = ["Controls: Q=Quit  F=Fullscreen  S=Save"]
        for i, line in enumerate(controls):
            text_y = frame.shape[0] - 20 - i * 20
            cv2.putText(frame, line, (10, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
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