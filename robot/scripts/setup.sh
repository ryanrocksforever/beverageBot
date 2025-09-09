#!/bin/bash
# BevBot setup script for Raspberry Pi 5

set -e  # Exit on any error

echo "=== BevBot Setup Script ==="
echo "Setting up dependencies and services for Raspberry Pi 5"

# Update system
echo "Updating system packages..."
sudo apt update

# Install system dependencies
echo "Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-dev \
    python3-opencv \
    pigpio \
    git \
    cmake \
    v4l-utils

# Install Python packages
echo "Installing Python packages..."
pip3 install --user \
    pigpio \
    opencv-python \
    numpy

# Enable and start pigpiod daemon
echo "Configuring pigpiod daemon..."
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Check pigpiod status
if sudo systemctl is-active --quiet pigpiod; then
    echo "✓ pigpiod daemon is running"
else
    echo "⚠ Warning: pigpiod daemon not running. Try: sudo systemctl restart pigpiod"
fi

# Set up USB camera permissions
echo "Setting up USB camera permissions..."
sudo usermod -a -G video $USER

# Create systemd service file for pigpiod with correct permissions
sudo tee /etc/systemd/system/pigpiod.service > /dev/null <<EOF
[Unit]
Description=Pigpio daemon
After=network.target

[Service]
Type=forking
User=root
ExecStart=/usr/bin/pigpiod -l
ExecStop=/bin/systemctl kill pigpiod
ExecReload=/bin/systemctl kill -HUP pigpiod
KillMode=control-group
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and restart pigpiod with new config
sudo systemctl daemon-reload
sudo systemctl restart pigpiod

# Test pigpiod connection
echo "Testing pigpiod connection..."
if python3 -c "import pigpio; pi = pigpio.pi(); print('pigpiod connection:', 'OK' if pi.connected else 'FAILED'); pi.stop()" 2>/dev/null; then
    echo "✓ pigpiod connection test passed"
else
    echo "⚠ Warning: pigpiod connection test failed"
    echo "Try: sudo systemctl restart pigpiod"
fi

# Test USB camera
echo "Testing USB camera availability..."
if python3 -c "import cv2; cam = cv2.VideoCapture(0); print('USB Camera:', 'OK' if cam.isOpened() else 'FAILED'); cam.release()" 2>/dev/null; then
    echo "✓ USB Camera test passed"
else
    echo "⚠ Warning: USB Camera test failed"
    echo "Make sure USB camera is connected. Check with: lsusb | grep -i camera"
    echo "List video devices with: v4l2-ctl --list-devices"
fi

# Make scripts executable
chmod +x $(dirname "$0")/run_io_test.sh
chmod +x $(dirname "$0")/run_aruco.sh

echo ""
echo "=== Setup Complete ==="
echo "✓ System packages installed"
echo "✓ Python dependencies installed" 
echo "✓ pigpiod daemon configured and started"
echo "✓ Camera permissions configured"
echo "✓ Scripts made executable"
echo ""
echo "You may need to reboot for all changes to take effect."
echo ""
echo "To test the setup:"
echo "  cd robot && ./scripts/run_io_test.sh"
echo "  cd robot && ./scripts/run_aruco.sh"
echo ""
echo "Note: You may need to log out and back in for group membership changes to take effect."