"""Camera interface using OpenCV for USB cameras on BevBot."""

import time
import logging
from typing import Generator, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Install with: pip install opencv-python")

class CameraInterface:
    """USB Camera interface using OpenCV."""
    
    def __init__(self, width: int = 1920, height: int = 1080, camera_index: int = 0):
        """Initialize USB camera interface.
        
        Args:
            width: Frame width in pixels (default 1920 for 1080p)
            height: Frame height in pixels (default 1080 for 1080p)
            camera_index: USB camera index (usually 0 for first camera)
        """
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV not available. Install with: pip install opencv-python")
            
        self.width = width
        self.height = height
        self.camera_index = camera_index
        self._camera: Optional[cv2.VideoCapture] = None
        self._is_running = False
        
    def start(self) -> None:
        """Start the USB camera and configure it."""
        if self._camera is not None:
            logger.warning("Camera already started")
            return
            
        try:
            self._camera = cv2.VideoCapture(self.camera_index)
            
            if not self._camera.isOpened():
                raise RuntimeError(f"Cannot open USB camera at index {self.camera_index}")
            
            # Configure camera resolution
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # Set additional properties for better quality
            self._camera.set(cv2.CAP_PROP_FPS, 30)
            self._camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            
            # Verify actual resolution
            actual_width = int(self._camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"USB camera started at {actual_width}x{actual_height} (requested {self.width}x{self.height})")
            
            # Allow camera to warm up
            time.sleep(1.0)
            self._is_running = True
            logger.info("USB camera warmed up and ready")
            
        except Exception as e:
            logger.error(f"Failed to start USB camera: {e}")
            self._cleanup()
            raise
            
    def stop(self) -> None:
        """Stop the camera."""
        if self._camera is not None:
            logger.info("Stopping camera")
            self._cleanup()
            
    def _cleanup(self) -> None:
        """Clean up camera resources."""
        try:
            if self._camera is not None:
                self._camera.release()
        except Exception as e:
            logger.error(f"Error during camera cleanup: {e}")
        finally:
            self._camera = None
            self._is_running = False
            
    def capture_frame(self) -> Tuple[np.ndarray, float]:
        """Capture a single frame.
        
        Returns:
            Tuple of (frame_array, timestamp) - frame in BGR format
        """
        if not self._is_running or self._camera is None:
            raise RuntimeError("Camera not started")
            
        ret, frame = self._camera.read()
        timestamp = time.time()
        
        if not ret or frame is None:
            raise RuntimeError("Failed to capture frame from USB camera")
            
        return frame, timestamp
        
    def capture_stream(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        """Continuous frame capture generator.
        
        Yields:
            Tuple of (frame_array, timestamp)
        """
        if not self._is_running:
            self.start()
            
        try:
            while self._is_running:
                yield self.capture_frame()
        except KeyboardInterrupt:
            logger.info("Camera stream interrupted")
        finally:
            self.stop()
            
    def get_frame_shape(self) -> Tuple[int, int, int]:
        """Get expected frame shape (height, width, channels)."""
        return (self.height, self.width, 3)
        
    def get_actual_resolution(self) -> Tuple[int, int]:
        """Get actual camera resolution if running."""
        if self._camera is not None and self._is_running:
            actual_width = int(self._camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return (actual_width, actual_height)
        return (self.width, self.height)
        
    def get_fps(self) -> float:
        """Get camera FPS setting."""
        if self._camera is not None and self._is_running:
            return self._camera.get(cv2.CAP_PROP_FPS)
        return 30.0
        
    def is_available(self) -> bool:
        """Check if USB camera hardware is available."""
        try:
            if not CV2_AVAILABLE:
                return False
            test_cam = cv2.VideoCapture(self.camera_index)
            is_available = test_cam.isOpened()
            test_cam.release()
            return is_available
        except Exception:
            return False
            
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()