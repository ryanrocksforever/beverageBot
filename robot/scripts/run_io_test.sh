
#!/bin/bash
# Run BevBot hardware IO test

cd "$(dirname "$0")/.."

echo "=== BevBot Hardware IO Test ==="
echo "This will test motors, actuator, camera, and GPIO"
echo "Press Ctrl+C to stop at any time"
echo "Hold the button (GPIO17) during motor tests to skip them for safety"
echo ""

# Check if pigpiod is running
if ! pgrep pigpiod > /dev/null; then
    echo "⚠ Warning: pigpiod not running. Starting it..."
    sudo systemctl start pigpiod
    sleep 1
fi

# Check pigpiod connection
if ! python3 -c "import pigpio; pi = pigpio.pi(); exit(0 if pi.connected else 1); pi.stop()" 2>/dev/null; then
    echo "❌ Cannot connect to pigpiod"
    echo "Try: sudo systemctl restart pigpiod"
    exit 1
fi

echo "✓ pigpiod connection OK"
echo ""

# Run the IO test
export PYTHONPATH="$(pwd):$PYTHONPATH"
python3 -m src.io_test