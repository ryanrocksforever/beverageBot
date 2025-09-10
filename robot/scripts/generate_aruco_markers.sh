#!/bin/bash
# Generate ArUco markers for printing

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Default settings
IDS="0,1,2,3,4,5"
SIZE=200
OUTPUT="aruco_markers.png"
SINGLE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ids)
            IDS="$2"
            shift 2
            ;;
        --size)
            SIZE="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --single)
            SINGLE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --ids IDS        Comma-separated marker IDs (default: 0,1,2,3,4,5)"
            echo "  --size PIXELS    Size of each marker in pixels (default: 200)"
            echo "  --output FILE    Output filename (default: aruco_markers.png)"
            echo "  --single         Generate individual marker files"
            echo ""
            echo "Examples:"
            echo "  $0                           # Generate sheet with markers 0-5"
            echo "  $0 --ids 0,1,2               # Generate markers 0, 1, and 2"
            echo "  $0 --single --ids 0          # Generate single marker 0"
            echo "  $0 --size 300                # Generate larger markers"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

echo "=== ArUco Marker Generator ==="
echo ""

# Check for OpenCV
python3 -c "import cv2" 2>/dev/null || {
    echo "Error: OpenCV not installed"
    echo "Install with: pip3 install opencv-python opencv-contrib-python"
    exit 1
}

# Run generator
if [ "$SINGLE" = true ]; then
    echo "Generating individual markers for IDs: $IDS"
    python3 scripts/generate_aruco_markers.py --ids "$IDS" --size "$SIZE" --single
else
    echo "Generating marker sheet for IDs: $IDS"
    echo "Output: $OUTPUT"
    python3 scripts/generate_aruco_markers.py --ids "$IDS" --size "$SIZE" --output "$OUTPUT"
fi

echo ""
echo "Done! Markers generated successfully."
echo ""
echo "For best results when printing:"
echo "- Print at 100% scale (no fit-to-page)"
echo "- Use white paper with good contrast"
echo "- Mount on rigid flat surface"
echo "- Recommended real-world size: 10cm x 10cm"