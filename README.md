# Video and Log Saver - Desktop Application

A Python desktop application built with CustomTkinter.

## Prerequisites

### 1. Python 3.8 or higher
Check if Python is installed:
```powershell
python --version
```
If not installed, download from [python.org](https://www.python.org/downloads/) (check "Add Python to PATH" during installation).

### 2. Create a virtual environment (recommended)
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Or on Windows (CMD)
venv\Scripts\activate.bat
```

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Run the application
```powershell
python main.py
```

## Project Structure

```
video and log saver/
├── main.py           # Application entry point
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Tech Stack

- **CustomTkinter** - Modern, customizable UI framework
- **Python 3.8+** - Core language

## Android Setup (for video/log capture)

1. **Enable USB debugging** on your Android device:
   - Settings → About phone → tap "Build number" 7 times
   - Settings → Developer options → enable "USB debugging"

2. **Install ADB** (Android Debug Bridge):
   - Option A: Install [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools)
   - Option B: `winget install Google.PlatformTools` (Windows)
   - Add `adb` to your PATH

3. Connect phone via USB, select "File transfer" mode, allow debugging when prompted.

## How it works (Android + Both)

- **Start**: Connects to device, starts PC background log, starts screen recording on phone via ADB
- **Stop**: Stops recording, pulls the video to PC, saves the log file
- Files are saved to `saved_output/` in the project folder
