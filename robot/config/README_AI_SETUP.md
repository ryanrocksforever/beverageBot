# BevBot AI Vision Setup

This guide explains how to set up the OpenAI Vision features for BevBot.

## Features

1. **360° Surroundings Scan**: Robot rotates 360 degrees, captures images, and GPT-4o mini provides a comprehensive analysis of the environment.

2. **Navigate to Closest Human**: AI-powered autonomous navigation that uses vision to find and approach the nearest human.

## Setup Instructions

### 1. Get OpenAI API Key

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-`)

### 2. Configure API Key

Choose one of these methods:

#### Method A: Environment Variable (Recommended)
```bash
# Linux/Mac:
export OPENAI_API_KEY="sk-your-key-here"

# Windows Command Prompt:
set OPENAI_API_KEY=sk-your-key-here

# Windows PowerShell:
$env:OPENAI_API_KEY="sk-your-key-here"
```

#### Method B: Configuration File
1. Copy `openai_config.json.example` to `openai_config.json`
2. Replace `"sk-your-openai-api-key-here"` with your actual API key
3. Keep this file secure and never commit it to version control

#### Method C: Home Directory Config
Create `~/.bevbot/openai_config.json`:
```json
{
  "api_key": "sk-your-key-here"
}
```

### 3. Install Required Dependencies

```bash
pip install requests
```

The OpenAI vision features use the standard `requests` library to communicate with the API.

## Usage

1. Launch the remote control GUI:
```bash
cd robot
./scripts/remote_control.sh
# or
python -m src.remote_control_gui
```

2. Navigate to the "AI Vision" tab

3. Use the available features:
   - **360° Surroundings Scan**: Click to perform a full environmental scan
   - **Navigate to Closest Human**: Click to start autonomous human-finding navigation
   - **Stop AI Operation**: Emergency stop for any AI operation

## AI Output Display

The GUI shows:
- **AI Thinking Process & Output**: Real-time log of what the AI is doing and thinking
- **Current Analysis**: Structured display of the latest AI analysis
- **Status Indicator**: Current state of AI operations

## Cost Considerations

- GPT-4o mini is used for cost efficiency
- Images are sent at "low" detail setting to minimize tokens
- Typical costs:
  - 360° scan (8 images): ~$0.02-0.05
  - Navigation (continuous): ~$0.01 per minute

## Troubleshooting

### "AI Not Available" Error
- Check that your API key is set correctly
- Verify the key is valid at https://platform.openai.com/
- Check your OpenAI account has credits

### No AI Vision Tab
- Ensure `openai_vision.py` is in the `src` directory
- Check that `requests` is installed: `pip install requests`
- Look for import errors in the console when starting the GUI

### API Errors
- Check your internet connection
- Verify API key permissions
- Check OpenAI service status at https://status.openai.com/

## Safety Notes

- The robot will stop automatically when it gets close to a human
- Use the Stop button to immediately halt any AI operation
- AI navigation includes obstacle detection and safety concerns
- Always supervise the robot during AI operations

## API Key Security

- **NEVER** commit your API key to version control
- Add `openai_config.json` to `.gitignore`
- Consider using environment variables in production
- Rotate your API key if it's ever exposed

## Advanced Configuration

Edit `openai_config.json` to customize:
- `num_images`: Number of images for 360° scan (default: 8)
- `rotation_speed`: Speed of rotation during scan (default: 30)
- `max_duration`: Maximum time for human search (default: 30 seconds)
- `temperature`: AI response consistency (lower = more consistent)