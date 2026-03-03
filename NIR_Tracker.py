"""
Basler Camera Blob Tracking - Acceleration & Filtering Edition
with NDI Output for TouchDesigner

Tracks the brightest blob, filters positions via an Active Zone,
calculates acceleration, applies a low-pass filter to reduce noise,
and streams the OpenCV render output to TouchDesigner via NDI.

Dependencies:
    pip install pypylon opencv-python numpy python-osc ndi-python

NDI library note:
    ndi-python requires the NDI SDK runtime DLLs to be installed separately.
    Download the free NDI Tools pack from: https://ndi.video/tools/
    (includes the runtime needed by ndi-python)
"""

from pypylon import pylon
from pypylon import genicam
import cv2
import numpy as np
import sys
import time
from pythonosc import udp_client

# NDI import with a clear error message if the package is missing
try:
    import NDIlib as ndi
except ImportError:
    raise ImportError(
        "ndi-python is not installed. Run: pip install ndi-python\n"
        "Also install NDI Tools runtime from: https://ndi.video/tools/"
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CAMERA_ID = "IR"
DISPLAY_WINDOW = True
BLOB_THRESHOLD = 200
MIN_BLOB_SIZE = 5

# Bounding Box Configuration (Normalized 0.0 to 1.0)
#BOUNDING_BOX = [0.25, 0.4, 0.6, 1]
BOUNDING_BOX = [0.1, 0.0, 0.6, 1.0]
SHOW_BOUNDS = True

# Pre-processing Threshold Filter (Optional)
# Zeroes out all pixels below this value BEFORE blob detection.
# When enabled, the filtered image becomes the main display/NDI output.
# Useful for isolating very bright points and eliminating noise.
PREPROCESS_THRESHOLD = 20   # None = disabled, or set to 150-250 to enable

# Runtime Keyboard Controls (press keys while program is running):
# - '↑' (UP arrow) or '+' : INCREASE threshold by 5
# - '↓' (DOWN arrow) or '-' : DECREASE threshold by 5  
# - 'p' : toggle prefilter on/off
# - 'r' : reset threshold to initial value
# - 'q' : quit

# Acceleration & Noise Filtering
# Alpha (0.0 to 1.0): Lower = smoother/slower, Higher = noisier/faster
SMOOTHING_ALPHA = 0.05

# OSC Configuration
OSC_ENABLED = True
OSC_IP = "192.168.0.100"
OSC_PORT = 9000
OSC_ADDRESS = "/blob/data"  # Message format: [x, y, brightness, acceleration]

# NDI Configuration
NDI_ENABLED = False
NDI_SOURCE_NAME = "OpenCV"   # Name shown in TouchDesigner's NDI In TOP
NDI_FRAME_RATE_N = 60             # Numerator   → 60/1 = 60 fps target
NDI_FRAME_RATE_D = 1              # Denominator   (match your camera frame rate)

# Colors
COLOR_CROSSHAIR = (0, 255, 0)    # Green
COLOR_CIRCLE    = (0, 255, 255)  # Yellow
COLOR_TEXT      = (255, 255, 255)# White
COLOR_BOUNDS    = (0, 0, 255)    # Red (Active Zone)
COLOR_OUTSIDE   = (100, 100, 100)# Gray

# ---------------------------------------------------------------------------
# NDI helpers
# ---------------------------------------------------------------------------

def create_ndi_sender(source_name: str):
    """Initialise NDI and return a sender handle, or None on failure."""
    if not ndi.initialize():
        print("[NDI] Failed to initialise NDI library. Is the NDI runtime installed?")
        return None

    send_settings = ndi.SendCreate()
    send_settings.ndi_name = source_name
    sender = ndi.send_create(send_settings)

    if sender is None:
        print("[NDI] Failed to create NDI sender.")
        ndi.destroy()
        return None

    print(f"[NDI] Sender '{source_name}' created. Visible on the local network.")
    return sender


def send_ndi_frame(sender, frame_bgr: np.ndarray,
                   frame_rate_n: int = 60, frame_rate_d: int = 1):
    """
    Send a single BGR OpenCV frame over NDI.

    NDI expects BGRA (4-channel), so we add an alpha channel here.
    The conversion is cheap because numpy just appends a constant plane.
    """
    # Convert BGR → BGRA (NDI native format on Windows/Linux)
    frame_bgra = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2BGRA)
    h, w = frame_bgra.shape[:2]

    video_frame = ndi.VideoFrameV2()
    video_frame.xres = w
    video_frame.yres = h
    video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRA
    video_frame.frame_rate_N = frame_rate_n
    video_frame.frame_rate_D = frame_rate_d
    video_frame.data = frame_bgra          # ndi-python reads the numpy array directly
    video_frame.line_stride_in_bytes = w * 4

    ndi.send_send_video_v2(sender, video_frame)


def destroy_ndi_sender(sender):
    """Clean shutdown of the NDI sender and library."""
    if sender is not None:
        ndi.send_destroy(sender)
    ndi.destroy()
    print("[NDI] Sender destroyed.")


# ---------------------------------------------------------------------------
# Camera helpers
# ---------------------------------------------------------------------------

def find_camera(camera_id: str):
    tlFactory = pylon.TlFactory.GetInstance()
    devices = tlFactory.EnumerateDevices()
    for device in devices:
        if device.GetUserDefinedName() == camera_id:
            return device
    return None


# ---------------------------------------------------------------------------
# Image Pre-processing
# ---------------------------------------------------------------------------

def apply_prefilter(image, threshold):
    """
    Apply a global threshold to zero out dim pixels.
    Returns a copy of the image with pixels < threshold set to 0.
    This helps isolate the brightest regions before blob detection.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Create mask: pixels >= threshold remain, others → 0
    _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    
    # Apply mask to original image
    filtered = image.copy()
    if len(image.shape) == 3:
        filtered = cv2.bitwise_and(filtered, filtered, mask=mask)
    else:
        filtered = cv2.bitwise_and(filtered, mask)
    
    return filtered


# ---------------------------------------------------------------------------
# Tracking helpers
# ---------------------------------------------------------------------------

def is_inside_bounds(x_norm, y_norm, bounds):
    x_min, y_min, x_max, y_max = bounds
    return x_min <= x_norm <= x_max and y_min <= y_norm <= y_max


def draw_bounds_overlay(image, bounds):
    h, w = image.shape[:2]
    pt1 = (int(bounds[0] * w), int(bounds[1] * h))
    pt2 = (int(bounds[2] * w), int(bounds[3] * h))
    cv2.rectangle(image, pt1, pt2, COLOR_BOUNDS, 2)
    cv2.putText(image, "ACTIVE ZONE", (pt1[0], pt1[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_BOUNDS, 1)


def find_brightest_blob(image, threshold=200, min_size=5, bounds=None):
    """
    Find the brightest blob in the image.
    
    Args:
        image: Input image (BGR or grayscale)
        threshold: Minimum brightness threshold
        min_size: Minimum blob area in pixels
        bounds: Optional [x_min, y_min, x_max, y_max] normalized (0-1) coordinates.
                If provided, only blobs within this region are considered.
    
    Returns:
        Tuple of (x, y, brightness, area, contour) or None if no blob found
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    h, w = gray.shape[:2]

    # Apply bounding box mask if provided
    if bounds is not None:
        x_min, y_min, x_max, y_max = bounds
        mask = np.zeros_like(gray)
        pt1 = (int(x_min * w), int(y_min * h))
        pt2 = (int(x_max * w), int(y_max * h))
        cv2.rectangle(mask, pt1, pt2, 255, -1)  # Fill rectangle with white
        gray = cv2.bitwise_and(gray, mask)  # Zero out everything outside bounds

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray)
    _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    brightest_blob = None
    for contour in contours:
        if cv2.contourArea(contour) >= min_size:
            if cv2.pointPolygonTest(contour, max_loc, False) >= 0:
                brightest_blob = contour
                break

    if brightest_blob is not None:
        M = cv2.moments(brightest_blob)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            return (cx, cy, max_val, cv2.contourArea(brightest_blob), brightest_blob)

    return (max_loc[0], max_loc[1], max_val, 1, None) if max_val >= threshold else None


def draw_tracking_overlay(image, tracking_data, is_active=True, accel=0.0, prefilter_active=False):
    if tracking_data is None:
        return
    x, y, brightness, area, contour = tracking_data
    color = COLOR_CIRCLE if is_active else COLOR_OUTSIDE
    cv2.drawMarker(image, (x, y),
                   COLOR_CROSSHAIR if is_active else COLOR_OUTSIDE,
                   markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
    cv2.putText(image, f"Status: {'ACTIVE' if is_active else 'OUTSIDE'}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(image, f"Accel: {accel:.2f}",
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    # Show filter status
    filter_text = "Prefilter: ON" if prefilter_active else "Prefilter: OFF"
    cv2.putText(image, filter_text,
                (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 150, 0), 2)
    cv2.putText(image, "NDI: Streaming",
                (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # OSC setup
    osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT) if OSC_ENABLED else None

    # NDI setup
    ndi_sender = create_ndi_sender(NDI_SOURCE_NAME) if NDI_ENABLED else None
    if NDI_ENABLED and ndi_sender is None:
        print("[NDI] Warning: NDI sender could not be created. Continuing without NDI.")

    # Camera setup
    target_device = find_camera(CAMERA_ID)
    if not target_device:
        print(f"[Camera] No camera found with ID '{CAMERA_ID}'. Exiting.")
        destroy_ndi_sender(ndi_sender)
        return 1

    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(target_device))
    camera.Open()
    converter = pylon.ImageFormatConverter()
    converter.OutputPixelFormat = pylon.PixelType_BGR8packed
    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    # Tracking state
    prev_pos, prev_vel, smoothed_accel = None, (0.0, 0.0), 0.0
    prev_time = time.time()

    # Runtime threshold control state
    current_threshold = PREPROCESS_THRESHOLD
    initial_threshold = PREPROCESS_THRESHOLD  # For reset
    prefilter_active = (PREPROCESS_THRESHOLD is not None)

    # Resilience: how many consecutive timeouts before we give up entirely.
    # A single dropout is ignored; a genuine camera disconnect will hit this.
    MAX_CONSECUTIVE_TIMEOUTS = 10
    consecutive_timeouts = 0

    print("[Main] Running. Keyboard controls:")
    print("  UP/DOWN arrows (or +/-) : increase/decrease threshold")
    print("  'p' : toggle prefilter on/off")
    print("  'r' : reset threshold")
    print("  'q' : quit")
    if prefilter_active:
        print(f"[Main] Prefilter ACTIVE: threshold={current_threshold}")
    else:
        print("[Main] Prefilter DISABLED (press 'p' to enable)")

    try:
        while camera.IsGrabbing():

            # ── Grab with graceful timeout handling ───────────────────────
            # TimeoutHandling_Return lets us catch transient frame drops
            # without crashing the loop. The genicam.TimeoutException guard
            # below is a secondary safety net for any unexpected throw.
            grabResult = None
            try:
                grabResult = camera.RetrieveResult(
                    5000, pylon.TimeoutHandling_Return
                )
            except genicam.TimeoutException:
                consecutive_timeouts += 1
                print(f"[Camera] Timeout #{consecutive_timeouts} — skipping frame.")
                if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                    print("[Camera] Too many consecutive timeouts. Camera may be disconnected. Exiting.")
                    break
                continue   # skip processing, try next grab immediately
            except genicam.GenericException as e:
                print(f"[Camera] GenICam error: {e}. Skipping frame.")
                continue

            # A successful return resets the timeout counter.
            # IMPORTANT: must check IsValid() before any other GrabResult method —
            # TimeoutHandling_Return gives back a non-None but data-less object on
            # timeout, and calling GrabSucceeded() on it raises a RuntimeException.
            if grabResult is None or not grabResult.IsValid():
                consecutive_timeouts += 1
                print(f"[Camera] No valid grab result (timeout #{consecutive_timeouts}).")
                if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                    print("[Camera] Too many consecutive timeouts. Camera may be disconnected. Exiting.")
                    break
                continue

            if not grabResult.GrabSucceeded():
                consecutive_timeouts += 1
                print(f"[Camera] Grab failed: {grabResult.ErrorDescription} — timeout #{consecutive_timeouts}.")
                grabResult.Release()
                if consecutive_timeouts >= MAX_CONSECUTIVE_TIMEOUTS:
                    print("[Camera] Too many consecutive failures. Exiting.")
                    break
                continue

            # ── Frame acquired successfully ────────────────────────────────
            consecutive_timeouts = 0   # reset watchdog

            now = time.time()
            dt = now - prev_time
            prev_time = now

            img = converter.Convert(grabResult).Array.copy()
            grabResult.Release()       # release as early as possible

            h, w = img.shape[:2]

            # ── Optional Pre-processing Threshold Filter ───────────────────
            # When active, the filtered image becomes the main display/NDI output.
            if prefilter_active and current_threshold is not None:
                img_processed = apply_prefilter(img, current_threshold)
                img_output = img_processed.copy()  # Filtered becomes the main output
            else:
                img_processed = img.copy()
                img_output = img.copy()  # Original becomes the main output

            if SHOW_BOUNDS:
                draw_bounds_overlay(img_output, BOUNDING_BOX)

            # ── Blob tracking on the (possibly filtered) image ─────────────
            # Pass BOUNDING_BOX to restrict tracking to the active zone only.
            # This prevents jumping to brighter blobs outside the region.
            tracking_data = find_brightest_blob(img_processed, BLOB_THRESHOLD, MIN_BLOB_SIZE, bounds=BOUNDING_BOX)

            if tracking_data:
                x, y, brightness, area, _ = tracking_data
                x_norm, y_norm = x / w, y / h

                # Acceleration with low-pass filter
                if prev_pos is not None and dt > 0:
                    vx = (x_norm - prev_pos[0]) / dt
                    vy = (y_norm - prev_pos[1]) / dt
                    ax = (vx - prev_vel[0]) / dt
                    ay = (vy - prev_vel[1]) / dt
                    raw_accel = np.sqrt(ax**2 + ay**2)
                    smoothed_accel = (SMOOTHING_ALPHA * raw_accel) + ((1 - SMOOTHING_ALPHA) * smoothed_accel)
                    prev_vel = (vx, vy)
                prev_pos = (x_norm, y_norm)

                # Blob is guaranteed to be inside bounds (enforced by find_brightest_blob)
                draw_tracking_overlay(img_output, tracking_data, is_active=True, accel=smoothed_accel)

                if osc_client:
                    osc_client.send_message(OSC_ADDRESS,
                                            [x_norm, y_norm, brightness / 255.0, smoothed_accel])
            else:
                # Lost track — reset state
                prev_pos, prev_vel, smoothed_accel = None, (0.0, 0.0), 0.0

            # ── NDI send ──────────────────────────────────────────────────
            # Sends the fully composited frame (overlay + tracking markers)
            # to TouchDesigner every loop iteration.
            if ndi_sender is not None:
                send_ndi_frame(ndi_sender, img_output, NDI_FRAME_RATE_N, NDI_FRAME_RATE_D)

            # ── Local preview with keyboard controls ──────────────────────
            if DISPLAY_WINDOW:
                # Add status overlay showing current threshold
                status_y = img_output.shape[0] - 20
                if prefilter_active and current_threshold is not None:
                    cv2.putText(img_output, f"Threshold: {current_threshold} (UP/DOWN or +/-, p=toggle, r=reset)",
                                (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                else:
                    cv2.putText(img_output, "Prefilter OFF (press 'p' to enable)",
                                (10, status_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
                
                cv2.imshow("Tracking + Accel Filter [NDI Out]", img_output)
                
                # Keyboard controls
                key = cv2.waitKey(1) & 0xFF
                
                # Debug: uncomment to see what key codes your system uses
                # if key != 255:
                #     print(f"[Debug] Key pressed: {key}")
                
                if key == ord('q'):
                    break

                # Fallback: use +/- keys as well
                elif key == ord('+') or key == ord('='):  # + or = key (increase)
                    if current_threshold is not None:
                        current_threshold = min(255, current_threshold + 5)
                        print(f"[Threshold] Increased to {current_threshold}")
                elif key == ord('-') or key == ord('_'):  # - key (decrease)
                    if current_threshold is not None:
                        current_threshold = max(0, current_threshold - 5)
                        print(f"[Threshold] Decreased to {current_threshold}")
                elif key == ord('p'):  # Toggle prefilter
                    prefilter_active = not prefilter_active
                    if prefilter_active and current_threshold is None:
                        current_threshold = 150  # Default threshold when enabling
                    status = "ENABLED" if prefilter_active else "DISABLED"
                    print(f"[Prefilter] {status}" + (f" at threshold={current_threshold}" if prefilter_active else ""))
                elif key == ord('r'):  # Reset threshold
                    current_threshold = initial_threshold if initial_threshold is not None else 150
                    print(f"[Threshold] Reset to {current_threshold}")

    finally:
        camera.Close()
        cv2.destroyAllWindows()
        destroy_ndi_sender(ndi_sender)
        print("[Main] Shutdown complete.")


if __name__ == "__main__":
    main()
