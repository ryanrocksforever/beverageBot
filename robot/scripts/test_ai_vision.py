#!/usr/bin/env python3
"""Test script for AI Vision features."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np
import json
from src.openai_vision import OpenAIVision, VisionAnalysis

def test_api_key():
    """Test if API key is configured."""
    print("Testing OpenAI API key configuration...")
    try:
        vision = OpenAIVision()
        print("✓ API key loaded successfully")
        return vision
    except ValueError as e:
        print(f"✗ API key error: {e}")
        print("\nPlease configure your OpenAI API key:")
        print("1. Set environment variable: export OPENAI_API_KEY='sk-...'")
        print("2. Or create robot/config/openai_config.json from the example file")
        return None

def test_image_encoding(vision):
    """Test image encoding."""
    print("\nTesting image encoding...")
    # Create a test image
    test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(test_image, "TEST IMAGE", (200, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)

    try:
        encoded = vision.encode_image(test_image)
        print(f"✓ Image encoded successfully (length: {len(encoded)} chars)")
        return test_image
    except Exception as e:
        print(f"✗ Encoding failed: {e}")
        return None

def test_human_detection(vision, image):
    """Test human detection on a single image."""
    print("\nTesting human detection API...")
    try:
        print("Sending image to GPT-4o mini for analysis...")
        analysis = vision.find_human(image)

        print("\n=== Analysis Results ===")
        print(f"Human detected: {analysis.human_detected}")
        print(f"Direction: {analysis.human_direction}")
        print(f"Distance: {analysis.human_distance}")
        print(f"Recommended action: {analysis.recommended_action}")
        print(f"Confidence: {analysis.confidence:.1%}")
        print(f"Description: {analysis.description}")

        print("\n✓ Human detection API working")
        return True
    except Exception as e:
        print(f"✗ API call failed: {e}")
        return False

def test_surroundings_analysis(vision):
    """Test surroundings analysis with multiple images."""
    print("\nTesting surroundings analysis...")

    # Create multiple test images
    images = []
    for i in range(4):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(img, f"VIEW {i+1}", (250, 240),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        images.append(img)

    try:
        print(f"Sending {len(images)} images to GPT-4o mini...")
        results = vision.analyze_surroundings(images, "Test environment scan")

        print("\n=== Surroundings Analysis ===")
        print(f"Environment: {results.get('environment_description', 'N/A')}")
        print(f"Objects detected: {results.get('objects', [])}")
        print(f"Obstacles: {results.get('obstacles', [])}")
        print(f"Humans detected: {results.get('humans_detected', False)}")
        print(f"Navigation suggestions: {results.get('navigation_suggestions', 'N/A')}")

        print("\n✓ Surroundings analysis working")
        return True
    except Exception as e:
        print(f"✗ Analysis failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("BevBot AI Vision Test Suite")
    print("=" * 60)

    # Test API key
    vision = test_api_key()
    if not vision:
        print("\n❌ Tests cannot continue without valid API key")
        return 1

    # Test image encoding
    test_image = test_image_encoding(vision)
    if not test_image:
        print("\n❌ Image encoding failed")
        return 1

    # Test human detection
    if not test_human_detection(vision, test_image):
        print("\n⚠️  Human detection test failed - check API key and internet connection")

    # Test surroundings analysis
    if not test_surroundings_analysis(vision):
        print("\n⚠️  Surroundings analysis test failed")

    print("\n" + "=" * 60)
    print("✅ AI Vision tests completed!")
    print("\nTo use in the GUI:")
    print("1. Run: ./scripts/remote_control.sh")
    print("2. Navigate to the 'AI Vision' tab")
    print("3. Click '360° Surroundings Scan' or 'Navigate to Closest Human'")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())