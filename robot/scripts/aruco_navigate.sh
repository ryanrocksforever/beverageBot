#!/bin/bash
# ArUco marker navigation system
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "Running on: $(cat /proc/device-tree/model)"
else
    echo "Warning: Not running on Raspberry Pi - running in simulation mode"
fi

echo ""
echo "=== BevBot ArUco Navigation System ==="
echo ""
echo "This system allows precise navigation between ArUco markers."
echo "First calibrate positions, then navigate between them."
echo ""

# Default mode
MODE=""
MARKERS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --calibrate|-c)
            MODE="calibrate"
            shift
            ;;
        --navigate|-n)
            MODE="navigate"
            shift
            MARKERS="$@"
            break
            ;;
        --save|-s)
            MODE="save"
            MARKER_ID="$2"
            shift 2
            ;;
        --list|-l)
            MODE="list"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --calibrate, -c         Enter interactive calibration mode"
            echo "  --navigate, -n ID...    Navigate to markers in sequence"
            echo "  --save, -s ID           Save current position for marker ID"
            echo "  --list, -l              List all saved positions"
            echo ""
            echo "Examples:"
            echo "  $0 --calibrate                  # Interactive calibration"
            echo "  $0 --save 5                      # Save position for marker 5"
            echo "  $0 --navigate 1 2 3              # Navigate to markers 1, 2, 3"
            echo "  $0 --list                        # Show saved positions"
            echo ""
            echo "Calibration Process:"
            echo "1. Place an ArUco marker where you want the robot to stop"
            echo "2. Manually position the robot exactly where it should be"
            echo "3. Run: $0 --calibrate"
            echo "4. Select option 1 to save the current position"
            echo "5. Repeat for all marker positions"
            echo ""
            echo "The robot will then be able to navigate to these exact positions!"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check for required packages
python3 -c "import cv2" 2>/dev/null || {
    echo "Error: OpenCV not installed"
    echo "Install with: pip3 install opencv-python opencv-contrib-python"
    exit 1
}

# Run the appropriate mode
case $MODE in
    calibrate)
        echo "Starting calibration mode..."
        echo "Position the robot at each marker location and save the position."
        echo ""
        python3 -m src.aruco_navigation --calibrate
        ;;
    navigate)
        if [ -z "$MARKERS" ]; then
            echo "Error: No marker IDs specified"
            echo "Usage: $0 --navigate ID1 ID2 ID3..."
            exit 1
        fi
        echo "Navigating to markers: $MARKERS"
        python3 -m src.aruco_navigation --navigate $MARKERS
        ;;
    save)
        echo "Saving current position for marker $MARKER_ID"
        python3 -m src.aruco_navigation --save $MARKER_ID
        ;;
    list)
        python3 -m src.aruco_navigation --list
        ;;
    *)
        echo "No mode specified. Use --help for options."
        echo ""
        echo "Quick start:"
        echo "  $0 --calibrate    # Set up marker positions"
        echo "  $0 --navigate 1 2 # Navigate between markers"
        exit 1
        ;;
esac