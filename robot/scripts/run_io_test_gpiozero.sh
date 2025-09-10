#!/bin/bash
# Run the gpiozero-based hardware IO test for BevBot
# Compatible with Raspberry Pi 5

# Ensure we're in the robot directory
cd "$(dirname "$0")/.." || exit 1

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "Running on: $(cat /proc/device-tree/model)"
else
    echo "Warning: Not running on Raspberry Pi - some tests may not work"
fi

# Run the gpiozero IO test
echo "Starting BevBot IO test with gpiozero (Raspberry Pi 5 compatible)..."
python3 -m src.io_test_gpiozero "$@"