"""Camera and ArUco marker configuration for BevBot.

This file contains calibration parameters for the Innomaker 1080P USB 2.0 
UVC Camera with 130° wide angle lens, and ArUco marker specifications.
"""

import numpy as np

# Camera specifications
CAMERA_NAME = "Innomaker 1080P USB 2.0 UVC Camera"
CAMERA_FOV_DEGREES = 130  # Field of view in degrees
CAMERA_RESOLUTION_NATIVE = (1920, 1080)  # Native resolution
CAMERA_RESOLUTION_CAPTURE = (640, 480)  # Actual capture resolution

# Calculate focal length for wide angle lens
# Formula: focal_length = (image_width / 2) / tan(FOV/2)
# For 130° FOV at 1920x1080: focal_length ≈ 448 pixels
# Scaled to 640x480: 448 * (640/1920) ≈ 149 pixels
FOCAL_LENGTH_PIXELS = 149

# Camera intrinsic matrix for 640x480 capture
# [fx  0  cx]
# [0  fy  cy]
# [0   0   1]
CAMERA_MATRIX = np.array([
    [FOCAL_LENGTH_PIXELS, 0, 320],  # cx = image_width / 2
    [0, FOCAL_LENGTH_PIXELS, 240],  # cy = image_height / 2
    [0, 0, 1]
], dtype=np.float32)

# Distortion coefficients for 130° wide angle lens
# [k1, k2, p1, p2, k3]
# k1, k2, k3: Radial distortion coefficients
# p1, p2: Tangential distortion coefficients
# Wide angle lenses typically have significant barrel distortion (negative k1)
DISTORTION_COEFFS = np.array([-0.3, 0.1, 0, 0, 0], dtype=np.float32)

# ArUco marker specifications
ARUCO_DICT_TYPE = "DICT_4X4_50"  # 4x4 grid, 50 unique markers
MARKER_SIZE_MM = 100  # Real-world marker size in millimeters
MARKER_SIZE_CM = MARKER_SIZE_MM / 10  # Convert to centimeters

# Navigation parameters
DEFAULT_TARGET_DISTANCE_CM = 30  # Default distance to maintain from markers
APPROACH_THRESHOLD = 0.7  # Switch to precision mode when marker size > 70% of target

# Precision alignment tolerances (in pixels)
TOLERANCE_X_PIXELS = 10  # Horizontal position tolerance
TOLERANCE_Y_PIXELS = 10  # Vertical position tolerance  
TOLERANCE_SIZE_PIXELS = 5  # Size tolerance for distance

# Control parameters
PID_GAINS = {
    'heading': {
        'kp': 0.15,  # Proportional gain
        'ki': 0.01,  # Integral gain
        'kd': 0.02   # Derivative gain
    },
    'distance': {
        'kp': 0.8,
        'ki': 0.05,
        'kd': 0.01
    }
}

# Speed limits
SPEED_LIMITS = {
    'max_linear': 40,  # Maximum forward/backward speed
    'max_turn': 30,    # Maximum turning speed
    'min_speed': 8,    # Minimum speed threshold
    'approach': 25,    # Speed during approach phase
    'search_turn': 15  # Speed when searching for markers
}

def get_focal_length_for_resolution(width, height):
    """Calculate focal length for a different resolution.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        
    Returns:
        Focal length in pixels for the given resolution
    """
    # Scale from native resolution
    scale = width / CAMERA_RESOLUTION_NATIVE[0]
    return 448 * scale  # 448 is focal length at 1920x1080

def get_camera_matrix_for_resolution(width, height):
    """Get camera matrix for a specific resolution.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        
    Returns:
        3x3 camera intrinsic matrix
    """
    focal_length = get_focal_length_for_resolution(width, height)
    return np.array([
        [focal_length, 0, width / 2],
        [0, focal_length, height / 2],
        [0, 0, 1]
    ], dtype=np.float32)