# Just in case when needed.


# from pymavlink import mavutil
# import math
# from flask import Flask, jsonify, request
# from flask_cors import CORS
# import threading
# import time

# # ---------------------------------------------------------------------------
# # Konfigurasi Endpoint MAVLink & Server
# # ---------------------------------------------------------------------------
# # Endpoint UDP untuk menerima data telemetri MAVLink dari Pixhawk / Companion Computer
# MAVLINK_UDP_ENDPOINT = 'udpin:0.0.0.0:14553'
# HEARTBEAT_TIMEOUT_S = 10.0
# RECONNECT_DELAY_S = 3.0

# app = Flask(__name__)
# CORS(app)

# state_lock = threading.Lock()

# # 'dummy' atau 'real' - default 'dummy' agar langsung dapat divisualisasikan saat pengujian
# current_source = 'dummy'

# # Data mentah dari sensor / MAVLink
# real_data = {
#     'x': 0.0,
#     'y': 0.0,
#     'z': 0.0,
#     'yaw': 0.0,
#     'mavlink_connected': False,
# }

# # Data simulasi tiruan untuk pengujian tanpa perangkat fisik
# dummy_data = {
#     'x': 0.0,
#     'y': 0.0,
#     'z': 0.0,
#     'yaw': 0.0,
# }

# # Titik origin kalibrasi (offset)
# origin = {
#     'x': 0.0,
#     'y': 0.0,
#     'z': 0.0,
# }

# # ---------------------------------------------------------------------------
# # MAVLink Background Worker Thread
# # ---------------------------------------------------------------------------
# def mavlink_worker():
#     """Menerima data telemetri posisi & orientasi dari Pixhawk via MAVLink."""
#     while True:
#         master = None
#         try:
#             print(f"[MAVLINK] Menghubungkan ke {MAVLINK_UDP_ENDPOINT} ...")
#             master = mavutil.mavlink_connection(MAVLINK_UDP_ENDPOINT)

#             hb = master.wait_heartbeat(timeout=HEARTBEAT_TIMEOUT_S)
#             if not hb:
#                 print("[MAVLINK] Tidak menerima heartbeat, mencoba menghubungkan ulang...")
#                 with state_lock:
#                     real_data['mavlink_connected'] = False
#                 time.sleep(RECONNECT_DELAY_S)
#                 continue

#             print(
#                 f"[MAVLINK] Heartbeat diterima. System ID: {master.target_system}, Component ID: {master.target_component}"
#             )

#             # Request data stream posisi (10 Hz)
#             master.mav.request_data_stream_send(
#                 master.target_system,
#                 master.target_component,
#                 mavutil.mavlink.MAV_DATA_STREAM_POSITION,
#                 10,
#                 1,
#             )

#             # Request data stream attitude / orientasi (10 Hz)
#             master.mav.request_data_stream_send(
#                 master.target_system,
#                 master.target_component,
#                 mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
#                 10,
#                 1,
#             )

#             # Request seluruh stream umum
#             master.mav.request_data_stream_send(
#                 master.target_system,
#                 master.target_component,
#                 mavutil.mavlink.MAV_DATA_STREAM_ALL,
#                 10,
#                 1,
#             )

#             last_msg_time = time.time()

#             # Looping penerimaan paket MAVLink
#             while True:
#                 msg = master.recv_match(blocking=True, timeout=1.0)

#                 if msg:
#                     last_msg_time = time.time()
#                     msg_type = msg.get_type()

#                     with state_lock:
#                         real_data['mavlink_connected'] = True

#                         if msg_type == 'HEARTBEAT':
#                             pass

#                         elif msg_type == 'LOCAL_POSITION_NED':
#                             # x = North (meter), y = East (meter), z = Down (meter)
#                             real_data['x'] = float(msg.x)
#                             real_data['y'] = float(msg.y)
#                             real_data['z'] = float(msg.z)

#                         elif msg_type == 'GLOBAL_POSITION_INT':
#                             if hasattr(msg, 'relative_alt'):
#                                 real_data['z'] = max(0.0, -float(msg.relative_alt) / 1000.0)

#                         elif msg_type == 'ATTITUDE':
#                             # Konversi radian yaw ke derajat (0 - 360)
#                             yaw_deg = (math.degrees(msg.yaw) + 360.0) % 360.0
#                             real_data['yaw'] = yaw_deg

#                 # Timeout jika tidak ada paket masuk selama lebih dari 5 detik
#                 if time.time() - last_msg_time > 5.0:
#                     print("[MAVLINK] Koneksi MAVLink terputus (timeout > 5s)...")
#                     with state_lock:
#                         real_data['mavlink_connected'] = False
#                     break

#         except Exception as e:
#             print(f"[MAVLINK] Terjadi kesalahan: {e}")
#             with state_lock:
#                 real_data['mavlink_connected'] = False
#             time.sleep(RECONNECT_DELAY_S)
#         finally:
#             if master is not None:
#                 try:
#                     master.close()
#                 except Exception:
#                     pass


# # ---------------------------------------------------------------------------
# # Dummy Simulation Worker Thread (20 Hz)
# # ---------------------------------------------------------------------------
# def dummy_worker():
#     """Menghasilkan pola trajectory halus untuk pengujian UI tanpa MAVLink."""
#     t0 = time.time()
#     while True:
#         t = time.time() - t0
#         speed = 0.22  # rad/detik
#         scale_x = 3.0  # rentang sumbu X (meter)
#         scale_y = 2.0  # rentang sumbu Y (meter)

#         # Pola kurva lemniscate / figure-8 di dalam kolam
#         x = scale_x * math.sin(t * speed)
#         y = scale_y * math.sin(t * speed * 2.0)
#         z = 1.0 + 0.3 * math.sin(t * speed * 0.5)

#         # Hitung sudut heading (yaw) berdasarkan vektor pergerakan
#         dx = scale_x * speed * math.cos(t * speed)
#         dy = scale_y * speed * 2.0 * math.cos(t * speed * 2.0)
#         yaw_rad = math.atan2(dy, dx)
#         yaw_deg = (math.degrees(yaw_rad) + 360.0) % 360.0

#         with state_lock:
#             dummy_data['x'] = x
#             dummy_data['y'] = y
#             dummy_data['z'] = z
#             dummy_data['yaw'] = yaw_deg

#         time.sleep(0.05)


# # ---------------------------------------------------------------------------
# # API Routes
# # ---------------------------------------------------------------------------
# @app.route('/api/trajectory', methods=['GET'])
# def get_telemetry():
#     """Mengembalikan posisi relatif dari titik origin, data raw, origin offset, serta status koneksi."""
#     with state_lock:
#         source = current_source
#         if source == 'real':
#             raw_x = real_data['x']
#             raw_y = real_data['y']
#             raw_z = real_data['z']
#             yaw = real_data['yaw']
#             connected = real_data['mavlink_connected']
#         else:
#             raw_x = dummy_data['x']
#             raw_y = dummy_data['y']
#             raw_z = dummy_data['z']
#             yaw = dummy_data['yaw']
#             connected = real_data['mavlink_connected']

#         # Hitung koordinat relatif terhadap titik origin yang telah dikalibrasi
#         rel_x = raw_x - origin['x']
#         rel_y = raw_y - origin['y']
#         rel_z = raw_z - origin['z']

#         return jsonify({
#             'source': source,
#             'x': round(rel_x, 3),
#             'y': round(rel_y, 3),
#             'z': round(rel_z, 3),
#             'raw_x': round(raw_x, 3),
#             'raw_y': round(raw_y, 3),
#             'raw_z': round(raw_z, 3),
#             'origin_x': round(origin['x'], 3),
#             'origin_y': round(origin['y'], 3),
#             'origin_z': round(origin['z'], 3),
#             'yaw': round(yaw, 1),
#             'mavlink_connected': connected,
#         })


# @app.route('/api/origin/calibrate', methods=['POST'])
# @app.route('/api/calibrate', methods=['POST'])
# def calibrate_origin():
#     """Mengatur posisi saat ini sebagai titik (0, 0, 0) baru (Origin Calibration)."""
#     with state_lock:
#         if current_source == 'real':
#             origin['x'] = real_data['x']
#             origin['y'] = real_data['y']
#             origin['z'] = real_data['z']
#         else:
#             origin['x'] = dummy_data['x']
#             origin['y'] = dummy_data['y']
#             origin['z'] = dummy_data['z']

#         return jsonify({
#             'status': 'ok',
#             'message': 'Titik origin berhasil dikalibrasi ke posisi saat ini',
#             'origin': {
#                 'x': round(origin['x'], 3),
#                 'y': round(origin['y'], 3),
#                 'z': round(origin['z'], 3),
#             }
#         })


# @app.route('/api/origin/reset', methods=['POST'])
# def reset_origin():
#     """Mereset titik origin kembali ke (0, 0, 0)."""
#     with state_lock:
#         origin['x'] = 0.0
#         origin['y'] = 0.0
#         origin['z'] = 0.0

#         return jsonify({
#             'status': 'ok',
#             'message': 'Titik origin di-reset ke default (0, 0, 0)',
#             'origin': {'x': 0.0, 'y': 0.0, 'z': 0.0}
#         })


# @app.route('/api/source', methods=['POST'])
# def set_source():
#     """Mengubah sumber data antara 'real' (MAVLink Pixhawk) atau 'dummy' (Simulasi)."""
#     global current_source
#     payload = request.get_json(silent=True) or {}
#     requested = payload.get('source')

#     if requested not in ('real', 'dummy'):
#         return jsonify({'error': 'source harus "real" atau "dummy"'}), 400

#     with state_lock:
#         current_source = requested

#     return jsonify({'status': 'ok', 'source': current_source})


# # ---------------------------------------------------------------------------
# # Entrypoint
# # ---------------------------------------------------------------------------
# if __name__ == '__main__':
#     mav_thread = threading.Thread(target=mavlink_worker, daemon=True)
#     dummy_thread = threading.Thread(target=dummy_worker, daemon=True)
#     mav_thread.start()
#     dummy_thread.start()

#     print("[ROV TRAJECTORY] Server Backend aktif pada http://0.0.0.0:8007")
#     app.run(host='0.0.0.0', port=8007, debug=False, threaded=True)
