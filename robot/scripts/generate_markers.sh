#!/bin/bash
# Generate BevBot ArUco markers and export to PDF

cd "$(dirname "$0")/.."

echo "=== BevBot ArUco Marker Generator ==="
echo "This will generate printable ArUco markers for BevBot locations"
echo ""

# Check dependencies
if ! python -c "import cv2, reportlab" 2>/dev/null; then
    echo "❌ Missing dependencies. Install with:"
    echo "pip3 install opencv-python reportlab"
    exit 1
fi

echo "✓ Dependencies available"
echo ""

# Show available options
echo "Available options:"
echo "  Default: DICT_4X4_50, 2-inch markers with borders"
echo "  Custom: --dict DICT_5X5_50 --marker-size 1.5 --no-border"
echo "  List locations: --list-locations"
echo ""

# Run the marker generator
export PYTHONPATH="$(pwd):$PYTHONPATH"
python -m src.generate_markers "$@"

# Check if PDF was generated
if [ -f "bevbot_markers.pdf" ]; then
    echo ""
    echo "✓ Markers generated successfully!"
    echo "📄 File: bevbot_markers.pdf"
    echo ""
    echo "Printing instructions:"
    echo "1. Print on standard 8.5\" x 11\" paper"
    echo "2. Use 100% scale (no fit-to-page)"
    echo "3. Cut along border lines"
    echo "4. Mount markers at corresponding robot locations"
fi