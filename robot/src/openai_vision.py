#!/usr/bin/env python3
"""OpenAI Vision integration for BevBot using GPT-4o mini."""

import base64
import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import cv2
import numpy as np
from io import BytesIO
import time

try:
    import requests
except ImportError:
    raise ImportError("requests library is required for OpenAI Vision. Install with: pip install requests")

logger = logging.getLogger(__name__)

@dataclass
class VisionAnalysis:
    """Result of vision analysis from GPT-4o mini."""
    description: str
    objects_detected: List[str]
    human_detected: bool
    human_direction: Optional[str]  # 'left', 'right', 'center', 'none'
    human_distance: Optional[str]   # 'close', 'medium', 'far'
    recommended_action: Optional[str]
    confidence: float
    raw_response: str

class OpenAIVision:
    """Interface to OpenAI GPT-4o mini for vision tasks."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize OpenAI Vision interface.

        Args:
            api_key: OpenAI API key. If not provided, looks for OPENAI_API_KEY env variable.
        """
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            # Try to load from config file
            self._load_api_key_from_config()

        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable or provide it in config.")

        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o-mini"  # Using GPT-4o mini for cost efficiency
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _load_api_key_from_config(self):
        """Try to load API key from config file."""
        config_paths = [
            "config/openai_config.json",
            "../config/openai_config.json",
            "robot/config/openai_config.json",
            os.path.expanduser("~/.bevbot/openai_config.json")
        ]

        for path in config_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        config = json.load(f)
                        self.api_key = config.get('api_key')
                        if self.api_key:
                            logger.info(f"Loaded API key from {path}")
                            return
                except Exception as e:
                    logger.warning(f"Failed to load config from {path}: {e}")

    def encode_image(self, image: np.ndarray) -> str:
        """Encode OpenCV image to base64 string.

        Args:
            image: OpenCV image (numpy array)

        Returns:
            Base64 encoded image string
        """
        # Convert to JPEG
        success, buffer = cv2.imencode('.jpg', image)
        if not success:
            raise ValueError("Failed to encode image")

        # Encode to base64
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return jpg_as_text

    def analyze_surroundings(self, images: List[np.ndarray], context: str = "") -> Dict[str, Any]:
        """Analyze multiple images to understand robot's surroundings.

        Args:
            images: List of OpenCV images from different angles
            context: Additional context about the robot's state

        Returns:
            Dictionary with analysis results
        """
        # Prepare image data
        image_contents = []
        for i, img in enumerate(images):
            base64_image = self.encode_image(img)
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "low"  # Use low detail for cost efficiency
                }
            })

        # Build the prompt
        prompt = f"""You are analyzing images from a robot's camera after it has done a 360-degree rotation.
The images show the robot's surroundings from different angles.
{context}

Please provide:
1. A brief description of the environment (2-3 sentences)
2. List of notable objects or landmarks visible
3. Any potential obstacles or hazards
4. Whether any humans are visible and their approximate positions
5. Suggested navigation strategies for this environment

IMPORTANT: Return ONLY valid JSON without any markdown formatting or code blocks.
Format your response as pure JSON:
{{
    "environment_description": "...",
    "objects": ["object1", "object2", ...],
    "obstacles": ["obstacle1", ...],
    "humans_detected": true/false,
    "human_positions": ["front-left at medium distance", ...],
    "navigation_suggestions": "...",
    "safety_notes": "..."
}}"""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *image_contents
                ]
            }
        ]

        try:
            response = self._call_api(messages)
            # Parse JSON from response
            result = json.loads(response)
            result['raw_response'] = response
            result['num_images_analyzed'] = len(images)
            return result
        except json.JSONDecodeError:
            # Fallback if response isn't valid JSON
            return {
                "environment_description": response,
                "objects": [],
                "obstacles": [],
                "humans_detected": False,
                "human_positions": [],
                "navigation_suggestions": "",
                "safety_notes": "",
                "raw_response": response,
                "num_images_analyzed": len(images)
            }

    def find_human(self, image: np.ndarray) -> VisionAnalysis:
        """Analyze a single image to find humans and determine navigation direction.

        Args:
            image: OpenCV image from robot's camera

        Returns:
            VisionAnalysis object with detection results and recommended action
        """
        base64_image = self.encode_image(image)

        prompt = """You are helping a robot navigate towards the closest human.
Analyze this image and provide:
1. Whether any humans are visible
2. If humans are visible, their position relative to the robot's view (left, center, right)
3. Approximate distance (close <1m, medium 1-3m, far >3m)
4. Recommended movement command for the robot

IMPORTANT: Return ONLY valid JSON without any markdown formatting or code blocks.
Format your response as pure JSON:
{
    "human_detected": true/false,
    "human_count": 0,
    "primary_human_position": "left|center|right|none",
    "primary_human_distance": "close|medium|far|unknown",
    "other_humans": ["position: distance", ...],
    "recommended_action": "forward|backward|turn_left|turn_right|stop|approach_slowly",
    "action_duration": 0.5,
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation",
    "obstacles_noted": ["obstacle1", ...],
    "safety_concerns": ""
}"""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": "low"
                        }
                    }
                ]
            }
        ]

        try:
            response = self._call_api(messages)
            result = json.loads(response)

            # Create VisionAnalysis object
            return VisionAnalysis(
                description=result.get('reasoning', ''),
                objects_detected=result.get('obstacles_noted', []),
                human_detected=result.get('human_detected', False),
                human_direction=result.get('primary_human_position', 'none'),
                human_distance=result.get('primary_human_distance', 'unknown'),
                recommended_action=result.get('recommended_action', 'stop'),
                confidence=result.get('confidence', 0.0),
                raw_response=response
            )
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response[:500] if 'response' in locals() else 'N/A'}")
            # Fallback for non-JSON response
            return VisionAnalysis(
                description=response if 'response' in locals() else "Parse error",
                objects_detected=[],
                human_detected=False,
                human_direction='none',
                human_distance='unknown',
                recommended_action='stop',
                confidence=0.0,
                raw_response=response if 'response' in locals() else "Parse error"
            )

    def _call_api(self, messages: List[Dict], max_tokens: int = 500) -> str:
        """Call OpenAI API with messages.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens in response

        Returns:
            Response text from the model
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3  # Lower temperature for more consistent responses
        }

        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            content = result['choices'][0]['message']['content']

            # Clean up response if it contains markdown code blocks
            if '```json' in content:
                # Extract JSON from markdown code blocks
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end != -1:
                    content = content[start:end].strip()
            elif '```' in content:
                # Remove any other code blocks
                start = content.find('```') + 3
                end = content.find('```', start)
                if end != -1:
                    content = content[start:end].strip()

            return content

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
        except KeyError as e:
            logger.error(f"Unexpected API response format: {e}")
            logger.error(f"Response: {response.text if 'response' in locals() else 'N/A'}")
            raise

class VisionNavigator:
    """High-level navigation using vision AI."""

    def __init__(self, robot_controller, camera, openai_vision: OpenAIVision):
        """Initialize vision navigator.

        Args:
            robot_controller: Robot control interface
            camera: Camera interface
            openai_vision: OpenAI vision interface
        """
        self.robot = robot_controller
        self.camera = camera
        self.vision = openai_vision
        self.running = False
        self.last_action_time = 0
        self.action_cooldown = 0.5  # Minimum time between actions

    def scan_surroundings(self, num_images: int = 8, rotation_speed: int = 30) -> Dict[str, Any]:
        """Perform 360-degree scan and analyze surroundings.

        Args:
            num_images: Number of images to capture during rotation
            rotation_speed: Speed of rotation (0-100)

        Returns:
            Analysis results from GPT-4o mini
        """
        images = []
        angle_per_image = 360 / num_images
        rotation_time = angle_per_image / (rotation_speed * 3.6)  # Approximate time calculation

        logger.info(f"Starting 360-degree scan with {num_images} images")

        for i in range(num_images):
            # Capture image
            frame, _ = self.camera.capture_frame()
            if frame is not None:
                images.append(frame.copy())

            # Rotate to next position (except for last image)
            if i < num_images - 1:
                self.robot.turn_right(rotation_speed)
                time.sleep(rotation_time)
                self.robot.stop_motors()
                time.sleep(0.2)  # Let robot stabilize

        logger.info(f"Captured {len(images)} images, analyzing...")

        # Analyze all images
        context = f"The robot has just completed a 360-degree rotation, capturing {num_images} images at equal intervals."
        analysis = self.vision.analyze_surroundings(images, context)

        return analysis

    def navigate_to_human(self, max_duration: int = 30) -> bool:
        """Navigate towards the closest human using vision AI.

        Args:
            max_duration: Maximum time to search (seconds)

        Returns:
            True if human was found and approached, False otherwise
        """
        self.running = True
        start_time = time.time()
        human_found = False
        search_rotation = 0

        logger.info("Starting human navigation mode")

        while self.running and (time.time() - start_time) < max_duration:
            # Capture current frame
            frame, _ = self.camera.capture_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # Analyze frame for humans
            analysis = self.vision.find_human(frame)

            # Execute recommended action
            current_time = time.time()
            if current_time - self.last_action_time >= self.action_cooldown:
                if analysis.human_detected:
                    human_found = True
                    search_rotation = 0

                    # Execute navigation based on recommendation
                    action = analysis.recommended_action
                    duration = 0.5  # Default action duration

                    if action == 'forward' or action == 'approach_slowly':
                        speed = 20 if action == 'approach_slowly' else 30
                        if analysis.human_distance == 'close':
                            logger.info("Human very close, stopping")
                            self.robot.stop_motors()
                            self.running = False
                            break
                        else:
                            self.robot.move_forward(speed)
                    elif action == 'turn_left':
                        self.robot.turn_left(25)
                    elif action == 'turn_right':
                        self.robot.turn_right(25)
                    elif action == 'backward':
                        self.robot.move_backward(20)
                    elif action == 'stop':
                        self.robot.stop_motors()
                        if analysis.human_distance == 'close':
                            self.running = False
                            break

                    # Apply action for duration
                    time.sleep(duration)
                    self.robot.stop_motors()

                else:
                    # No human detected, search by rotating
                    search_rotation += 1
                    if search_rotation % 4 == 0:  # Every 4 attempts, do larger rotation
                        logger.info("Searching for humans - large rotation")
                        self.robot.turn_right(30)
                        time.sleep(1.0)
                    else:
                        logger.info("Searching for humans - small rotation")
                        self.robot.turn_right(25)
                        time.sleep(0.3)
                    self.robot.stop_motors()

                self.last_action_time = current_time

            # Small delay between iterations
            time.sleep(0.1)

        self.robot.stop_motors()
        self.running = False

        return human_found

    def stop(self):
        """Stop navigation."""
        self.running = False
        self.robot.stop_motors()