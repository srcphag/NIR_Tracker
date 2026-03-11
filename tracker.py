import cv2
import numpy as np
import time
import threading
import json
import os
from pypylon import pylon, genicam
from pythonosc import udp_client

class BlobTracker:
    def __init__(self):
        # Configuration properties
        self.camera_id = "IR"
        self.threshold_range = [200, 255]
        self.min_blob_size = 5
        self.bounding_box = [0.1, 0.0, 0.6, 1.0] # [x_min, y_min, x_max, y_max]
        self.invert_bounds = False
        self.show_bounds = True
        self.preprocess_threshold = 20 # None = disabled
        self.smoothing_alpha = 0.05
        
        # OSC Configuration
        self.osc_enabled = True
        self.osc_ip = "192.168.0.100"
        self.osc_port = 9000
        self.osc_address = "/point"
        self.osc_client = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port) if self.osc_enabled else None
        self.osc_no_tracking_sent = False 
        
        # Display Colors
        self.color_crosshair = (246, 130, 59)
        self.color_circle = (0, 255, 255)
        self.color_bounds = (200, 200, 200)
        self.color_outside = (100, 100, 100)
        
        self.config_file = "config.json"
        
        # Load from disk if available
        self._load_config()
        
        # State
        self.running = False
        self.camera = None
        self.converter = None
        self.latest_frame_jpeg = None
        self.lock = threading.Lock()
        
        # Tracking internal state
        self.prev_pos = None
        self.prev_vel = (0.0, 0.0)
        self.smoothed_accel = 0.0
        self.current_brightness = 0.0
        self.current_x = 0.0
        self.current_y = 0.0
        self.current_area = 0.0
        self.fps = 0.0
        self._frame_count = 0
        self._fps_time = time.time()
        
        # Performance/status
        self.status_msg = "Initialized"

    def update_osc_client(self):
        if self.osc_enabled:
            self.osc_client = udp_client.SimpleUDPClient(self.osc_ip, self.osc_port)
        else:
            self.osc_client = None

    def trigger_reconnect(self):
        """Signals the background thread to attempt reconnecting to the camera."""
        self.reconnect_requested = True

    def start(self):
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._thread_main, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.reconnect_requested = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)

    def get_latest_frame(self):
        with self.lock:
            return self.latest_frame_jpeg

    def get_config(self):
        return {
            "camera_id": self.camera_id,
            "threshold_range": self.threshold_range,
            "min_blob_size": self.min_blob_size,
            "bounding_box": self.bounding_box,
            "invert_bounds": getattr(self, "invert_bounds", False),
            "show_bounds": self.show_bounds,
            "preprocess_threshold": self.preprocess_threshold,
            "smoothing_alpha": self.smoothing_alpha,
            "osc_enabled": self.osc_enabled,
            "osc_ip": self.osc_ip,
            "osc_port": self.osc_port,
            "osc_address": self.osc_address,
            "status_msg": self.status_msg,
            "current_brightness": self.current_brightness,
            "fps": round(self.fps, 1)
        }

    def update_config(self, new_config):
        needs_osc_update = False
        for key, value in new_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                if key in ['osc_enabled', 'osc_ip', 'osc_port']:
                    needs_osc_update = True
        
        if needs_osc_update:
            self.update_osc_client()
            
        self._save_config()

    def _save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.get_config(), f, indent=4)
        except Exception as e:
            print(f"[Tracker] Error saving config: {e}")

    def _load_config(self):
        if not os.path.exists(self.config_file):
            return
            
        try:
            with open(self.config_file, 'r') as f:
                saved = json.load(f)
                
            for key, value in saved.items():
                if hasattr(self, key) and key not in ['status_msg', 'current_brightness', 'fps']:
                    setattr(self, key, value)
                    
        except Exception as e:
            print(f"[Tracker] Error loading config: {e}")

    # --- Processing Helpers ---

    def _apply_prefilter(self, image, threshold):
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        
        filtered = image.copy()
        if len(image.shape) == 3:
            filtered = cv2.bitwise_and(filtered, filtered, mask=mask)
        else:
            filtered = cv2.bitwise_and(filtered, mask)
        return filtered

    def _draw_bounds_overlay(self, image, bounds):
        h, w = image.shape[:2]
        pt1 = (int(bounds[0] * w), int(bounds[1] * h))
        pt2 = (int(bounds[2] * w), int(bounds[3] * h))
        cv2.rectangle(image, pt1, pt2, self.color_bounds, 2)

    def _find_brightest_blob(self, image, threshold, min_size, bounds):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        h, w = gray.shape[:2]

        if bounds is not None:
            x_min, y_min, x_max, y_max = bounds
            
            if getattr(self, "invert_bounds", False):
                mask = np.full_like(gray, 255)
                fill_color = 0
            else:
                mask = np.zeros_like(gray)
                fill_color = 255
                
            pt1 = (int(x_min * w), int(y_min * h))
            pt2 = (int(x_max * w), int(y_max * h))
            cv2.rectangle(mask, pt1, pt2, fill_color, -1)
            gray = cv2.bitwise_and(gray, mask)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(gray)
        thresh = cv2.inRange(gray, threshold[0], threshold[1])
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

        # Only track if blob meets size threshold
        return None

    def _draw_tracking_overlay(self, image, tracking_data, is_active=True, accel=0.0):
        if tracking_data is None:
            return
        x, y, brightness, area, contour = tracking_data
        cv2.drawMarker(image, (x, y),
                       self.color_crosshair if is_active else self.color_outside,
                       markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
        
        # Draw contour if available
        if contour is not None:
            cv2.drawContours(image, [contour], 0, self.color_circle, 2)

    # --- Main Loop ---

    def _find_camera(self):
        tlFactory = pylon.TlFactory.GetInstance()
        devices = tlFactory.EnumerateDevices()
        for device in devices:
            if device.GetUserDefinedName() == self.camera_id:
                return device
        return None

    def _thread_main(self):
        print("[Tracker] Background thread starting.")
        while self.running:
            self.reconnect_requested = False
            
            target_device = self._find_camera()
            if target_device:
                success = self._run_camera_loop(target_device)
                if not success:
                    self._run_dummy_loop()
            else:
                self.status_msg = f"Camera '{self.camera_id}' not found. Check connection."
                print(f"[Tracker] {self.status_msg}")
                self._run_dummy_loop()
                
        print("[Tracker] Background thread stopped.")

    def _run_camera_loop(self, target_device):
        try:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(target_device))
            self.camera.Open()
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.status_msg = "Camera connected and grabbing."
        except Exception as e:
            msg = str(e)
            if "EDevice.cpp" in msg or "locked" in msg.lower():
                self.status_msg = f"Camera found but locked (Close TouchDesigner/PylonViewer!)"
            else:
                self.status_msg = f"Failed to open camera: {msg}"
            print(f"[Tracker] {self.status_msg}")
            if hasattr(self, 'camera') and self.camera:
                 self.camera.Close()
                 self.camera = None
            return False

        prev_time = time.time()
        max_timeouts = 10
        timeouts = 0

        try:
            while self.running and self.camera.IsGrabbing() and not self.reconnect_requested:
                try:
                    grabResult = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_Return)
                except genicam.TimeoutException:
                    timeouts += 1
                    if timeouts >= max_timeouts:
                        self.status_msg = "Camera timeouts exceeded."
                        break
                    continue
                except genicam.GenericException as e:
                    continue

                if grabResult is None or not grabResult.IsValid():
                    timeouts += 1
                    if timeouts >= max_timeouts:
                        self.status_msg = "Camera invalid grabs exceeded."
                        break
                    continue

                if not grabResult.GrabSucceeded():
                    timeouts += 1
                    grabResult.Release()
                    if timeouts >= max_timeouts:
                        self.status_msg = "Camera grab failures exceeded."
                        break
                    continue

                timeouts = 0
                now = time.time()
                dt = now - prev_time
                prev_time = now

                img = self.converter.Convert(grabResult).Array.copy()
                grabResult.Release()
                
                # FPS calculation
                self._frame_count += 1
                if now - self._fps_time >= 1.0:
                    self.fps = self._frame_count / (now - self._fps_time)
                    self._frame_count = 0
                    self._fps_time = now

                self._process_frame(img, dt)

        finally:
            if self.camera:
                self.camera.Close()
                self.camera = None
                
            if self.running and self.reconnect_requested:
                print("[Tracker] Camera closed for reconnect.")
            else:
                self.status_msg = "Camera closed."
                print("[Tracker] Camera closed in loop.")
                
        return True
            
    def _run_dummy_loop(self):
        # Fallback loop when no camera is present so the UI can still be tested
        prev_time = time.time()
        while self.running and not self.reconnect_requested:
            now = time.time()
            dt = now - prev_time
            prev_time = now
            
            img = np.zeros((1024, 1280, 3), dtype=np.uint8)

            
            # Create a moving bright spot for testing
            cx = int(1280/2 + 500 * np.sin(now))
            cy = int(1024/2 + 250 * np.cos(now * 1.3))
            # Smoothly change radius from 5 to 100 over time
            radius = int(5 + (100 - 5) * (np.sin(now * 0.5) + 1) / 2)
            cv2.circle(img, (cx, cy), radius, (255, 255, 255), -1)
            
            self._process_frame(img, dt)
            time.sleep(1/60.0)

    def _process_frame(self, img, dt):
        h, w = img.shape[:2]

        if self.preprocess_threshold is not None and self.preprocess_threshold > 0:
            img_processed = self._apply_prefilter(img, self.preprocess_threshold)
            img_output = img_processed.copy()
        else:
            img_processed = img.copy()
            img_output = img.copy()

        if self.show_bounds:
            self._draw_bounds_overlay(img_output, self.bounding_box)

        tracking_data = self._find_brightest_blob(img_processed, self.threshold_range, self.min_blob_size, bounds=self.bounding_box)
        
        if tracking_data:
            x, y, brightness, area, _ = tracking_data
            x_norm, y_norm = x / w, y / h
            self.current_brightness = brightness
            self.current_x = x_norm
            self.current_y = y_norm
            self.current_area = area
            self.osc_no_tracking_sent = False  # Reset flag when tracking is active

            if self.prev_pos is not None and dt > 0:
                vx = (x_norm - self.prev_pos[0]) / dt
                vy = (y_norm - self.prev_pos[1]) / dt
                ax = (vx - self.prev_vel[0]) / dt
                ay = (vy - self.prev_vel[1]) / dt
                raw_accel = np.sqrt(ax**2 + ay**2)
                self.smoothed_accel = (self.smoothing_alpha * raw_accel) + ((1 - self.smoothing_alpha) * self.smoothed_accel)
                self.prev_vel = (vx, vy)
            self.prev_pos = (x_norm, y_norm)

            self._draw_tracking_overlay(img_output, tracking_data, is_active=True, accel=self.smoothed_accel)

            if self.osc_enabled and self.osc_client:
                try:
                    self.osc_client.send_message(self.osc_address,
                                            [x_norm, y_norm, brightness / 255.0, self.smoothed_accel])
                except Exception as e:
                    pass # Ignore OSC errors to not crash the tracking loop

        else:
            self.prev_vel, self.smoothed_accel = (0.0, 0.0), 0.0
            self.prev_vel = (0.0, 0.0)
            self.current_brightness = 0.0
            self.current_x = 0.0
            self.current_y = 0.0
            self.current_area = 0.0

            if not self.osc_no_tracking_sent and self.osc_enabled and self.osc_client:
                try:
                    x_norm, y_norm = self.prev_pos if self.prev_pos else (0.0, 0.0)
                    self.osc_client.send_message(self.osc_address,
                                            [x_norm, y_norm, 0.0, self.smoothed_accel])
                    self.osc_no_tracking_sent = False  # Set flag after sending
                except Exception as e:
                    pass # Ignore OSC errors to not crash the tracking loop
            
            #self.prev_pos = None
        
        # Encode to JPEG for HTTP stream
        ret, buffer = cv2.imencode('.jpg', img_output)
        if ret:
            with self.lock:
                self.latest_frame_jpeg = buffer.tobytes()
