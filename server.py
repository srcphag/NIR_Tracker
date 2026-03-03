from flask import Flask, render_template, Response, jsonify, request
import time
from tracker import BlobTracker

app = Flask(__name__)
tracker = BlobTracker()

def gen_frames():
    """Generator function that continuously yields JPEG frames for MJPEG streaming."""
    while True:
        frame = tracker.get_latest_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.01)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Returns the current tracker configuration."""
    return jsonify(tracker.get_config())

@app.route('/api/config', methods=['POST'])
def set_config():
    """Updates the tracker configuration."""
    new_config = request.json
    
    # Optional typing/validation could go here
    # E.g. converting strings to ints
    parsed_config = {}
    
    if 'blob_threshold' in new_config:
        parsed_config['blob_threshold'] = int(new_config['blob_threshold'])
    if 'min_blob_size' in new_config:
        parsed_config['min_blob_size'] = int(new_config['min_blob_size'])
    if 'preprocess_threshold' in new_config:
        val = new_config['preprocess_threshold']
        parsed_config['preprocess_threshold'] = int(val) if val is not None and str(val).strip() != "" else None
    if 'smoothing_alpha' in new_config:
        parsed_config['smoothing_alpha'] = float(new_config['smoothing_alpha'])
    if 'osc_enabled' in new_config:
        parsed_config['osc_enabled'] = bool(new_config['osc_enabled'])
    if 'osc_ip' in new_config:
        parsed_config['osc_ip'] = str(new_config['osc_ip'])
    if 'osc_port' in new_config:
        parsed_config['osc_port'] = int(new_config['osc_port'])
    if 'show_bounds' in new_config:
        parsed_config['show_bounds'] = bool(new_config['show_bounds'])
        
    # parse bounding box: list of 4 floats
    if 'bounding_box' in new_config:
        try:
            bb = [float(x) for x in new_config['bounding_box']]
            if len(bb) == 4:
                parsed_config['bounding_box'] = bb
        except (ValueError, TypeError):
            pass

    tracker.update_config(parsed_config)
    return jsonify({"status": "success", "config": tracker.get_config()})


@app.route('/api/reconnect', methods=['POST'])
def reconnect_camera():
    """Signals the tracker to restart the camera grab loop."""
    tracker.trigger_reconnect()
    return jsonify({"status": "success", "message": "Reconnection triggered"})


if __name__ == '__main__':
    try:
        # Start the background tracker thread
        tracker.start()
        # Start Flask development server
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        tracker.stop()
