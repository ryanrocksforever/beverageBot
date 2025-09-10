#!/bin/bash
# Test right motor continuously with gpiozero
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Default values
SPEED=30
DIRECTION="forward"
MODE="simple"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --speed)
            SPEED="$2"
            shift 2
            ;;
        --direction)
            DIRECTION="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --speed PERCENT     Motor speed 0-100 (default: 30)"
            echo "  --direction DIR     forward or reverse (default: forward)"
            echo "  --mode MODE         simple or cycle (default: simple)"
            echo ""
            echo "Examples:"
            echo "  $0                           # Run at 30% forward"
            echo "  $0 --speed 50                # Run at 50% forward"
            echo "  $0 --direction reverse       # Run at 30% reverse"
            echo "  $0 --mode cycle              # Cycle through speeds"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "Running on: $(cat /proc/device-tree/model)"
else
    echo "Warning: Not running on Raspberry Pi - test may not work"
fi

echo "Starting right motor test..."
echo "Mode: $MODE"
if [ "$MODE" = "simple" ]; then
    echo "Speed: $SPEED%"
    echo "Direction: $DIRECTION"
fi
echo "Press Ctrl+C to stop"
echo ""

# Run the test
python3 -m src.test_right_motor --speed "$SPEED" --direction "$DIRECTION" --mode "$MODE"