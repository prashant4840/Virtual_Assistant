# Sasta Tony Stark - Gesture Controller

A real-time hand-gesture virtual assistant with a JARVIS-style HUD, face overlay, mode switching, and system controls.

## Features

- Gesture-based mode selector (idle, gesture control, game remote, volume, brightness, exit)
- Premium HUD UI with live telemetry, gauges, help overlay, and settings drawer
- Persistent settings saved to `settings.json`
- Modular gesture engine with adaptive performance tracking
- Thread-safe FPS telemetry system
- Optimized HUD rendering with cached grid drawing
- Cross-platform runtime support for Windows and macOS

## Gesture Mappings

| Gesture | Action |
|---|---|
| Closed fist (hold) | Toggle settings mode ON/OFF |
| 1 finger (hold in menu) | Gesture Controller |
| 2 fingers (hold in menu) | Game Remote |
| 3 fingers (hold in menu) | Volume Control |
| 4 fingers (hold in menu) | Brightness Control |
| 5 fingers (hold in menu) | Exit app |

## Demo

Demo video will be updated soon.

### Pinch Controls

In Volume/Brightness mode:
- Spread thumb and index finger → increase
- Bring thumb and index finger closer → decrease

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/prashant4840/Virtual_Assistant.git
cd Virtual_Assistant
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## HUD Hotkeys

- `H` = Help overlay
- `S` = Settings drawer
- `F11` = Fullscreen/windowed
- `M` = Minimize
- `Esc` = Exit app

## Project Structure

```text
├── main.py                 # Entry point (recommended)
├── gesture_engine.py       # Core state machine + gesture logic
├── ui_layer.py             # PyQt5 HUD + camera worker + settings drawer
├── settings_manager.py     # Persistent settings load/save (JSON)
├── settings.json           # Auto-generated config file
├── HandTracking.py         # Mediapipe hand landmarks
├── FaceTracking.py         # Face detection + HUD facial overlay
├── additional_functions.py # OpenCV overlay helpers
├── VirtualAssistant.py     # Legacy OpenCV entry (preserved)
├── setup.sh                # macOS/Linux setup
├── setup.ps1               # Windows setup
└── requirements.txt
```

## Compatibility

### Windows
- Supported
- Volume control uses `pycaw`
- Brightness uses `screen_brightness_control`

### macOS
- Supported
- Volume control uses AppleScript (`osascript`)
- Brightness support depends on display hardware/driver (external monitors may vary)
- You must grant Camera + Accessibility permissions

## Quick Start (Exact Commands)

> Recommended Python: `3.10` or `3.11`
>
> Mediapipe compatibility in this project is validated with `mediapipe==0.10.9`.

### macOS

```bash
git clone https://github.com/LazyyVenom/Virtual_Assistant.git
cd Virtual_Assistant
chmod +x setup.sh
./setup.sh
```

First run permissions:
- Camera: allow access when prompted
- Accessibility: `System Settings -> Privacy & Security -> Accessibility` and allow your terminal/IDE

### Windows (PowerShell)

```powershell
git clone https://github.com/LazyyVenom/Virtual_Assistant.git
cd Virtual_Assistant
.\setup.ps1
```

### Bootstrap Script Options

- `setup.sh` defaults:
  - `PY_BIN=python3`
  - `VENV_DIR=.venv`
  - runs app automatically
- macOS examples:
  - `RUN_AFTER_SETUP=0 ./setup.sh` (install only)
  - `PY_BIN=python3.11 ./setup.sh` (specific Python)
- Windows examples:
  - `.\setup.ps1 -NoRun` (install only)
  - `.\setup.ps1 -Python py -VenvDir .venv311`

## Settings System (`settings.json`)

The app automatically creates `settings.json` on first launch.

You can update settings in two ways:
- **In-app drawer**: press `S`, change values, click **Apply + Save**
- **Manual edit**: edit `settings.json` and restart app

Main configurable fields:
- `camera_index`
- `theme` (`dark` or `light`)
- `menu_hold_seconds`, `mode_hold_seconds`
- `gesture_interval_seconds`, `game_interval_seconds`
- `swipe_left_threshold`, `swipe_right_threshold`
- `pinch_minimize_threshold`, `pinch_close_threshold`
- `pinch_smoothing_alpha`

## Troubleshooting

| Issue | Fix |
|---|---|
| `ModuleNotFoundError` for `cv2`, `PyQt5`, etc. | Activate venv and run `pip install -r requirements.txt` |
| Camera feed is blank | Change `camera_index` from settings drawer or edit `settings.json` |
| Gestures detected but no system control on macOS | Ensure Accessibility permission is granted |
| `mediapipe` errors | Use Python 3.10/3.11 and reinstall in fresh venv |
| Brightness not changing on macOS external monitor | Hardware/driver limitation; volume and gestures still work |

## Running Legacy Mode

Legacy OpenCV-only UI (without premium HUD):

- macOS: `python3 VirtualAssistant.py`
- Windows: `python VirtualAssistant.py`

## Architecture Improvements

Recent upgrades include:
- Modular mode-handler architecture
- Adaptive FPS/performance tracking
- Thread-safe telemetry handling
- Gesture cooldown system
- Smoothed pinch controls
- Graceful shutdown flow
- Cached HUD rendering optimization
- Improved gesture confidence validation

## License

This project is licensed under the MIT License. Add a `LICENSE` file to the repo root if you plan to publish publicly.

## Contact

For inquiries: `prashantsharma4849@gmail.com`
