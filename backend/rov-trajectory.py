from pymavlink import mavutil
import math
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import threading
import time

# Koneksi ke Pixhawk (via MAVProxy/UDP atau USB)

MAVLINK_UDP_ENDPOINT = 'udpin:0.0.0.0:14553'
HEARTBEAT_TIMEOUT_S = 10.0
RECONNECT_DELAY_S = 3.0

app = Flask(__name__)
CORS(app)

state_lock = threading.Lock()

data = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
    'yaw': 0.0,
    'mavlink_connected': False,
}

# koneksi mavlink function


def mavlink_worker():
    while True:
        master = None
        try:
            print(f"[MAVLINK] Connecting via {MAVLINK_UDP_ENDPOINT} ...")
            master = mavutil.mavlink_connection(MAVLINK_UDP_ENDPOINT)

            hb = master.wait_heartbeat(timeout=HEARTBEAT_TIMEOUT_S)
            if not hb:
                print("[MAVLINK] No heartbeat received, retrying... ")
                with state_lock:
                    data['mavlink_connected'] = False
                    print("state lock di jalankan.")
                time.sleep(RECONNECT_DELAY_S)
                continue
            print(
                f"[MAVLINK] Heartbeat received. System ID: {master.target_system}"
            )

            # Request semua data stream posisi dan attitute 10Hz
            master.mav.request_data_stream_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                10,
                1,
            )

            master.mav.request_data_stream_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,  # untuk attitude/yaw
                10,
                1,
            )

            last_msg_time = time.time()

            # Looping menerima data
            while True:
                msg = master.recv_match(
                    type=['HEARTBEAT', 'LOCAL_POSITION_NED, ATTITUDE'],
                    blocking=True,
                    timeout=1.0
                )

                if msg:
                    msg_type = msg.get_type()

                    if msg_type == 'HEARTBEAT':
                        last_msg_time = time.time()
                        with state_lock:
                            data['mavlink_connected'] = True

                    elif msg_type == 'GLOBAL_POSITION_INT':
                        with state_lock:
                            data['x'] = float(msg.x)
                            data['y'] = float(msg.y)
                            data['z'] = float(msg.z)

                    elif msg_type == 'ATTITUDE':
                        with state_lock:
                            data['yaw'] = float(msg.yaw * (180.0 / 3.14159265))

                # jika tidak dapat pesan apapun dalam 5 detik
                if time.time() - last_msg_time > 5.0:
                    print("[MAVLINK] Connection lost (timeout > 5s)... ")
                    with state_lock:
                        data['mavlink_connected'] = False
                    break

        except Exception as e:
            print(f"[MAVLINK] Error: {e}")
            with state_lock:
                data['mavlink_connected'] = False
            time.sleep(RECONNECT_DELAY_S)
        finally:
            if master is not None:
                try:
                    master.close()
                except Exception:
                    pass


# Routes
@app.route('/api/trajectory', methods=['GET'])
def get_telemetry():
    with state_lock:
        return jsonify({
            'x': round(data['x'], 2),
            'y': round(data['y'], 2),
            'yaw': round(data['yaw'], 1),
            'mavlink_connected': data['mavlink_connected'],
        })


# Entrypoint
if __name__ == '__main__':
    mav_thread = threading.Thread(target=mavlink_worker, daemon=True)
    mav_thread.start()

    app.run(host='0.0.0.0', port=8007)
