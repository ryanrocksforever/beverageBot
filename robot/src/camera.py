"""Camera interface using OpenCV for USB cameras on BevBot."""

import time
import logging
from typing import Generator, Tuple, Optional, List
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
        self._device_path = None
        
    def start(self) -> None:
        """Start the USB camera and configure it."""
        if self._camera is not None:
            logger.warning("Camera already started")
            return
            
        try:
            import glob
            import os
            
            # Try stable device paths first (like the working script)
            device_paths = []
            
            # Prefer stable paths if available
            stable_devs = sorted(glob.glob("/dev/v4l/by-id/*"))
            if stable_devs:
                for dev in stable_devs:
                    try:
                        path = os.path.realpath(dev)
                        device_paths.append(path)
                    except:
                        continue
            
            # Fallback to standard video devices
            for i in range(self.camera_index, self.camera_index + 3):
                device_paths.append(f"/dev/video{i}")
                
            # Also try the index directly as last resort
            device_paths.append(self.camera_index)
            
            self._camera = None
            working_path = None
            
            for dev_path in device_paths:
                try:
                    logger.info(f"Trying camera path: {dev_path}")
                    
                    # Use V4L2 backend specifically (like working script)
                    if isinstance(dev_path, str):
                        test_camera = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
                    else:
                        test_camera = cv2.VideoCapture(dev_path, cv2.CAP_V4L2)
                        
                    if test_camera.isOpened():
                        # Test if we can actually read a frame
                        ret, test_frame = test_camera.read()
                        if ret and test_frame is not None and test_frame.size > 0:
                            self._camera = test_camera
                            working_path = dev_path
                            logger.info(f"Successfully opened camera: {dev_path}")
                            break
                        else:
                            test_camera.release()
                            logger.warning(f"Camera {dev_path} opened but no frames")
                    else:
                        test_camera.release()
                        logger.warning(f"Cannot open camera: {dev_path}")
                        
                except Exception as e:
                    logger.warning(f"Error with camera {dev_path}: {e}")
                    
            if self._camera is None:
                raise RuntimeError("Cannot open any USB camera device")
                
            self._device_path = working_path
            
            # Configure camera resolution (like working script)
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # Get actual resolution
            actual_width = int(self._camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"Camera started: {working_path}")
            logger.info(f"Resolution: {actual_width}x{actual_height} (requested {self.width}x{self.height})")
            
            # Quick warmup
            time.sleep(0.5)
            self._is_running = True
            logger.info("USB camera ready")
            
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
            
        # Simple frame capture like working script
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
                
            import glob
            import os
            
            # Check stable paths first (like working script)
            stable_devs = sorted(glob.glob("/dev/v4l/by-id/*"))
            if stable_devs:
                for dev in stable_devs[:1]:  # Just check first one
                    try:
                        path = os.path.realpath(dev)
                        test_cam = cv2.VideoCapture(path, cv2.CAP_V4L2)
                        if test_cam.isOpened():
                            ret, frame = test_cam.read()
                            test_cam.release()
                            if ret and frame is not None:
                                return True
                        test_cam.release()
                    except:
                        continue
                        
            # Fallback to index-based check
            test_cam = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            if test_cam.isOpened():
                ret, frame = test_cam.read()
                test_cam.release()
                return ret and frame is not None
            test_cam.release()
            return False
            
        except Exception:
            return False
            
    @staticmethod
    def list_cameras() -> List[str]:
        """List available camera devices."""
        import glob
        import os
        
        available = []
        
        # List stable device paths
        stable_devs = sorted(glob.glob("/dev/v4l/by-id/*"))
        for dev in stable_devs:
            try:
                path = os.path.realpath(dev)
                cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        available.append(f"{dev} -> {path}")
                cap.release()
            except Exception:
                continue
                
        # Also check standard video devices
        for i in range(5):
            try:
                path = f"/dev/video{i}"
                cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        available.append(path)
                cap.release()
            except Exception:
                continue
                
        return available
            
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()