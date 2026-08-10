"""
BlueROV2 Depth Telemetry Backend
--------------------------------
Serves index.html (untouched, separate file) and exposes:
  GET  /api/telemetry  -> current depth/rate/source data as JSON
  POST /api/source     -> switch between "real" (Pixhawk/MAVLink) and "dummy" data

Reads MAVLink telemetry over UDP from BlueOS.

IMPORTANT: BlueOS MAVLink endpoint is configured as:
    Type: UDP Client
    IP:   127.0.0.1
    Port: 14552
"UDP Client" means BlueOS actively SENDS packets to that IP:port, so this
backend must LISTEN (bind) on that same port -> udpin:0.0.0.0:14552
"""

import time
import math
import threading
from flask import Flask, jsonify, request, send_file
from pymavlink import mavutil

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# matches BlueOS "UDP Client -> 127.0.0.1:14552"
MAVLINK_UDP_ENDPOINT = 'udpin:0.0.0.0:14552'
MAX_DEPTH_M = 2.0                              # matches frontend default maxDepth
HEARTBEAT_TIMEOUT_S = 10.0
RECV_TIMEOUT_S = 2.0
RECONNECT_DELAY_S = 3.0

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared state (protected by lock)
# ---------------------------------------------------------------------------
state_lock = threading.Lock()

# 'dummy' or 'real' - matches frontend default (Dummy Data active)
current_source = 'dummy'

real_data = {
    'depth': 0.0,
    'rate': 0.0,
    'mavlink_connected': False,
}

dummy_data = {
    'depth': 0.0,
    'rate': 0.0,
}


# ---------------------------------------------------------------------------
# MAVLink background thread
# ---------------------------------------------------------------------------
def mavlink_worker():
    while True:
        master = None
        try:
            print(f"[MAVLink] Connecting via {MAVLINK_UDP_ENDPOINT} ...")
            master = mavutil.mavlink_connection(MAVLINK_UDP_ENDPOINT)

            hb = master.wait_heartbeat(timeout=HEARTBEAT_TIMEOUT_S)
            if not hb:
                print("[MAVLink] No heartbeat received, retrying...")
                with state_lock:
                    real_data['mavlink_connected'] = False
                time.sleep(RECONNECT_DELAY_S)
                continue

            print(
                f"[MAVLink] Heartbeat received. System ID: {master.target_system}")
            with state_lock:
                real_data['mavlink_connected'] = True

            # Request data streams
            master.mav.request_data_stream_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                10, 1
            )
            master.mav.request_data_stream_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                10, 1
            )

            # Main receive loop
            while True:
                msg = master.recv_match(
                    type=['GLOBAL_POSITION_INT', 'VFR_HUD'],
                    blocking=True,
                    timeout=RECV_TIMEOUT_S
                )
                if not msg:
                    print(
                        "[MAVLink] Timeout waiting for data, checking connection...")
                    with state_lock:
                        real_data['mavlink_connected'] = False
                    break  # break inner loop -> reconnect

                with state_lock:
                    real_data['mavlink_connected'] = True

                msg_type = msg.get_type()
                if msg_type == 'GLOBAL_POSITION_INT':
                    # relative_alt is mm, negative underwater -> flip & convert to meters
                    depth_m = max(0.0, -(msg.relative_alt / 1000.0))
                    with state_lock:
                        real_data['depth'] = depth_m

                elif msg_type == 'VFR_HUD':
                    # climb: negative = diving, positive = surfacing
                    # rate positive = descending (matches frontend icon logic)
                    rate_ms = -float(msg.climb)
                    with state_lock:
                        real_data['rate'] = rate_ms

        except Exception as e:
            print(f"[MAVLink] Error: {e}")
            with state_lock:
                real_data['mavlink_connected'] = False
            time.sleep(RECONNECT_DELAY_S)
        finally:
            try:
                if master is not None:
                    master.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Dummy data background thread (smooth sine oscillation for UI testing)
# ---------------------------------------------------------------------------
def dummy_worker():
    speed = 0.4  # rad/s, controls oscillation speed
    t0 = time.time()
    while True:
        t = time.time() - t0
        # depth oscillates smoothly between 0 and MAX_DEPTH_M
        depth = (MAX_DEPTH_M / 2.0) * (1 - math.cos(t * speed))
        # rate = d(depth)/dt
        rate = (MAX_DEPTH_M / 2.0) * math.sin(t * speed) * speed

        with state_lock:
            dummy_data['depth'] = depth
            dummy_data['rate'] = rate

        time.sleep(0.1)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_file('index.html')


@app.route('/api/telemetry', methods=['GET'])
def get_telemetry():
    with state_lock:
        source = current_source
        if source == 'real':
            depth = real_data['depth']
            rate = real_data['rate']
            mavlink_connected = real_data['mavlink_connected']
        else:
            depth = dummy_data['depth']
            rate = dummy_data['rate']
            # report true status regardless
            mavlink_connected = real_data['mavlink_connected']

    return jsonify({
        'source': source,
        'depth': round(depth, 4),
        'depth_cm': round(depth * 100.0, 2),
        'rate': round(rate, 4),
        'mavlink_connected': mavlink_connected,
        'max_depth_m': MAX_DEPTH_M,
        'max_depth_cm': MAX_DEPTH_M * 100.0,
    })


@app.route('/api/source', methods=['POST'])
def set_source():
    global current_source
    payload = request.get_json(silent=True) or {}
    requested = payload.get('source')

    if requested not in ('real', 'dummy'):
        return jsonify({'error': 'source must be "real" or "dummy"'}), 400

    with state_lock:
        current_source = requested

    return jsonify({'status': 'ok', 'source': current_source})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    mav_thread = threading.Thread(target=mavlink_worker, daemon=True)
    dummy_thread = threading.Thread(target=dummy_worker, daemon=True)
    mav_thread.start()
    dummy_thread.start()

    app.run(host='0.0.0.0', port=5001, debug=False)
