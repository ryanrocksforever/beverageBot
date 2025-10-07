# BevBot AI Vision System - Technical Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                         │
│                  (Tkinter GUI - AI Tab)                  │
└────────────────┬────────────────┬──────────────────────┘
                 │                │
┌────────────────▼────────────────▼──────────────────────┐
│              Remote Control GUI Module                   │
│         (remote_control_gui.py - 1500 lines)            │
├──────────────────────────────────────────────────────────┤
│ • AI Tab Management      • Status Display               │
│ • Thread Management      • Real-time Output             │
│ • Report Generation      • Safety Controls              │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│           OpenAI Vision Module (openai_vision.py)        │
├──────────────────────────────────────────────────────────┤
│ • OpenAIVision Class    • VisionNavigator Class         │
│ • API Communication     • Navigation Logic              │
│ • Image Processing      • Exploration Algorithm         │
└────────────────┬────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────┐
│                   Hardware Abstraction                   │
│              (RobotController, CameraInterface)          │
├──────────────────────────────────────────────────────────┤
│ • Motor Control         • Camera Capture                │
│ • Actuator Management   • GPIO Interface                │
└──────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. OpenAIVision Class
**File:** `src/openai_vision.py`
**Purpose:** Handles all communication with OpenAI's GPT-4o mini API

```python
class OpenAIVision:
    def __init__(self, api_key: Optional[str] = None)
    def encode_image(self, image: np.ndarray) -> str
    def analyze_surroundings(self, images: List[np.ndarray]) -> Dict
    def find_human(self, image: np.ndarray) -> VisionAnalysis
    def _call_api(self, messages: List[Dict]) -> str
```

**Key Methods:**
- `encode_image()`: Converts OpenCV images to base64 for API transmission
- `_call_api()`: Handles API requests with retry logic and markdown stripping
- `analyze_surroundings()`: Multi-image analysis for 360° scans
- `find_human()`: Single image analysis for human detection

### 2. VisionNavigator Class
**Purpose:** High-level navigation and exploration logic

```python
class VisionNavigator:
    def scan_surroundings(self, num_images: int = 8) -> Dict
    def navigate_to_human(self, max_duration: int = 30) -> bool
    def explore_environment(self, duration: int = 60) -> ExplorationReport
    def analyze_for_exploration(self, image: np.ndarray) -> Dict
```

**Navigation Algorithm:**
```
1. Capture current frame
2. Send to AI for analysis
3. Receive structured JSON response
4. Execute recommended action
5. Monitor for obstacles
6. Adjust strategy if stuck
7. Repeat until goal achieved
```

### 3. Data Structures

```python
@dataclass
class VisionAnalysis:
    description: str
    objects_detected: List[str]
    human_detected: bool
    human_direction: Optional[str]  # 'left', 'right', 'center'
    human_distance: Optional[str]   # 'close', 'medium', 'far'
    recommended_action: Optional[str]
    confidence: float
    raw_response: str

@dataclass
class ExplorationReport:
    duration: float
    areas_explored: int
    obstacles_encountered: List[str]
    objects_found: List[str]
    humans_detected: int
    environment_type: str
    navigation_challenges: List[str]
    safety_incidents: int
    total_distance_estimate: float
    summary: str
    detailed_observations: List[Dict[str, Any]]
```

---

## API Communication Protocol

### Request Structure
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "prompt"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/jpeg;base64,{base64_image}",
            "detail": "low"
          }
        }
      ]
    }
  ],
  "max_tokens": 500,
  "temperature": 0.3
}
```

### Response Processing
1. **Markdown Stripping**: Remove ```json blocks if present
2. **JSON Parsing**: Convert to structured data
3. **Validation**: Ensure required fields exist
4. **Fallback**: Graceful degradation on parse errors

---

## Navigation Algorithms

### Human Finding Algorithm
```python
while searching and time_remaining:
    frame = capture_camera()
    analysis = ai.find_human(frame)

    if analysis.human_detected:
        if analysis.human_direction == "left":
            robot.turn_left(25)
        elif analysis.human_direction == "right":
            robot.turn_right(25)
        elif analysis.human_direction == "center":
            if analysis.human_distance == "close":
                robot.stop()
                break
            else:
                robot.move_forward(30)
    else:
        # Search pattern
        robot.turn_right(25)  # Rotate to search
```

### Exploration Algorithm
```python
exploration_step = 0
stuck_counter = 0
movement_history = []

while exploring:
    frame = capture_camera()
    analysis = ai.analyze_for_exploration(frame)

    # Check for immediate obstacles
    if analysis.obstacles.immediate:
        robot.stop()
        robot.move_backward(20)
        robot.turn_to_safe_direction(analysis.safe_directions)
        continue

    # Execute recommended action
    if analysis.recommended_action == "forward":
        robot.move_forward(25)
    elif analysis.recommended_action == "turn_left":
        robot.turn_left(25)
    # ... more actions

    # Anti-stuck mechanism
    if movement_history[-3:] == ["stop", "stop", "stop"]:
        execute_unstuck_routine()
```

### Anti-Stuck Routine
```python
def execute_unstuck_routine():
    robot.move_backward(25)
    sleep(1.0)
    robot.turn_right(30)
    sleep(1.5)
    robot.stop()
```

---

## Thread Management

### GUI Thread Structure
```
Main Thread (Tkinter)
├── Camera Processing Thread
│   └── Continuous frame capture
├── AI Worker Thread (per operation)
│   ├── Scan Worker
│   ├── Navigation Worker
│   └── Exploration Worker
└── Progress Monitor Thread
    └── Status updates
```

### Thread Safety
- Queue-based frame passing (max size: 2)
- Thread-safe status updates via `root.after()`
- Daemon threads for automatic cleanup
- Stop flags for graceful termination

---

## Performance Optimization

### Image Processing
- **Resolution**: 640x480 for processing
- **Encoding**: JPEG compression before base64
- **Detail Level**: "low" for API calls (reduces tokens)
- **Batch Processing**: Multiple images in single API call for scans

### API Optimization
```python
# Optimized settings
config = {
    "model": "gpt-4o-mini",        # Most cost-effective
    "max_tokens": 500,              # Limit response size
    "temperature": 0.3,             # Consistent responses
    "image_detail": "low"           # Reduce token usage
}
```

### Navigation Timing
```python
TIMING_CONSTANTS = {
    "action_cooldown": 0.5,         # Minimum time between actions
    "forward_duration": 0.8,        # Forward movement time
    "turn_duration": 0.5,           # Turn time
    "scan_rotation_time": 2.0,     # Time per scan segment
    "unstuck_backup": 1.0,          # Backup duration when stuck
}
```

---

## Safety Systems

### Collision Avoidance
```python
if immediate_obstacles and safety_first:
    # Emergency response
    robot.stop_motors()
    robot.move_backward(20)

    # Find escape route
    if 'right' in safe_directions:
        robot.turn_right(30)
    elif 'left' in safe_directions:
        robot.turn_left(30)
    else:
        robot.turn_right(30)  # 180° turn
```

### Human Safety
```python
if human_distance == "close":
    robot.stop_motors()
    log("Human very close - stopping for safety")
    mission_complete = True
```

### Emergency Stop
- GUI Stop button always available
- Sets `ai_running = False` flag
- Calls `robot.stop_motors()`
- Terminates worker threads

---

## Configuration Management

### API Configuration
```json
{
  "api_key": "sk-...",
  "model": "gpt-4o-mini",
  "max_tokens": 500,
  "temperature": 0.3,
  "scan_settings": {
    "num_images": 8,
    "rotation_speed": 30,
    "image_detail": "low"
  },
  "navigation_settings": {
    "max_duration": 30,
    "action_cooldown": 0.5,
    "search_rotation_speed": 25,
    "approach_speed": 20,
    "normal_speed": 30
  }
}
```

### Configuration Loading Priority
1. Environment variable: `OPENAI_API_KEY`
2. Local config: `robot/config/openai_config.json`
3. Home directory: `~/.bevbot/openai_config.json`

---

## Error Handling

### API Errors
```python
try:
    response = requests.post(url, json=payload)
    response.raise_for_status()
except requests.RequestException as e:
    logger.error(f"API request failed: {e}")
    return fallback_response
```

### Hardware Errors
```python
if not self.camera.is_available():
    self.simulation_mode = True
    logger.warning("Camera not available, using simulation")
```

### Parse Errors
```python
try:
    result = json.loads(response)
except json.JSONDecodeError:
    # Use fallback behavior
    return VisionAnalysis(
        human_detected=False,
        recommended_action="stop",
        ...
    )
```

---

## Logging and Debugging

### Log Levels
- **INFO**: Normal operations, state changes
- **WARNING**: Recoverable issues, fallbacks
- **ERROR**: Failures requiring attention
- **DEBUG**: Detailed trace information

### Debug Output
```python
logger.debug(f"Raw API response: {response[:500]}")
logger.info(f"Exploration step {step}: {action}")
logger.warning(f"Obstacle detected: {obstacle}")
logger.error(f"Failed to parse JSON: {error}")
```

---

## Testing Infrastructure

### Unit Test Structure
```python
def test_api_key_loading():
    vision = OpenAIVision()
    assert vision.api_key is not None

def test_image_encoding():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    encoded = vision.encode_image(image)
    assert len(encoded) > 1000

def test_json_parsing():
    response = '{"human_detected": true}'
    parsed = json.loads(response)
    assert parsed['human_detected'] == True
```

### Integration Testing
```bash
# Test script
python scripts/test_ai_vision.py

# Tests performed:
1. API key configuration
2. Image encoding
3. API connectivity
4. Response parsing
5. Navigation logic
```

---

## Deployment Considerations

### Raspberry Pi Optimization
- Hardware PWM for motor control
- pigpio daemon for GPIO access
- Camera interface via V4L2
- Headless operation support

### Network Requirements
- Stable internet for API calls
- ~100KB per image upload
- 2-3 second latency tolerance
- Retry logic for connection issues

### Resource Usage
- RAM: ~200MB for application
- CPU: 10-20% during navigation
- Network: 1-5 MB/minute active use
- Storage: <10MB for reports

---

## Security Considerations

### API Key Protection
- Never hardcode keys in source
- Use environment variables
- `.gitignore` configuration files
- Rotate keys regularly

### Data Privacy
- Images processed in cloud
- No persistent storage by default
- Local report storage only
- No personally identifiable information logged

---

## Future Architecture Improvements

### Planned Enhancements
1. **Edge AI Integration**: Run smaller models locally
2. **WebSocket Communication**: Real-time streaming vs polling
3. **Multi-Camera Support**: Stereo vision and depth perception
4. **SLAM Integration**: Simultaneous localization and mapping
5. **Distributed Processing**: Multi-robot coordination

### Scalability Path
```
Current: Single robot → Single API
Future:  Multiple robots → API Gateway → Load Balancer → API Pool
         ↓
         Shared Knowledge Base
```

---

*This document provides the technical foundation for understanding and extending BevBot's AI Vision System.*