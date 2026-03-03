# NIR Tracker - Quick Reference Guide

## Connect the Hardware
- Connect the camera with a Cat6 RJ45 Cable to the PoE injector OUT
- Connect the PC with a Cat6 RJ45 Cable to the PoE injector IN

## Setup the Network
The camera has a fixed IP setted. To be able to communicate with the camera you must set-up the network card attached to the camera on an IP in the same range as the setted on the camera.

**To configure a fixed IP on a network card:**

1. Go to Configuration/Network/Advanced Network Configuration/**[Your Ethernet Adapter]**/More Options
2. A window will pop-up. On this window search for Internet Protocol Version 4. Double click on it.
3. Click on set fixed IP
4. Configure the adress with this parameters:
    * **IP:** 192.168.0.20
    * **Subnet:** 255.255.255.0
    * **Gateway:** Leave empty
5. Save and close

## Install Software Requisites

1. **Download Python 3.14.3**
   - Visit: https://www.python.org/downloads/release/python-3143/
   - Add to system PATH during installation

2. **Download Basler Pylon SDK**
   - Visit: https://www.baslerweb.com/en/downloads/software/?downloadCategory.values.label.data=pylon
   - Install to default location
   - Restart computer after installation

## Software Quick Start

Go to the project folder and open:

```bash
# Windows
run.bat

# Linux/Mac
chmod +x run.sh && ./run.sh

# Then open: http://localhost:5000
```
This will create the environments and will install the software dependencies for the project. 
This happens only the fist time the project starts.

## Essential Controls

| Control | Purpose | Tips |
|---------|---------|------|
| **Blob Threshold Range** | Min/Max brightness for blob detection | Drag sliders to bracket target brightness |
| **Min Blob Size** | Ignore tiny artifacts | Increase if spotting noise |
| **Enable Prefilter** | Reduce image noise | Enable if background is noisy |
| **Bounding Box** | Define tracking region | Normalized 0-1 (left, top, right, bottom) |
| **Smoothing Alpha** | Position filtering | 0.1 (responsive), 0.5 (balanced), 0.9 (smooth) |
| **Enable OSC** | Send to external app | Requires target IP:port |
| **Reconnect** | Fix camera dropout | Click if status shows "Not found" |

## Port Info

- **Web Dashboard:** http://localhost:5000
- **OSC Default:** 127.0.0.1:9000 (or configured IP:port)
- **PC:** 192.168.0.20 (Configured manually)
- **Pylon Camera:** 192.168.0.200

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | Flask web server & API endpoints |
| `tracker.py` | Blob detection & tracking engine |
| `templates/index.html` | Web dashboard UI |
| `config.json` | Settings storage |
| `DOCUMENTATION.md` | Full documentation |

## Troubleshooting Checklist

- [ ] Camera detected? Check status in dashboard
- [ ] Blobs showing? Adjust threshold range slider
- [ ] Too much noise? Enable prefilter + increase min_blob_size
- [ ] OSC not working? Check IP:port and firewall
- [ ] Web page won't load? Restart with `run.bat`


**Stuck?** See full `Documentation_EN.md` or check terminal output for error messages.
