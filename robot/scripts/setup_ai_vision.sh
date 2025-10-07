#!/bin/bash
# Setup script for AI Vision features

cd "$(dirname "$0")/.." || exit 1

echo "======================================="
echo "  BevBot AI Vision Setup Script"
echo "======================================="
echo ""

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    echo "✓ Running on: $(cat /proc/device-tree/model)"
else
    echo "⚠ Not on Raspberry Pi - some features may be limited"
fi

echo ""
echo "Checking dependencies..."

# Check Python version
python3 --version

# Check for required libraries
echo ""
echo "Checking required Python packages..."

# Check OpenCV
python3 -c "import cv2; print('✓ OpenCV installed')" 2>/dev/null || {
    echo "✗ OpenCV not installed"
    echo "  Install with: sudo apt-get install python3-opencv"
    MISSING_DEPS=1
}

# Check numpy
python3 -c "import numpy; print('✓ NumPy installed')" 2>/dev/null || {
    echo "✗ NumPy not installed"
    echo "  Install with: pip3 install numpy"
    MISSING_DEPS=1
}

# Check Pillow
python3 -c "import PIL; print('✓ Pillow installed')" 2>/dev/null || {
    echo "✗ Pillow not installed"
    echo "  Install with: pip3 install Pillow"
    MISSING_DEPS=1
}

# Check requests
python3 -c "import requests; print('✓ requests installed')" 2>/dev/null || {
    echo "✗ requests not installed"
    echo "  Installing requests..."
    pip3 install requests || sudo pip3 install requests
}

echo ""
echo "Checking OpenAI API configuration..."

# Check for API key in environment
if [ -n "$OPENAI_API_KEY" ]; then
    echo "✓ OPENAI_API_KEY environment variable is set"
elif [ -f "config/openai_config.json" ]; then
    echo "✓ Config file exists: config/openai_config.json"
elif [ -f "$HOME/.bevbot/openai_config.json" ]; then
    echo "✓ Config file exists: ~/.bevbot/openai_config.json"
else
    echo "✗ OpenAI API key not configured"
    echo ""
    echo "To configure:"
    echo "1. Get an API key from https://platform.openai.com/"
    echo "2. Set it using one of these methods:"
    echo "   a) Export environment variable:"
    echo "      export OPENAI_API_KEY='sk-your-key-here'"
    echo "   b) Create config file:"
    echo "      cp config/openai_config.json.example config/openai_config.json"
    echo "      # Then edit the file and add your key"
    echo ""
    read -p "Would you like to set the API key now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your OpenAI API key (sk-...): " API_KEY
        if [ -n "$API_KEY" ]; then
            # Create config directory if it doesn't exist
            mkdir -p config
            # Create config file
            cat > config/openai_config.json <<EOF
{
  "api_key": "$API_KEY",
  "model": "gpt-4o-mini"
}
EOF
            echo "✓ API key saved to config/openai_config.json"
            echo "  (Remember to add this file to .gitignore!)"
        fi
    fi
fi

echo ""
echo "Testing AI Vision module..."
python3 -c "from src.openai_vision import OpenAIVision; print('✓ AI Vision module loads successfully')" 2>/dev/null || {
    echo "✗ Failed to load AI Vision module"
    echo "  Check that all dependencies are installed"
}

echo ""
echo "======================================="
if [ -z "$MISSING_DEPS" ]; then
    echo "✅ Setup complete! AI Vision is ready to use."
    echo ""
    echo "To test AI features:"
    echo "  python3 scripts/test_ai_vision.py"
    echo ""
    echo "To use in GUI:"
    echo "  ./scripts/remote_control.sh"
    echo "  Then navigate to the 'AI Vision' tab"
else
    echo "⚠ Some dependencies are missing. Please install them."
fi
echo "======================================="