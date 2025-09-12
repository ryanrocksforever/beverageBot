#!/bin/bash
# Quick alignment test script for Raspberry Pi 5

echo "BevBot Quick Alignment Test"
echo "=========================="

# Check if running on Pi
if [ -f /proc/device-tree/model ]; then
    echo "Running on: $(cat /proc/device-tree/model | tr -d '\0')"
else
    echo "Warning: Not running on Raspberry Pi"
fi

# Test hardware first
if [ "$1" = "test" ]; then
    echo "Running hardware test..."
    python3 test_hardware_pi5.py
    exit $?
fi

# Simple alignment test
if [ "$1" = "simple" ]; then
    echo "Running simple alignment..."
    echo "Usage: python3 src/align_marker_simple.py <marker_id> [options]"
    echo ""
    echo "Examples:"
    echo "  Align to marker 1 at 30cm:"
    echo "    python3 src/align_marker_simple.py 1 -d 30"
    echo ""
    echo "  Save current position:"
    echo "    python3 src/align_marker_simple.py 1 --save"
    echo ""
    echo "  Load and align to saved position:"
    echo "    python3 src/align_marker_simple.py 1 --load"
    echo ""
    shift
    python3 src/align_marker_simple.py "$@"
    exit $?
fi

# GUI mode
if [ "$1" = "gui" ]; then
    echo "Launching GUI alignment tool..."
    python3 launch_aligner.py
    exit $?
fi

# New simple GUI
if [ "$1" = "simplegui" ]; then
    echo "Launching Simple Alignment GUI..."
    python3 align_gui.py
    exit $?
fi

# Default - show options
echo ""
echo "Usage: ./quick_align.sh [command]"
echo ""
echo "Commands:"
echo "  test       - Run hardware diagnostics"
echo "  simple     - Run simple command-line alignment"
echo "  gui        - Launch full GUI alignment tool (complex)"
echo "  simplegui  - Launch simple GUI (recommended)"
echo ""
echo "Quick test:"
echo "  ./quick_align.sh simplegui"
echo ""
echo "Or directly:"
echo "  python3 align_gui.py"
echo ""