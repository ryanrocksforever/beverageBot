#!/bin/bash
# Beverage delivery demonstration using ArUco navigation
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "=== BevBot Beverage Delivery Demo ==="
echo ""
echo "This demo shows a complete beverage delivery workflow:"
echo "• Navigate to pickup station"
echo "• Deliver to multiple locations"
echo "• Return to home position"
echo ""

# Parse arguments
SETUP=false
CYCLES=1
CONTINUOUS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --setup)
            SETUP=true
            shift
            ;;
        --cycles)
            CYCLES="$2"
            shift 2
            ;;
        --continuous)
            CONTINUOUS=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --setup         Run setup wizard to configure marker positions"
            echo "  --cycles N      Run N delivery cycles (default: 1)"
            echo "  --continuous    Run continuously until stopped"
            echo ""
            echo "First Time Setup:"
            echo "1. Print ArUco markers 0-4"
            echo "2. Place markers at each station location"
            echo "3. Run: $0 --setup"
            echo "4. Follow the setup wizard instructions"
            echo ""
            echo "Running the Demo:"
            echo "  $0                    # Run one delivery cycle"
            echo "  $0 --cycles 5         # Run 5 delivery cycles"
            echo "  $0 --continuous       # Run until Ctrl+C"
            echo ""
            echo "Station Assignments:"
            echo "  Marker 0: Home position"
            echo "  Marker 1: Pickup station"
            echo "  Marker 2: Delivery point A"
            echo "  Marker 3: Delivery point B"
            echo "  Marker 4: Charging station (optional)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
            ;;
    esac
done

# Check for marker positions file
if [ ! -f "marker_positions.json" ] && [ "$SETUP" = false ]; then
    echo "No marker positions configured!"
    echo "Run with --setup first to configure positions."
    echo ""
    echo "Example: $0 --setup"
    exit 1
fi

# Run the demo
if [ "$SETUP" = true ]; then
    echo "Starting setup wizard..."
    echo "Have your ArUco markers ready (IDs 0-4)"
    echo ""
    python3 scripts/demo_beverage_delivery.py --setup
elif [ "$CONTINUOUS" = true ]; then
    echo "Starting continuous delivery mode..."
    echo "Press Ctrl+C to stop"
    echo ""
    python3 scripts/demo_beverage_delivery.py --continuous
else
    echo "Running $CYCLES delivery cycle(s)..."
    python3 scripts/demo_beverage_delivery.py --cycles $CYCLES
fi