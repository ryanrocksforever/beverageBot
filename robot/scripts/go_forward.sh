#!/bin/bash
# Simple script to drive BevBot forward - verify motor directions
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Default values
SPEED=30
DURATION=0
TEST_MODE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --speed)
            SPEED="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --test)
            TEST_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --speed PERCENT     Motor speed 0-100 (default: 30)"
            echo "  --duration SECONDS  Duration in seconds, 0=continuous (default: 0)"
            echo "  --test              Run direction test sequence"
            echo ""
            echo "Examples:"
            echo "  $0                           # Drive forward at 30% continuously"
            echo "  $0 --speed 50                # Drive forward at 50% continuously"
            echo "  $0 --duration 5              # Drive forward for 5 seconds"
            echo "  $0 --test                    # Run direction verification test"
            echo ""
            echo "Direction test sequence:"
            echo "  1. Left motor only (3s)"
            echo "  2. Right motor only (3s)"
            echo "  3. Both motors forward (3s)"
            echo "  4. Turn left (3s)"
            echo "  5. Turn right (3s)"
            echo "  6. Reverse (3s)"
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

echo ""
if [ "$TEST_MODE" = true ]; then
    echo "Starting motor direction test sequence..."
    python3 -m src.go_forward --test
else
    echo "Starting forward drive test..."
    echo "Speed: $SPEED%"
    if [ "$DURATION" = "0" ]; then
        echo "Duration: Continuous (press Ctrl+C to stop)"
    else
        echo "Duration: $DURATION seconds"
    fi
    echo ""
    python3 -m src.go_forward --speed "$SPEED" --duration "$DURATION"
fi