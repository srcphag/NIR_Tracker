# NIR Tracker - Complete Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [API Reference](#api-reference)
7. [Image Processing Pipeline](#image-processing-pipeline)
8. [OSC Integration](#osc-integration)
9. [Web Interface](#web-interface)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

**NIR Tracker** is a real-time Near Infrared (NIR) blob tracking system with a web-based control interface. It connects to Basler Pylon cameras to capture infrared imagery, detects and tracks bright spots (blobs) within configurable thresholds, and streams live video with overlay graphics to a web dashboard.
The tracked blob position is sended to the localhost via OSC protocol.

### Key Features
- **Live NIR Camera Feed**: Real-time MJPEG streaming from Basler Pylon cameras
- **Blob Detection & Tracking**: Configurable threshold range for blob detection
- **Range Threshold Control**: Dual-slider interface for min/max threshold selection
- **Bounding Box Constraints**: Define tracking region within the image
- **Image Preprocessing**: Optional prefilter threshold for noise reduction
- **OSC Output**: Send tracked coordinates via Open Sound Control protocol
- **Position Smoothing**: Exponential moving average for smooth tracking
- **Web Dashboard**: Browser-based control panel with real-time updates
- **Configuration Persistence**: Settings saved to `config.json`
- **Performance Monitoring**: Real-time FPS and brightness tracking

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────┐
│             Web Browser (Dashboard)                 │
│  ┌──────────────────────────────────────────────┐   │
│  │  index.html - React-like UI with sliders     │   │
│  │  - Live video stream                         │   │
│  │  - Configuration controls                    │   │
│  │  - Real-time parameter updates               │   │
│  └──────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────┘
               │ HTTP/WebSocket over LAN
┌──────────────▼──────────────────────────────────────┐
│            Flask Web Server (server.py)             │
│  ┌──────────────────────────────────────────────┐   │
│  │  /api/config - Config GET/POST               │   │
│  │  /video_feed - MJPEG stream endpoint         │   │
│  │  /api/reconnect - Camera reconnect trigger   │   │
│  └──────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────┘
               │ Thread communication
┌──────────────▼──────────────────────────────────────┐
│         Blob Tracker (tracker.py)                   │
│  ┌──────────────────────────────────────────────┐   │
│  │  Background Thread:                          │   │
│  │  1. Camera capture loop                      │   │
│  │  2. Image preprocessing                      │   │
│  │  3. Blob detection                           │   │
│  │  4. Position tracking & smoothing            │   │
│  │  5. OSC output (if enabled)                  │   │
│  │  6. JPEG encoding for streaming              │   │
│  └──────────────────────────────────────────────┘   │
└──────────────┬──────────────────────────────────────┘
               │ USB/GigE
┌──────────────▼──────────────────────────────────────┐
│     Basler Pylon NIR Camera                         │
│     (camera_id: "IR")                              │
└──────────────────────────────────────────────────────┘
```

### File Structure

```
NIR_Tracker/
├── server.py                 # Flask web server (main entry point)
├── tracker.py               # Core blob tracking logic
├── NIR_Tracker.py           # (Optional) Alternative launcher
├── config.json              # Configuration storage
├── requirements.txt         # Python dependencies
├── run.bat                  # Windows startup script
├── run.sh                   # Linux/Mac startup script
├── README.md               # Quick start guide
├── DOCUMENTATION.md        # This file
└── templates/
    └── index.html          # Web dashboard UI
```

---

## Installation & Setup

### Prerequisites
- **Python**: 3.8+ (tested on 3.14.3)
- **Camera**: Basler Pylon-compatible NIR camera
- **Basler Pylon SDK**: Latest version installed
- **OS**: Windows, macOS, or Linux

### Step 1: Install Python & Pylon SDK

1. **Download Python 3.14.3**
   - Visit: https://www.python.org/downloads/release/python-3143/
   - Add to system PATH during installation

2. **Download Basler Pylon SDK**
   - Visit: https://www.baslerweb.com/en/downloads/software/?downloadCategory.values.label.data=pylon
   - Install to default location
   - Restart computer after installation

### Step 2: Run Startup Script

#### Windows (Recommended)
```batch
run.bat
```
This automatically:
- Creates virtual environment (`venv/`)
- Installs dependencies from `requirements.txt`
- Starts the Flask server on `http://localhost:5000`

#### macOS / Linux
```bash
chmod +x run.sh
./run.sh
```

#### Manual Setup
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python server.py
```

### Step 3: Access Web Dashboard
Open browser and navigate to: `http://localhost:5000` or `http://<machine_ip>:5000`

---

## Configuration

### Configuration File Structure (`config.json`)

```json
{
    "camera_id": "IR",                    // Basler camera user-defined name
    "threshold_range": [150, 255],        // Min/max brightness for blob detection (0-255)
    "min_blob_size": 31,                 // Minimum blob area (pixels)
    "bounding_box": [0.15, 0.15, 0.85, 0.85],  // [x_min, y_min, x_max, y_max] (0-1 normalized)
    "show_bounds": true,                 // Draw bounding box overlay
    "preprocess_threshold": null,        // Prefilter threshold (null = disabled, 1-255)
    "smoothing_alpha": 0.6,              // Position smoothing factor (0-1, higher = more smooth)
    "osc_enabled": true,                 // Enable OSC output
    "osc_ip": "127.0.0.1",              // OSC target IP address
    "osc_port": 9001,                   // OSC target port
    "osc_address": "/point",            // OSC message address
    "status_msg": "Camera connected",   // Current status (read-only)
    "current_brightness": 255.0,        // Current tracked brightness (read-only)
    "fps": 30.0                         // Current frames per second (read-only)
}
```

### Configuration Parameters

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `camera_id` | string | - | Basler camera user-defined name |
| `threshold_range` | [min, max] | 0-255 | Brightness range for blob detection |
| `min_blob_size` | int | 1+ | Minimum contour area (pixels) |
| `bounding_box` | [x_min, y_min, x_max, y_max] | 0-1 | Normalized coordinates (top-left to bottom-right) |
| `show_bounds` | bool | true/false | Show bounding box overlay |
| `preprocess_threshold` | int or null | 1-255 | Prefilter brightness threshold (null = disabled) |
| `smoothing_alpha` | float | 0-1 | EMA smoothing factor (0.05 = heavy smoothing, 0.9 = light smoothing) |
| `osc_enabled` | bool | true/false | Enable OSC message output |
| `osc_ip` | string | - | Target IP for OSC messages |
| `osc_port` | int | 1-65535 | Target port for OSC messages |
| `osc_address` | string | - | OSC address pattern (e.g., "/point", "/tracker/pos") |

### Modifying Configuration

**Via Web Dashboard:**
All parameters (except read-only fields) can be adjusted in real-time through the web interface.

**Direct File Edit:**
Edit `config.json` and restart the server, or trigger reconnect via web UI.

**Via API:**
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "threshold_range": [100, 200],
    "min_blob_size": 20,
    "smoothing_alpha": 0.3
  }'
```
---

## Usage

### Starting the System

1. **Startup**
   ```bash
   run.bat  # Windows
   ./run.sh # Linux/Mac
   ```

2. **Monitor Terminal Output**
   - Watch for "[Tracker]" messages indicating camera detection
   - Look for FPS updates to confirm processing

3. **Open Web Dashboard**
   - Navigate to `http://localhost:5000`
   - Confirm camera status shows "Connected"

### Web Dashboard Layout

```
┌───────────────────────────────────────────┐
│         NIR Tracker Dashboard             │
├─────────────────────┬─────────────────────┤
│                     │  Image Processing   │
│  Live Video Stream  │  ├─ Blob Threshold  │
│  (MJPEG 30fps)      │  │  Range Slider   │
│                     │  ├─ Min Blob Size  │
│                     │  └─ Prefilter       │
│                     │                     │
│                     │  Tracking Settings  │
│                     │  ├─ Smoothing       │
│                     │  └─ Bounding Box    │
│                     │                     │
│                     │  OSC Configuration  │
│                     │  ├─ Enable OSC      │
│                     │  ├─ IP & Port       │
│                     │  └─ Reconnect Btn   │
└─────────────────────┴─────────────────────┘
```

### Typical Workflow

1. **Initial Setup**
   - Place object in camera view
   - Adjust bounding box to region of interest
   - Enable prefilter if image is noisy

2. **Blob Detection Tuning**
   - Move the threshold range slider to bracket the target brightness
   - Increase `min_blob_size` if detecting noise
   - Adjust `show_bounds` to verify region

3. **Tracking Configuration**
   - Set `smoothing_alpha` based on desired responsiveness
   - Increase for stable tracking (~0.5-0.7)
   - Decrease for quick response (~0.1-0.3)

4. **OSC Output**
   - Enable OSC if integrating with external systems
   - Configure target IP and port
   - Messages sent to `/point` address with x, y coordinates

---

## API Reference

### Endpoints

#### GET `/`
Returns the web dashboard HTML.
```
Response: HTML page
```

#### GET `/video_feed`
MJPEG video stream endpoint.
```
Response: Multipart JPEG frames (~30fps)
Content-Type: multipart/x-mixed-replace; boundary=frame
```

#### GET `/api/config`
Retrieve current tracker configuration.
```bash
curl http://localhost:5000/api/config
```

**Response:**
```json
{
  "camera_id": "IR",
  "threshold_range": [150, 255],
  "min_blob_size": 31,
  "bounding_box": [0.15, 0.15, 0.85, 0.85],
  "show_bounds": true,
  "preprocess_threshold": null,
  "smoothing_alpha": 0.6,
  "osc_enabled": true,
  "osc_ip": "127.0.0.1",
  "osc_port": 9001,
  "osc_address": "/point",
  "status_msg": "Camera connected",
  "current_brightness": 200.5,
  "fps": 29.8
}
```

#### POST `/api/config`
Update tracker configuration.
```bash
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "threshold_range": [100, 200],
    "smoothing_alpha": 0.4,
    "osc_ip": "192.168.0.10"
  }'
```

**Request Body:** JSON object with any subset of config parameters

**Response:**
```json
{
  "status": "success",
  "config": { /* full config object */ }
}
```

#### POST `/api/reconnect`
Trigger camera reconnection attempt.
```bash
curl -X POST http://localhost:5000/api/reconnect
```

**Response:**
```json
{
  "status": "success",
  "message": "Reconnection triggered"
}
```

---

## Image Processing Pipeline

### Step-by-Step Processing

```
Raw NIR Frame (Basler Camera)
         ↓
    [1] Convert to Grayscale
         ↓
    [2] Apply Bounding Box Mask (optional)
    └─→ Only process region of interest
         ↓
    [3] Prefilter (optional)
    └─→ Apply brightness threshold to reduce noise
         ↓
    [4] Find Min/Max Brightness & Location
         ↓
    [5] Apply Threshold Range
    └─→ cv2.inRange(gray, thresh_min, thresh_max)
         ↓
    [6] Find Contours
         ↓
    [7] Detect Blobs
    └─→ Filter by min_blob_size
    └─→ Check if blob contains brightest pixel
         ↓
    [8] Calculate Center of Mass
         ↓
    [9] Apply Position Smoothing (EMA)
         ↓
   [10] Draw Overlays
    └─→ Crosshair at tracked position
    └─→ Bounding box (if enabled)
         ↓
   [11] Encode to JPEG
         ↓
   [12] OSC Output (if enabled)
    └─→ Send coordinates to OSC server
         ↓
   Stream to Web Dashboard
```

### Key Processing Functions (tracker.py)

#### `_find_brightest_blob(image, threshold, min_size, bounds)`
- Finds the brightest blob within threshold range
- Constrains search to bounding box
- Returns: `(cx, cy, brightness, area, contour)`

#### `_apply_prefilter(image, threshold)`
- Applies brightness threshold before blob detection
- Reduces noise from dark regions
- Returns: Filtered grayscale image

#### `_draw_tracking_overlay(image, tracking_data, is_active, accel)`
- Draws crosshair and visual feedback
- Indicates if target is in bounds
- Returns: Modified image

#### `_update_smoothed_position(raw_pos)`
- Exponential Moving Average: `pos_smooth = α × pos_raw + (1 - α) × pos_prev`
- Provides temporal smoothing
- Returns: Smoothed position

---

## OSC Integration

### Overview
OSC (Open Sound Control) is a protocol for communication among computers over a network. NIR Tracker can send tracked position data via OSC.

### Configuration

```json
{
  "osc_enabled": true,
  "osc_ip": "192.168.0.10",
  "osc_port": 9000,
  "osc_address": "/point"
}
```

### Message Format

**Address:** `/point` (configurable)

**Arguments:**
- `x`: Horizontal position (normalized 0-1 or pixel coordinates)
- `y`: Vertical position (normalized 0-1 or pixel coordinates)
- `brightness`: Tracked pixel brightness (0-255)

---

## Web Interface

### Technology Stack
- **Frontend**: Vanilla JavaScript + HTML/CSS
- **Styling**: Custom CSS with CSS variables
- **Protocol**: HTTP (Flask), MJPEG (video stream)
- **Real-time Updates**: Fetch API with polling

### UI Components

#### Video Stream Display
- MJPEG stream from `/video_feed` endpoint
- ~30 FPS live feed with overlays
- Status indicators and FPS counter

#### Control Panel (Sidebar)
- **Image Processing Section**
  - Threshold Range: Dual-slider for min/max blob detection
  - Min Blob Size: Slider (1-255 pixels)
  - Enable Prefilter: Toggle + threshold control

- **Tracking Settings**
  - Smoothing Alpha: Slider (0-1)
  - Bounding Box: Four input fields (x_min, y_min, x_max, y_max)
  - Show Bounds: Toggle

- **OSC Configuration**
  - Enable OSC: Toggle
  - IP Address: Text input
  - Port: Number input

- **System Control**
  - Reconnect Button: Trigger camera reconnection
  - Status Badge: Connection status

### JavaScript Functions

| Function | Purpose |
|----------|---------|
| `fetchConfig()` | Sync UI with server state every 5 seconds |
| `updateConfig(key, value)` | Update single parameter with debounce |
| `updateThresholdRange(type, value)` | Handle dual-slider min/max updates |
| `updateRangeSliderTrack()` | Update visual gradient between min/max |
| `updateBoundingBox()` | Submit bounding box coordinates |
| `togglePrefilter(enabled)` | Enable/disable prefilter threshold |
| `sendUpdate(payload)` | POST config changes to server |
| `reconnectCamera()` | Trigger camera reconnection |

### Styling Variables

```css
:root {
  --bg-color: #0f172a;              /* Dark background */
  --surface-color: #262a3b;         /* Card background */
  --text-color: #f8fafc;            /* Text color */
  --primary: #3b82f6;               /* Blue accent */
  --danger: #ef4444;                /* Red alert */
  --border-color: #334155;          /* Border color */
}
```

---

## Troubleshooting

### Camera Connection Issues

**Problem:** "Camera 'IR' not found"
- **Solution 1:** Verify camera is powered and connected via USB/GigE
- **Solution 2:** Check camera user-defined name in Pylon viewer matches `camera_id` in config
- **Solution 3:** Restart Basler Pylon service
- **Solution 4:** Click "Reconnect" button in web dashboard

**Problem:** Inconsistent camera detection
- **Solution:** Pylon SDK may have conflicts; reinstall or update to latest version

### Blob Detection Issues

**Problem:** No blobs detected
- **Solution 1:** Lower the `threshold_range` minimum value
- **Solution 2:** Increase `min_blob_size` if detecting noise
- **Solution 3:** Verify target is within bounding box (enable `show_bounds`)
- **Solution 4:** Check camera exposure/gain settings in Pylon viewer

**Problem:** Detecting too many blobs
- **Solution 1:** Narrow the `threshold_range` (increase min or decrease max)
- **Solution 2:** Increase `min_blob_size`
- **Solution 3:** Enable `preprocess_threshold` for noise reduction

### Performance Issues

**Problem:** Low FPS (< 15)
- **Solution 1:** Reduce image size/decimation in Pylon camera settings
- **Solution 2:** Decrease bounding box size
- **Solution 3:** Disable unnecessary image processing

**Problem:** Laggy web dashboard updates
- **Solution 1:** Reduce config polling interval (edit `fetchConfig`)
- **Solution 2:** Ensure LAN connection to host machine
- **Solution 3:** Check browser developer console for errors

### OSC Issues

**Problem:** OSC messages not received
- **Solution 1:** Verify `osc_enabled` is `true`
- **Solution 2:** Confirm target IP/port are correct
- **Solution 3:** Check firewall isn't blocking UDP port
- **Solution 4:** Test with simple OSC listener:
  ```python
  python -c "from pythonosc import dispatcher, osc_server; s = osc_server.ThreadingOSCUDPServer(('0.0.0.0', 9000), dispatcher.Dispatcher()); print('Listening...'); s.handle_request()"
  ```

### Web Dashboard Issues

**Problem:** Dashboard won't load
- **Solution 1:** Ensure Flask server is running: `python server.py`
- **Solution 2:** Check firewall allows port 5000
- **Solution 3:** Try `http://localhost:5000` vs IP address

**Problem:** Sliders not updating
- **Solution 1:** Refresh page (Ctrl+F5)
- **Solution 2:** Check browser console for JavaScript errors
- **Solution 3:** Verify server is responding: `curl http://localhost:5000/api/config`

---

## Support & Debugging

### Enable Debug Output
Modify `tracker.py` logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check System Information
```bash
python -c "
import cv2, numpy as np
print(f'OpenCV: {cv2.__version__}')
print(f'NumPy: {np.__version__}')
"
```

### Validate OSC Connectivity
```bash
# Terminal 1: Start NIR Tracker
python server.py

# Terminal 2: Listen for OSC
python -c "
from pythonosc import dispatcher, osc_server
s = osc_server.ThreadingOSCUDPServer(('0.0.0.0', 9000), dispatcher.Dispatcher())
print('Listening on :9000 for messages')
s.handle_request()
"
```

---

## License & Attribution

- **Basler Pylon**: Commercial SDK - https://www.askantech.com/products/basler-pylon
- **Flask**: BSD License
- **OpenCV (cv2)**: Apache 2 License
- **python-osc**: BSD License

---