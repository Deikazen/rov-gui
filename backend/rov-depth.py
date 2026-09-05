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
from flask_cors import CORS

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
CORS(app)

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
    surface_pressure = None

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

            target_sys = master.target_system or 1
            target_comp = master.target_component or 1
            print(
                f"[MAVLink] Heartbeat received. System ID: {target_sys}, Component ID: {target_comp}")

            with state_lock:
                real_data['mavlink_connected'] = True

            # Request high-frequency data streams from ArduSub
            # 1. EXTRA2 stream (contains VFR_HUD: depth & climb rate) @ 20 Hz
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
                20, 1
            )
            # 2. RAW_SENSORS stream (contains SCALED_PRESSURE / Bar30) @ 20 Hz
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS,
                20, 1
            )
            # 3. POSITION stream (GLOBAL_POSITION_INT) @ 10 Hz
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                10, 1
            )
            # 4. ALL STREAMS fallback @ 10 Hz
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10, 1
            )

            # Request explicit message interval via MAVLink 2 if supported (50000 us = 20 Hz)
            try:
                master.mav.command_long_send(
                    target_sys, target_comp,
                    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                    0, 74, 50000, 0, 0, 0, 0, 0  # VFR_HUD (ID 74)
                )
            except Exception:
                pass

            last_msg_time = time.time()
            last_vfr_time = 0.0
            last_alt_time = 0.0
            last_stream_req_time = time.time()
            surface_pressure = None

            # Main fast receive loop - non-blocking queue drain to prevent UDP buffer lag
            while True:
                now = time.time()

                # Re-request streams every 10 seconds to ensure stream continuity
                if now - last_stream_req_time > 10.0:
                    try:
                        master.mav.request_data_stream_send(
                            target_sys, target_comp,
                            mavutil.mavlink.MAV_DATA_STREAM_EXTRA2, 20, 1
                        )
                        master.mav.request_data_stream_send(
                            target_sys, target_comp,
                            mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS, 20, 1
                        )
                    except Exception:
                        pass
                    last_stream_req_time = now

                # Drain all pending UDP packets so real_data immediately reflects the latest packet
                drained_count = 0
                while drained_count < 100:
                    msg = master.recv_msg()
                    if msg is None:
                        break

                    drained_count += 1
                    last_msg_time = now
                    msg_type = msg.get_type()

                    # Heartbeat
                    if msg_type == 'HEARTBEAT':
                        with state_lock:
                            real_data['mavlink_connected'] = True

                    # 1. PRIMARY: VFR_HUD (ArduSub standard for depth & climb rate, direct & immediate)
                    elif msg_type == 'VFR_HUD':
                        # In ArduSub, underwater altitude is negative depth (meters).
                        # msg.alt is negative when submerged/pressed (e.g. -0.5m).
                        depth_m = max(0.0, -float(msg.alt))
                        rate_ms = -float(msg.climb)
                        with state_lock:
                            real_data['depth'] = depth_m
                            real_data['rate'] = rate_ms
                            real_data['mavlink_connected'] = True
                        last_vfr_time = now

                    # 2. HIGH PRECISION: ALTITUDE (MAVLink 2 message #141)
                    elif msg_type == 'ALTITUDE':
                        if hasattr(msg, 'altitude_relative'):
                            depth_m = max(0.0, -float(msg.altitude_relative))
                            with state_lock:
                                real_data['depth'] = depth_m
                                real_data['mavlink_connected'] = True
                            last_alt_time = now

                    # 3. DIRECT SENSOR PRESSURE: SCALED_PRESSURE2 (Bar30 external) or SCALED_PRESSURE
                    elif msg_type in ('SCALED_PRESSURE2', 'SCALED_PRESSURE'):
                        press_abs = getattr(msg, 'press_abs', None)
                        if press_abs is not None and press_abs > 500:
                            if surface_pressure is None:
                                surface_pressure = float(press_abs)
                            
                            # Fallback if VFR_HUD is not actively publishing
                            if now - last_vfr_time > 1.0 and now - last_alt_time > 1.0:
                                delta_p = max(0.0, float(press_abs) - surface_pressure)
                                depth_m = delta_p / 98.0665
                                with state_lock:
                                    real_data['depth'] = depth_m
                                    real_data['mavlink_connected'] = True

                    # 4. FALLBACK: GLOBAL_POSITION_INT (relative_alt in mm from EKF)
                    elif msg_type == 'GLOBAL_POSITION_INT':
                        # Only use as fallback when direct sensor streams (VFR_HUD/ALTITUDE) are absent
                        if now - last_vfr_time > 1.0 and now - last_alt_time > 1.0:
                            if hasattr(msg, 'relative_alt'):
                                depth_m = max(0.0, -float(msg.relative_alt) / 1000.0)
                                with state_lock:
                                    real_data['depth'] = depth_m
                                    real_data['mavlink_connected'] = True

                # Disconnection tolerance (no message for > 5s)
                if now - last_msg_time > 5.0:
                    print("[MAVLink] Connection lost (timeout > 5s)...")
                    with state_lock:
                        real_data['mavlink_connected'] = False
                    break

                # Sleep briefly only if queue was already empty, to avoid 100% CPU
                if drained_count == 0:
                    time.sleep(0.002)

        except Exception as e:
            print(f"[MAVLink] Error: {e}")
            with state_lock:
                real_data['mavlink_connected'] = False
            time.sleep(RECONNECT_DELAY_S)
        finally:
            if master is not None:
                try:
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

        time.sleep(0.05)


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

    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
