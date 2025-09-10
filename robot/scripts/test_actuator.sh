#!/bin/bash
# Test linear actuator with gpiozero
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Default values
MODE="full"
SPEED=50
EXTEND_TIME=10
RETRACT_TIME=10
CYCLES=3

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --speed)
            SPEED="$2"
            shift 2
            ;;
        --extend-time)
            EXTEND_TIME="$2"
            shift 2
            ;;
        --retract-time)
            RETRACT_TIME="$2"
            shift 2
            ;;
        --cycles)
            CYCLES="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --mode MODE         Test mode: full, cycle, or manual (default: full)"
            echo "  --speed PERCENT     Actuator speed 0-100 (default: 50)"
            echo "  --extend-time SEC   Extension time for full test (default: 10)"
            echo "  --retract-time SEC  Retraction time for full test (default: 10)"
            echo "  --cycles NUM        Number of cycles for cycle test (default: 3)"
            echo ""
            echo "Test modes:"
            echo "  full   - Extend fully, then retract fully"
            echo "  cycle  - Perform multiple extend/retract cycles"
            echo "  manual - Manual control with interactive commands"
            echo ""
            echo "Examples:"
            echo "  $0                                  # Full extension test at 50%"
            echo "  $0 --mode full --speed 75           # Full test at 75% speed"
            echo "  $0 --mode cycle --cycles 5          # 5 cycles at 50%"
            echo "  $0 --mode manual                    # Interactive control"
            echo "  $0 --extend-time 15 --retract-time 15  # Longer extension times"
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
echo "Starting actuator test..."
echo "Mode: $MODE"

case $MODE in
    full)
        echo "Speed: $SPEED%"
        echo "Extension time: ${EXTEND_TIME}s"
        echo "Retraction time: ${RETRACT_TIME}s"
        echo "Press Ctrl+C to stop"
        python3 -m src.test_actuator --mode "$MODE" --speed "$SPEED" \
            --extend-time "$EXTEND_TIME" --retract-time "$RETRACT_TIME"
        ;;
    cycle)
        echo "Speed: $SPEED%"
        echo "Cycles: $CYCLES"
        echo "Press Ctrl+C to stop"
        python3 -m src.test_actuator --mode "$MODE" --speed "$SPEED" --cycles "$CYCLES"
        ;;
    manual)
        echo "Entering manual control mode..."
        python3 -m src.test_actuator --mode "$MODE"
        ;;
    *)
        echo "Invalid mode: $MODE"
        exit 1
        ;;
esac