""""
Receive semua data sensor

"""



import json
import logging
import math
import threading
import time
import urllib.request
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymavlink import mavutil

MAVLINK_UDP_ENDPOINT_TRAJECTORY = 'udpin:0.0.0.0:14553'

app = Flask(__name__)
CORS(app)


# ==================== DEPTH ==============================

MAVLINK_UDP_ENDPOINT_DEPTH = 'udpin:0.0.0.0:14552'
MAX_DEPTH_M = 2.0                              # matches frontend default maxDepth
HEARTBEAT_TIMEOUT_S = 10.0
RECONNECT_DELAY_S = 3.0




depth_data = {
    'depth': 0.0,
    'rate': 0.0,
    'mavlink_connected': False
}


def mavlink_worker_depth():
    while True:
        master = None
        try:
            print(f"[MAVLink] Connecting via {MAVLINK_UDP_ENDPOINT_DEPTH} ...")
            master = mavutil.mavlink_connection(MAVLINK_UDP_ENDPOINT_DEPTH)

            hb = master.wait_heartbeat(timeout=HEARTBEAT_TIMEOUT_S)
            if not hb:
                print("[MAVLink] No heartbeat received, retrying...")
                depth_data['mavlink_connected'] = False
                time.sleep(RECONNECT_DELAY_S)
                continue

            print(
                f"[MAVLink] Heartbeat received. System ID: {master.target_system}")

            # Request semua data stream dari ArduSub (ALL STREAMS @ 10Hz)
            master.mav.request_data_stream_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10, 1
            )

            last_msg_time = time.time()

            # Main receive loop
            while True:
                # Tangkap SEMUA pesan MAVLink tanpa membatasi tipe di recv_match
                msg = master.recv_match(blocking=True, timeout=1.0)

                if msg:
                    msg_type = msg.get_type()

                    # Heartbeat menandakan koneksi MAVLink aktif
                    if msg_type == 'HEARTBEAT':
                        last_msg_time = time.time()
                        depth_data['mavlink_connected'] = True

                    # 1. VFR_HUD: Primary & direct depth source from ArduSub
                    if msg_type == 'VFR_HUD':
                        depth_m = max(0.0, -float(msg.alt))
                        rate_ms = -float(msg.climb)
                        depth_data['depth'] = depth_m
                        depth_data['rate'] = rate_ms
                        depth_data['mavlink_connected'] = True

                    # 2. ALTITUDE: MAVLink 2 relative altitude
                    elif msg_type == 'ALTITUDE':
                        if hasattr(msg, 'altitude_relative'):
                            depth_data['depth'] = max(0.0, -float(msg.altitude_relative))
                            depth_data['mavlink_connected'] = True

                    # 3. Fallback: GLOBAL_POSITION_INT
                    elif msg_type == 'GLOBAL_POSITION_INT':
                        if hasattr(msg, 'relative_alt'):
                            depth_data['depth'] = max(0.0, -float(msg.relative_alt) / 1000.0)
                            depth_data['mavlink_connected'] = True

                # Toleransi disconnect jika tidak ada pesan apa pun selama 5 detik
                if time.time() - last_msg_time > 5.0:
                    print("[MAVLink] Connection lost (timeout > 5s)...")
                    depth_data['mavlink_connected'] = False
                    break

        except Exception as e:
            print(f"[MAVLink] Error: {e}")
            depth_data['mavlink_connected'] = False
            time.sleep(RECONNECT_DELAY_S)
        finally:
            if master is not None:
                try:
                    master.close()
                except Exception:
                    pass


@app.route('/api/telemetry', methods=['GET'])
def get_telemetry():
    depth = depth_data['depth']
    rate = depth_data['rate']

    return jsonify({
        'depth': round(depth, 4),
        'depth_cm': round(depth * 100.0, 2),
        'rate': round(rate, 4),
        'max_depth_m': MAX_DEPTH_M,
        'max_depth_cm': MAX_DEPTH_M * 100.0,
    })

