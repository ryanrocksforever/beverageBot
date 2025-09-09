#!/usr/bin/env python3
"""Camera debugging utility for BevBot."""

import cv2
import logging
import sys
from .camera import CameraInterface

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_opencv_backends():
    """Test different OpenCV backends."""
    backends = [
        (cv2.CAP_V4L2, "V4L2"),
        (cv2.CAP_ANY, "ANY"),
        (cv2.CAP_GSTREAMER, "GStreamer"),
        (cv2.CAP_FFMPEG, "FFmpeg")
    ]
    
    print("Testing OpenCV backends:")
    print("=" * 40)
    
    for backend_id, backend_name in backends:
        try:
            cap = cv2.VideoCapture(0, backend_id)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    height, width = frame.shape[:2]
                    print(f"✓ {backend_name}: OK ({width}x{height})")
                else:
                    print(f"⚠ {backend_name}: Opens but no frame")
                cap.release()
            else:
                print(f"❌ {backend_name}: Cannot open")
        except Exception as e:
            print(f"❌ {backend_name}: Error - {e}")

def list_all_cameras():
    """List all available cameras."""
    print("\nScanning for cameras:")
    print("=" * 40)
    
    available = CameraInterface.list_cameras()
    if available:
        for device in available:
            print(f"✓ {device}")
    else:
        print("❌ No cameras found")
    
    return available

def test_camera_properties(camera_index=0):
    """Test camera properties and capabilities."""
    print(f"\nTesting camera {camera_index} properties:")
    print("=" * 40)
    
    try:
        cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(camera_index)
            
        if not cap.isOpened():
            print(f"❌ Cannot open camera {camera_index}")
            return
            
        # Test different resolutions
        resolutions = [
            (1920, 1080),
            (1280, 720),
            (640, 480),
            (320, 240)
        ]
        
        print("Testing resolutions:")
        for width, height in resolutions:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Try to capture a frame
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"  ✓ {width}x{height} -> {actual_width}x{actual_height}")
            else:
                print(f"  ❌ {width}x{height} -> No frame")
                
        # Test FPS
        fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"Camera FPS: {fps}")
        
        # Test codec
        fourcc = cap.get(cv2.CAP_PROP_FOURCC)
        fourcc_str = "".join([chr((int(fourcc) >> 8 * i) & 0xFF) for i in range(4)])
        print(f"Camera codec: {fourcc_str}")
        
        cap.release()
        
    except Exception as e:
        print(f"❌ Error testing camera: {e}")

def test_bevbot_camera_interface():
    """Test BevBot camera interface."""
    print("\nTesting BevBot camera interface:")
    print("=" * 40)
    
    try:
        # Test with different resolutions
        resolutions = [(1920, 1080), (1280, 720), (640, 480)]
        
        for width, height in resolutions:
            print(f"Testing {width}x{height}...")
            try:
                camera = CameraInterface(width, height)
                if camera.is_available():
                    camera.start()
                    frame, timestamp = camera.capture_frame()
                    actual_width, actual_height = camera.get_actual_resolution()
                    print(f"  ✓ Success: {actual_width}x{actual_height}, frame shape: {frame.shape}")
                    camera.stop()
                    return True
                else:
                    print(f"  ❌ Camera not available")
            except Exception as e:
                print(f"  ❌ Error: {e}")
                
        return False
        
    except Exception as e:
        print(f"❌ Interface test failed: {e}")
        return False

def main():
    """Main debugging function."""
    print("BevBot Camera Debug Tool")
    print("=" * 50)
    
    # Test OpenCV backends
    test_opencv_backends()
    
    # List cameras
    available = list_all_cameras()
    
    if not available:
        print("\n❌ No cameras detected. Check connections and permissions.")
        print("Try: sudo usermod -a -G video $USER")
        return 1
        
    # Test camera properties if any available
    if available:
        test_camera_properties(0)  # Test with default index
    
    # Test BevBot interface
    success = test_bevbot_camera_interface()
    
    if success:
        print("\n✓ Camera debugging completed successfully!")
        print("Your camera should work with the ArUco detection.")
    else:
        print("\n❌ Camera issues detected.")
        print("Try using a lower resolution or different camera.")
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())