#!/bin/bash
# Test BevBot AI Vision features

cd "$(dirname "$0")/.." || exit 1

echo "==================================="
echo "   BevBot AI Vision Test Suite"
echo "==================================="
echo ""

# Check for requests library
python3 -c "import requests" 2>/dev/null || {
    echo "Error: requests library not installed"
    echo "Install with: pip3 install requests"
    exit 1
}

# Run the test
python3 scripts/test_ai_vision.py