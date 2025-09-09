#!/usr/bin/env python3
"""Simple camera test using the proven working approach."""

import cv2
import glob
import os

def test_simple_camera():
    """Test camera using the exact same approach as the working script."""
    print("Testing camera with proven approach...")
    
    # Prefer stable paths if available (exact copy of working script)
    devs = sorted(glob.glob("/dev/v4l/by-id/*")) or ["/dev/video0"]
    
    for dev in devs:
        try:
            path = os.path.realpath(dev)
            cap = cv2.VideoCapture(path, cv2.CAP_V4L2)
            if cap.isOpened():
                print(f"Opened {dev} -> {path}")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                
                # Test frame capture
                ok, frame = cap.read()
                if ok and frame is not None:
                    print(f"✓ Frame captured: {frame.shape}")
                    
                    # Show a few frames
                    frame_count = 0
                    while frame_count < 100:  # Show 100 frames
                        ok, frame = cap.read()
                        if not ok: 
                            print("❌ Failed to read frame")
                            break
                            
                        cv2.imshow(f"Simple Test - {dev}", frame)
                        
                        key = cv2.waitKey(1) & 0xFF
                        if key == 27:  # ESC to quit
                            print("ESC pressed, quitting...")
                            break
                        elif key == ord('q'):
                            print("Q pressed, quitting...")
                            break
                            
                        frame_count += 1
                        
                    cap.release()
                    cv2.destroyAllWindows()
                    print(f"✓ Simple camera test completed successfully!")
                    return True
                else:
                    print(f"❌ Cannot capture frame from {dev}")
                    cap.release()
            else:
                print(f"❌ Cannot open {dev}")
        except Exception as e:
            print(f"❌ Error with {dev}: {e}")
    
    print("❌ No working cameras found")
    return False

if __name__ == "__main__":
    test_simple_camera()